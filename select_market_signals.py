#!/usr/bin/env python3
"""Select the first qualifying hourly flag per market."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from compute_formula_scores import FINAL_SCORE_COLUMN


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Select the first qualifying signal per market."
    )
    parser.add_argument(
        "--formula-scores",
        type=Path,
        default=Path("outputs/formula_scores.csv"),
    )
    parser.add_argument(
        "--score-column",
        default=FINAL_SCORE_COLUMN,
        choices=[FINAL_SCORE_COLUMN],
        help="Frozen final combined score used for the study.",
    )
    parser.add_argument("--threshold", type=float, default=2.0)
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path("data/market_registry.csv"),
    )
    parser.add_argument(
        "--study-group-prefix",
        help="Optional registry study-group prefix to retain before selecting flags.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/market_signal_results.csv"),
    )
    return parser.parse_args()


def select_first_flags(
    scores: pd.DataFrame,
    score_column: str,
    threshold: float = 2.0,
) -> pd.DataFrame:
    required = {"market_id", "market_slug", "timestamp_utc", score_column}
    missing = sorted(required - set(scores.columns))
    if missing:
        raise ValueError(f"Formula scores missing required columns: {', '.join(missing)}")

    filtered = scores.copy()
    filtered["timestamp_utc"] = pd.to_datetime(
        filtered["timestamp_utc"], utc=True, errors="coerce"
    )
    filtered[score_column] = pd.to_numeric(filtered[score_column], errors="coerce")
    filtered = filtered.dropna(subset=["timestamp_utc", score_column])
    filtered = filtered[filtered[score_column] >= threshold]
    if filtered.empty:
        return pd.DataFrame(columns=["market_id", "market_slug", "flag_time_utc"])

    first_flags = (
        filtered.sort_values(["market_id", "timestamp_utc"])
        .groupby(["market_id", "market_slug"], as_index=False)
        .first()
        .rename(columns={"timestamp_utc": "flag_time_utc"})
    )
    return first_flags.loc[:, ["market_id", "market_slug", "flag_time_utc"]]


def filter_scores_by_study_group_prefix(
    scores: pd.DataFrame,
    registry: pd.DataFrame,
    study_group_prefix: str | None,
) -> pd.DataFrame:
    if not study_group_prefix:
        return scores.copy()

    required = {"market_id", "market_slug", "study_group"}
    missing = sorted(required - set(registry.columns))
    if missing:
        raise ValueError(f"Market registry missing required columns: {', '.join(missing)}")

    allowed = registry.loc[
        registry["study_group"].fillna("").astype(str).str.startswith(study_group_prefix),
        ["market_id", "market_slug"],
    ].copy()
    allowed["market_id"] = allowed["market_id"].astype("string")
    filtered = scores.copy()
    filtered["market_id"] = filtered["market_id"].astype("string")
    return filtered.merge(allowed, on=["market_id", "market_slug"], how="inner")


def main() -> None:
    args = parse_args()
    scores = pd.read_csv(args.formula_scores, dtype={"market_id": "string"})
    registry = pd.read_csv(args.registry, dtype={"market_id": "string"})
    scores = filter_scores_by_study_group_prefix(
        scores,
        registry,
        args.study_group_prefix,
    )
    signals = select_first_flags(scores, args.score_column, args.threshold)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    signals.to_csv(args.output, index=False)
    print(f"Wrote {len(signals):,} flagged markets to {args.output}")


if __name__ == "__main__":
    main()
