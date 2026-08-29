#!/usr/bin/env python3
"""Compute the five approved informed-trading formulas on hourly market data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


APPROVED_FORMULA_COLUMNS = [
    "sustained_shock_score",
    "fragile_repricing_score",
    "spread_stress_score",
    "impact_accepted_score",
    "anti_noise_score",
]
FINAL_SUSPICION_SCORE_FEATURE = "final_suspicion_score"
FINAL_SCORE_COLUMN = "final_suspicion_z"
BASELINE_FEATURE_COLUMNS = [
    "abs_initial_move",
    "log_trade_notional",
    "log_touch_depth_over_trade_volume",
    "relative_spread",
    "log_price_impact_per_dollar",
    "clipped_retention_ratio_6h",
    "log_noise_ratio_6h",
]
FEATURE_TO_Z_COLUMN = {
    "abs_initial_move": "z_abs_initial_move",
    "log_trade_notional": "z_log_trade_notional",
    "log_touch_depth_over_trade_volume": "z_log_touch_depth_over_trade_volume",
    "relative_spread": "z_relative_spread",
    "log_price_impact_per_dollar": "z_log_price_impact_per_dollar",
    "clipped_retention_ratio_6h": "z_clipped_retention_ratio_6h",
    "log_noise_ratio_6h": "z_log_noise_ratio_6h",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute approved hourly informed-trading formula scores."
    )
    parser.add_argument("--registry", type=Path, default=Path("data/market_registry.csv"))
    parser.add_argument(
        "--baseline-stats",
        type=Path,
        default=Path("data/formula_baseline_stats.csv"),
    )
    parser.add_argument("--output", type=Path, default=Path("outputs/formula_scores.csv"))
    return parser.parse_args()


def numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce")


def parse_book_levels(raw: Any) -> list[tuple[float, float]]:
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if not isinstance(raw, list):
        return []

    levels: list[tuple[float, float]] = []
    for level in raw:
        if not isinstance(level, (list, tuple)) or len(level) < 2:
            continue
        try:
            price = float(level[0])
            size = float(level[1])
        except (TypeError, ValueError):
            continue
        if np.isfinite(price) and np.isfinite(size) and price > 0 and size >= 0:
            levels.append((price, size))
    return levels


def summarize_book(row: pd.Series) -> pd.Series:
    bids = parse_book_levels(row.get("bids"))
    asks = parse_book_levels(row.get("asks"))
    best_bid = max((price for price, _ in bids), default=np.nan)
    best_ask = min((price for price, _ in asks), default=np.nan)
    top_bid_size = sum(size for price, size in bids if price == best_bid)
    top_ask_size = sum(size for price, size in asks if price == best_ask)
    return pd.Series(
        {
            "book_best_bid": best_bid,
            "book_best_ask": best_ask,
            "top_bid_size": top_bid_size if np.isfinite(best_bid) else np.nan,
            "top_ask_size": top_ask_size if np.isfinite(best_ask) else np.nan,
        }
    )


def prepare_events(raw: pd.DataFrame) -> pd.DataFrame:
    required = {"timestamp", "event_type"}
    missing = sorted(required - set(raw.columns))
    if missing:
        raise ValueError(f"Raw market data missing required columns: {', '.join(missing)}")

    events = raw.copy()
    events["timestamp"] = pd.to_datetime(events["timestamp"], utc=True, errors="coerce")
    events = events.dropna(subset=["timestamp"]).sort_values("timestamp")

    book_rows = events["event_type"].eq("book")
    if book_rows.any():
        book_summary = events.loc[book_rows].apply(summarize_book, axis=1)
        for column in book_summary.columns:
            events.loc[book_rows, column] = book_summary[column]
    else:
        for column in ["book_best_bid", "book_best_ask", "top_bid_size", "top_ask_size"]:
            events[column] = np.nan

    direct_best_bid = numeric_series(events, "best_bid")
    direct_best_ask = numeric_series(events, "best_ask")
    events["event_best_bid"] = direct_best_bid.combine_first(events["book_best_bid"])
    events["event_best_ask"] = direct_best_ask.combine_first(events["book_best_ask"])

    valid_quote = (
        events["event_best_bid"].gt(0)
        & events["event_best_ask"].gt(0)
        & events["event_best_ask"].ge(events["event_best_bid"])
    )
    events["midpoint"] = np.where(
        valid_quote,
        (events["event_best_bid"] + events["event_best_ask"]) / 2.0,
        np.nan,
    )

    last_trade_price = numeric_series(events, "price").where(
        events["event_type"].eq("last_trade_price")
    )
    events["derived_price"] = events["midpoint"].combine_first(last_trade_price)
    return events


def build_hourly_market_frame(raw: pd.DataFrame) -> pd.DataFrame:
    events = prepare_events(raw)
    if events.empty:
        raise ValueError("Raw market data contains no valid timestamped rows.")

    price_events = events.dropna(subset=["derived_price"]).copy()
    if price_events.empty:
        raise ValueError("Raw market data contains no usable midpoint or trade prices.")

    hourly_price = (
        price_events.set_index("timestamp")
        .resample("1h")
        .agg(price=("derived_price", "last"))
    )
    hourly_price["price"] = hourly_price["price"].ffill()

    quote_events = events.dropna(subset=["event_best_bid", "event_best_ask"]).copy()
    hourly_quotes = (
        quote_events.set_index("timestamp")
        .resample("1h")
        .agg(best_bid=("event_best_bid", "last"), best_ask=("event_best_ask", "last"))
    )
    hourly_quotes[["best_bid", "best_ask"]] = hourly_quotes[
        ["best_bid", "best_ask"]
    ].ffill()

    book_events = events.dropna(subset=["top_bid_size", "top_ask_size"]).copy()
    hourly_depth = (
        book_events.set_index("timestamp")
        .resample("1h")
        .agg(top_bid_size=("top_bid_size", "last"), top_ask_size=("top_ask_size", "last"))
    )
    hourly_depth[["top_bid_size", "top_ask_size"]] = hourly_depth[
        ["top_bid_size", "top_ask_size"]
    ].ffill()

    trades = events[events["event_type"].eq("last_trade_price")].copy()
    trades["trade_size"] = numeric_series(trades, "size")
    trades["trade_price"] = numeric_series(trades, "price")
    trades = trades.dropna(subset=["trade_size", "trade_price"])
    trades["trade_notional"] = trades["trade_size"] * trades["trade_price"]
    hourly_trades = (
        trades.set_index("timestamp")
        .resample("1h")
        .agg(
            hourly_trade_volume=("trade_size", "sum"),
            hourly_trade_notional=("trade_notional", "sum"),
        )
    )

    hourly = hourly_price.join(hourly_quotes, how="outer").join(hourly_depth, how="outer")
    hourly = hourly.join(hourly_trades, how="outer").sort_index()
    hourly["price"] = hourly["price"].ffill()
    hourly[["best_bid", "best_ask", "top_bid_size", "top_ask_size"]] = hourly[
        ["best_bid", "best_ask", "top_bid_size", "top_ask_size"]
    ].ffill()
    hourly[["hourly_trade_volume", "hourly_trade_notional"]] = hourly[
        ["hourly_trade_volume", "hourly_trade_notional"]
    ].fillna(0.0)
    hourly = hourly.dropna(subset=["price"]).reset_index(names="timestamp_utc")
    hourly["touch_depth"] = hourly["top_bid_size"] + hourly["top_ask_size"]
    midpoint = (hourly["best_bid"] + hourly["best_ask"]) / 2.0
    hourly["relative_spread"] = (
        (hourly["best_ask"] - hourly["best_bid"]) / midpoint.replace(0, np.nan)
    )
    return hourly


def add_raw_features(hourly: pd.DataFrame) -> pd.DataFrame:
    out = hourly.sort_values("timestamp_utc").copy()
    out["price_t_minus_1"] = out["price"].shift(1)
    out["price_t_plus_6h"] = out["price"].shift(-6)
    out["initial_move"] = out["price"] - out["price_t_minus_1"]
    out["abs_initial_move"] = out["initial_move"].abs()
    out["retained_move_6h"] = out["price_t_plus_6h"] - out["price_t_minus_1"]
    out["retention_ratio_6h"] = out["retained_move_6h"] / out["initial_move"].replace(
        0, np.nan
    )
    out["clipped_retention_ratio_6h"] = out["retention_ratio_6h"].clip(-1.0, 2.0)
    out["log_trade_notional"] = np.log1p(out["hourly_trade_notional"])
    depth_ratio = out["touch_depth"] / out["hourly_trade_volume"].where(
        out["hourly_trade_volume"] > 0
    )
    out["log_touch_depth_over_trade_volume"] = np.log(depth_ratio.where(depth_ratio > 0))
    impact_ratio = out["abs_initial_move"] / out["hourly_trade_notional"].where(
        out["hourly_trade_notional"] > 0
    )
    out["log_price_impact_per_dollar"] = np.log(impact_ratio.where(impact_ratio > 0))

    future_abs_moves = pd.concat(
        [
            out["price"].shift(-i).sub(out["price"].shift(-(i - 1))).abs()
            for i in range(1, 7)
        ],
        axis=1,
    )
    out["future_abs_move_sum_6h"] = future_abs_moves.sum(axis=1, min_count=6)
    out["future_net_move_6h"] = (out["price_t_plus_6h"] - out["price"]).abs()
    out["log_noise_ratio_6h"] = np.log1p(
        out["future_abs_move_sum_6h"] / out["future_net_move_6h"].replace(0, np.nan)
    )
    return out.replace([np.inf, -np.inf], np.nan)


def load_baseline_stats(path: Path) -> pd.DataFrame:
    stats = pd.read_csv(path)
    required = {"feature", "mean", "std"}
    missing = sorted(required - set(stats.columns))
    if missing:
        raise ValueError(f"Baseline stats missing required columns: {', '.join(missing)}")
    required_features = [*BASELINE_FEATURE_COLUMNS, FINAL_SUSPICION_SCORE_FEATURE]
    missing_features = sorted(set(required_features) - set(stats["feature"]))
    if missing_features:
        raise ValueError(
            f"Baseline stats missing required features: {', '.join(missing_features)}"
        )
    stats = stats.set_index("feature").loc[required_features].reset_index()
    stats["mean"] = pd.to_numeric(stats["mean"], errors="coerce")
    stats["std"] = pd.to_numeric(stats["std"], errors="coerce")
    if stats["mean"].isna().any() or stats["std"].isna().any() or stats["std"].le(0).any():
        raise ValueError("Baseline stats require finite means and positive standard deviations.")
    return stats


def add_baseline_zscores(features: pd.DataFrame, baseline_stats: pd.DataFrame) -> pd.DataFrame:
    out = features.copy()
    stats = baseline_stats.set_index("feature")
    for feature, z_column in FEATURE_TO_Z_COLUMN.items():
        mean = float(stats.loc[feature, "mean"])
        std = float(stats.loc[feature, "std"])
        out[z_column] = (out[feature] - mean) / std
    return out


def apply_formula_scores(zscored: pd.DataFrame) -> pd.DataFrame:
    out = zscored.copy()
    out["sustained_shock_score"] = (
        0.40 * out["z_abs_initial_move"]
        + 0.30 * out["z_log_trade_notional"]
        + 0.30 * out["z_clipped_retention_ratio_6h"]
    )
    out["fragile_repricing_score"] = (
        0.35 * out["z_abs_initial_move"]
        + 0.25 * out["z_log_trade_notional"]
        - 0.20 * out["z_log_touch_depth_over_trade_volume"]
        + 0.20 * out["z_clipped_retention_ratio_6h"]
    )
    out["spread_stress_score"] = (
        0.35 * out["z_abs_initial_move"]
        + 0.25 * out["z_log_trade_notional"]
        + 0.20 * out["z_relative_spread"]
        + 0.20 * out["z_clipped_retention_ratio_6h"]
    )
    out["impact_accepted_score"] = (
        0.35 * out["z_abs_initial_move"]
        + 0.25 * out["z_log_trade_notional"]
        + 0.20 * out["z_log_price_impact_per_dollar"]
        + 0.20 * out["z_clipped_retention_ratio_6h"]
    )
    out["anti_noise_score"] = (
        0.35 * out["z_abs_initial_move"]
        + 0.25 * out["z_log_trade_notional"]
        + 0.25 * out["z_clipped_retention_ratio_6h"]
        - 0.15 * out["z_log_noise_ratio_6h"]
    )
    return out


def add_quality_weight(scored: pd.DataFrame) -> pd.DataFrame:
    out = scored.copy()
    hourly_trade_notional = (
        out["hourly_trade_notional"]
        if "hourly_trade_notional" in out.columns
        else np.expm1(out["log_trade_notional"])
    )
    out["move_weight"] = out["abs_initial_move"] / (out["abs_initial_move"] + 0.10)
    out["volume_weight"] = hourly_trade_notional / (hourly_trade_notional + 1000.0)
    out["retention_weight"] = ((out["clipped_retention_ratio_6h"] + 1.0) / 3.0).clip(
        0.0,
        1.0,
    )
    out["quality_weight"] = (
        out["move_weight"] * out["volume_weight"] * out["retention_weight"]
    )
    return out


def apply_final_suspicion_score(scored: pd.DataFrame) -> pd.DataFrame:
    out = add_quality_weight(scored)
    weighted_columns: list[str] = []
    for column in APPROVED_FORMULA_COLUMNS:
        weighted_column = f"weighted_{column}"
        out[weighted_column] = out[column] * out["quality_weight"]
        weighted_columns.append(weighted_column)
    out[FINAL_SUSPICION_SCORE_FEATURE] = out[weighted_columns].mean(
        axis=1,
        skipna=False,
    )
    return out


def add_final_suspicion_z(scored: pd.DataFrame, baseline_stats: pd.DataFrame) -> pd.DataFrame:
    out = scored.copy()
    stats = baseline_stats.set_index("feature")
    mean = float(stats.loc[FINAL_SUSPICION_SCORE_FEATURE, "mean"])
    std = float(stats.loc[FINAL_SUSPICION_SCORE_FEATURE, "std"])
    out[FINAL_SCORE_COLUMN] = (out[FINAL_SUSPICION_SCORE_FEATURE] - mean) / std
    return out


def load_registry(path: Path) -> pd.DataFrame:
    registry = pd.read_csv(path, dtype={"market_id": "string", "yes_token_id": "string"})
    required = {"market_id", "market_slug", "source_data_path", "yes_token_id"}
    missing = sorted(required - set(registry.columns))
    if missing:
        raise ValueError(f"Market registry missing required columns: {', '.join(missing)}")
    return registry


def build_formula_scores(
    registry: pd.DataFrame,
    baseline_stats: pd.DataFrame,
) -> pd.DataFrame:
    market_frames: list[pd.DataFrame] = []
    for row in registry.itertuples(index=False):
        raw_path = Path(row.source_data_path)
        raw = pd.read_parquet(raw_path)
        if "asset_id" not in raw.columns:
            raise ValueError(f"Raw market data missing asset_id for market_slug={row.market_slug}.")
        raw = raw[raw["asset_id"].astype("string").eq(str(row.yes_token_id))].copy()
        if raw.empty:
            raise ValueError(f"No YES-token rows found for market_slug={row.market_slug}.")
        hourly = add_raw_features(build_hourly_market_frame(raw))
        hourly["market_id"] = str(row.market_id)
        hourly["market_slug"] = row.market_slug
        market_frames.append(hourly)

    features = pd.concat(market_frames, ignore_index=True)
    zscored = add_baseline_zscores(features, baseline_stats)
    scored = apply_formula_scores(zscored)
    scored = apply_final_suspicion_score(scored)
    scored = add_final_suspicion_z(scored, baseline_stats)
    output_columns = [
        "market_id",
        "market_slug",
        "timestamp_utc",
        *APPROVED_FORMULA_COLUMNS,
        FINAL_SCORE_COLUMN,
    ]
    return scored.loc[:, output_columns].sort_values(
        ["market_id", "timestamp_utc"]
    ).reset_index(drop=True)


def main() -> None:
    args = parse_args()
    registry = load_registry(args.registry)
    baseline_stats = load_baseline_stats(args.baseline_stats)
    scores = build_formula_scores(registry, baseline_stats)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    scores.to_csv(args.output, index=False)
    print(f"Wrote {len(scores):,} rows to {args.output}")


if __name__ == "__main__":
    main()
