#!/usr/bin/env python3
"""Build broad-market feature baselines for approved formula z-scores."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests

from compute_formula_scores import (
    BASELINE_FEATURE_COLUMNS,
    FINAL_SUSPICION_SCORE_FEATURE,
    add_baseline_zscores,
    add_raw_features,
    apply_final_suspicion_score,
    apply_formula_scores,
    build_hourly_market_frame,
)


BASELINE_REGISTRY_COLUMNS = [
    "market_id",
    "market_slug",
    "market_question",
    "broad_category",
    "series_slug",
    "start_time_utc",
    "resolution_time_utc",
    "volume",
    "source_data_path",
    "yes_token_id",
]
BROAD_CATEGORY_TAGS = {
    "sports": "sports",
    "crypto": "crypto",
    "politics": "politics",
    "economy": "economy",
    "business": "business",
    "pop-culture": "pop-culture",
    "science": "science",
    "tech": "tech",
    "world": "world",
    "weather": "weather",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build feature baseline statistics from many historical markets."
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path("data/baseline_market_registry.csv"),
        help="CSV of baseline markets with raw parquet paths and YES token ids.",
    )
    parser.add_argument(
        "--stats-output",
        type=Path,
        default=Path("data/formula_baseline_stats.csv"),
    )
    parser.add_argument(
        "--discover-output",
        type=Path,
        default=Path("data/baseline_market_registry.csv"),
    )
    parser.add_argument(
        "--discover",
        action="store_true",
        help="Query Polymarket Gamma markets API and write a candidate baseline registry.",
    )
    parser.add_argument("--closed-after", help="UTC lower bound for discovered closed markets.")
    parser.add_argument("--closed-before", help="UTC upper bound for discovered closed markets.")
    parser.add_argument("--started-after", help="UTC lower bound for discovered market start times.")
    parser.add_argument("--series-slug", help="Optional event series slug filter.")
    parser.add_argument("--min-volume", type=float, default=10_000.0)
    parser.add_argument("--min-duration-hours", type=float, default=0.0)
    parser.add_argument("--max-duration-hours", type=float)
    parser.add_argument("--max-markets", type=int, default=100)
    parser.add_argument(
        "--max-per-category",
        type=int,
        default=0,
        help="Optional maximum selected markets per broad category; 0 means no cap.",
    )
    parser.add_argument("--page-size", type=int, default=100)
    return parser.parse_args()


def parse_json_list(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(value) for value in raw]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return [str(value) for value in parsed]
    return []


def nested_series_slug(market: dict[str, Any]) -> str | None:
    events = market.get("events")
    if not isinstance(events, list) or not events:
        return None
    first = events[0]
    if not isinstance(first, dict):
        return None
    value = first.get("seriesSlug")
    return str(value) if value else None


def nested_event_id(market: dict[str, Any]) -> str | None:
    events = market.get("events")
    if not isinstance(events, list) or not events:
        return None
    first = events[0]
    if not isinstance(first, dict):
        return None
    value = first.get("id")
    return str(value) if value else None


def is_binary_yes_no_market(market: dict[str, Any]) -> bool:
    outcomes = [value.lower() for value in parse_json_list(market.get("outcomes"))]
    token_ids = parse_json_list(market.get("clobTokenIds"))
    return outcomes == ["yes", "no"] and len(token_ids) == 2


def within_timestamp_bounds(
    timestamp: pd.Timestamp,
    lower: pd.Timestamp | None,
    upper: pd.Timestamp | None,
) -> bool:
    if lower is not None and timestamp < lower:
        return False
    if upper is not None and timestamp > upper:
        return False
    return True


def market_duration_hours(market: dict[str, Any]) -> float | None:
    start = pd.to_datetime(market.get("startDate"), utc=True, errors="coerce")
    end = pd.to_datetime(
        market.get("closedTime") or market.get("endDate"),
        utc=True,
        errors="coerce",
    )
    if pd.isna(start) or pd.isna(end):
        return None
    return float((end - start).total_seconds() / 3600.0)


def fetch_event_tags(event_id: str, cache: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    if event_id not in cache:
        response = requests.get(
            f"https://gamma-api.polymarket.com/events/{event_id}/tags",
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        cache[event_id] = payload if isinstance(payload, list) else []
    return cache[event_id]


def infer_broad_category(tags: list[dict[str, Any]]) -> str | None:
    slugs = {str(tag.get("slug") or "") for tag in tags if isinstance(tag, dict)}
    for slug, category in BROAD_CATEGORY_TAGS.items():
        if slug in slugs:
            return category
    return None


def discover_candidate_markets(
    closed_after: str | None,
    closed_before: str | None,
    started_after: str | None,
    series_slug: str | None,
    min_volume: float,
    min_duration_hours: float,
    max_duration_hours: float | None,
    max_markets: int,
    max_per_category: int,
    page_size: int,
) -> pd.DataFrame:
    lower = pd.to_datetime(closed_after, utc=True) if closed_after else None
    upper = pd.to_datetime(closed_before, utc=True) if closed_before else None
    started_lower = pd.to_datetime(started_after, utc=True) if started_after else None
    candidate_rows: list[dict[str, object]] = []
    tag_cache: dict[str, list[dict[str, Any]]] = {}
    offset = 0

    while True:
        response = requests.get(
            "https://gamma-api.polymarket.com/markets",
            params={
                "closed": "true",
                "limit": page_size,
                "offset": offset,
                "order": "closedTime",
                "ascending": "false",
            },
            timeout=30,
        )
        if response.status_code == 422:
            break
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list) or not payload:
            break

        for market in payload:
            if not isinstance(market, dict) or not is_binary_yes_no_market(market):
                continue

            closed_time = pd.to_datetime(market.get("closedTime"), utc=True, errors="coerce")
            if pd.isna(closed_time) or not within_timestamp_bounds(closed_time, lower, upper):
                continue
            start_time = pd.to_datetime(market.get("startDate"), utc=True, errors="coerce")
            if started_lower is not None and (pd.isna(start_time) or start_time < started_lower):
                continue

            duration_hours = market_duration_hours(market)
            if duration_hours is None or duration_hours < min_duration_hours:
                continue
            if max_duration_hours is not None and duration_hours > max_duration_hours:
                continue

            volume = pd.to_numeric(market.get("volumeNum"), errors="coerce")
            if not np.isfinite(volume) or float(volume) < min_volume:
                continue

            market_series_slug = nested_series_slug(market)
            if series_slug and market_series_slug != series_slug:
                continue
            event_id = nested_event_id(market)
            if not event_id:
                continue
            broad_category = infer_broad_category(fetch_event_tags(event_id, tag_cache))
            if not broad_category:
                continue
            token_ids = parse_json_list(market.get("clobTokenIds"))
            market_slug = str(market.get("slug") or "")
            candidate_rows.append(
                {
                    "market_id": str(market.get("id") or ""),
                    "market_slug": market_slug,
                    "market_question": str(market.get("question") or ""),
                    "broad_category": broad_category,
                    "series_slug": market_series_slug,
                    "start_time_utc": str(market.get("startDate") or ""),
                    "resolution_time_utc": str(market.get("closedTime") or ""),
                    "volume": float(volume),
                    "source_data_path": f"data/raw_orderbooks/{market_slug}.parquet",
                    "yes_token_id": token_ids[0],
                }
            )

        last_market = payload[-1]
        if isinstance(last_market, dict):
            last_closed = pd.to_datetime(last_market.get("closedTime"), utc=True, errors="coerce")
            if lower is not None and not pd.isna(last_closed) and last_closed < lower:
                break
        offset += page_size

    candidates = pd.DataFrame(candidate_rows, columns=BASELINE_REGISTRY_COLUMNS)
    return select_varied_candidates(candidates, max_markets, max_per_category)


def select_varied_candidates(
    candidates: pd.DataFrame,
    max_markets: int,
    max_per_category: int,
) -> pd.DataFrame:
    if candidates.empty:
        return candidates.copy()

    buckets = {
        category: group.sort_values("volume", ascending=False).reset_index(drop=True)
        for category, group in candidates.groupby("broad_category")
    }
    category_order = sorted(buckets)
    positions = {category: 0 for category in category_order}
    selected_counts = {category: 0 for category in category_order}
    selected_rows: list[pd.Series] = []

    while len(selected_rows) < max_markets:
        made_progress = False
        for category in category_order:
            if len(selected_rows) >= max_markets:
                break
            if max_per_category > 0 and selected_counts[category] >= max_per_category:
                continue
            bucket = buckets[category]
            position = positions[category]
            if position >= len(bucket):
                continue
            selected_rows.append(bucket.iloc[position])
            positions[category] += 1
            selected_counts[category] += 1
            made_progress = True
        if not made_progress:
            break

    if not selected_rows:
        return candidates.iloc[0:0].copy()
    return pd.DataFrame(selected_rows, columns=BASELINE_REGISTRY_COLUMNS).reset_index(drop=True)


def load_baseline_registry(path: Path) -> pd.DataFrame:
    registry = pd.read_csv(path, dtype={"market_id": "string", "yes_token_id": "string"})
    required = {"market_id", "market_slug", "source_data_path", "yes_token_id"}
    missing = sorted(required - set(registry.columns))
    if missing:
        raise ValueError(f"Baseline registry missing required columns: {', '.join(missing)}")
    return registry


def load_baseline_feature_rows(registry: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for row in registry.itertuples(index=False):
        raw_path = Path(row.source_data_path)
        if not raw_path.exists():
            raise FileNotFoundError(f"Missing baseline raw parquet: {raw_path}")
        raw = pd.read_parquet(raw_path)
        raw = raw[raw["asset_id"].astype("string").eq(str(row.yes_token_id))].copy()
        if raw.empty:
            raise ValueError(f"No YES-token rows found for baseline market_slug={row.market_slug}.")
        hourly = add_raw_features(build_hourly_market_frame(raw))
        hourly["market_id"] = str(row.market_id)
        frames.append(hourly.loc[:, ["market_id", *BASELINE_FEATURE_COLUMNS]])
    return pd.concat(frames, ignore_index=True)


def compute_baseline_stats(
    feature_rows: pd.DataFrame,
    feature_columns: list[str] | None = None,
) -> pd.DataFrame:
    feature_columns = feature_columns or BASELINE_FEATURE_COLUMNS
    records: list[dict[str, object]] = []
    for feature in feature_columns:
        working = feature_rows.loc[:, ["market_id", feature]].copy()
        working[feature] = pd.to_numeric(working[feature], errors="coerce").replace(
            [np.inf, -np.inf], np.nan
        )
        per_market = working.groupby("market_id")[feature].agg(
            market_mean="mean",
            market_std=lambda values: values.std(ddof=0),
            hourly_rows="count",
        )
        valid_means = per_market["market_mean"].dropna()
        valid_stds = per_market["market_std"].replace([np.inf, -np.inf], np.nan).dropna()
        records.append(
            {
                "feature": feature,
                "mean": float(valid_means.mean()) if not valid_means.empty else np.nan,
                "std": float(valid_stds.mean()) if not valid_stds.empty else np.nan,
                "n_markets_mean": int(len(valid_means)),
                "n_markets_std": int(len(valid_stds)),
                "n_hourly_rows": int(per_market["hourly_rows"].sum()),
            }
        )
    stats = pd.DataFrame(records)
    invalid = stats[stats["std"].isna() | stats["std"].le(0)]
    if not invalid.empty:
        features = ", ".join(invalid["feature"].tolist())
        raise ValueError(f"Baseline stats require positive standard deviations for: {features}")
    return stats


def append_final_suspicion_baseline_stats(
    feature_rows: pd.DataFrame,
    feature_stats: pd.DataFrame,
) -> pd.DataFrame:
    zscored = add_baseline_zscores(feature_rows, feature_stats)
    scored = apply_formula_scores(zscored)
    scored = apply_final_suspicion_score(scored)
    final_stats = compute_baseline_stats(
        scored.loc[:, ["market_id", FINAL_SUSPICION_SCORE_FEATURE]],
        [FINAL_SUSPICION_SCORE_FEATURE],
    )
    return pd.concat([feature_stats, final_stats], ignore_index=True)


def main() -> None:
    args = parse_args()
    if args.discover:
        discovered = discover_candidate_markets(
            closed_after=args.closed_after,
            closed_before=args.closed_before,
            started_after=args.started_after,
            series_slug=args.series_slug,
            min_volume=args.min_volume,
            min_duration_hours=args.min_duration_hours,
            max_duration_hours=args.max_duration_hours,
            max_markets=args.max_markets,
            max_per_category=args.max_per_category,
            page_size=args.page_size,
        )
        args.discover_output.parent.mkdir(parents=True, exist_ok=True)
        discovered.to_csv(args.discover_output, index=False)
        print(f"Wrote {len(discovered):,} candidate markets to {args.discover_output}")
        return

    registry = load_baseline_registry(args.registry)
    feature_rows = load_baseline_feature_rows(registry)
    stats = append_final_suspicion_baseline_stats(
        feature_rows,
        compute_baseline_stats(feature_rows),
    )
    args.stats_output.parent.mkdir(parents=True, exist_ok=True)
    stats.to_csv(args.stats_output, index=False)
    print(f"Wrote baseline stats for {len(stats):,} features to {args.stats_output}")


if __name__ == "__main__":
    main()
