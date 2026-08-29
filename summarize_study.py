#!/usr/bin/env python3
"""Summarize the final event-level backtest using excess returns only."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


SUMMARY_COLUMNS = [
    "n_markets",
    "mean_excess_return_pct",
    "median_excess_return_pct",
    "win_rate",
    "p_value_one_sided",
    "ci_95_lower_pct",
    "ci_95_upper_pct",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize the final backtest study.")
    parser.add_argument(
        "--backtest-results",
        type=Path,
        default=Path("outputs/backtest_results.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/study_summary.csv"),
    )
    parser.add_argument("--bootstrap-samples", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=0)
    return parser.parse_args()


def bootstrap_ci(
    values: np.ndarray,
    samples: int = 10_000,
    seed: int = 0,
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    draws = rng.choice(values, size=(samples, len(values)), replace=True)
    means = draws.mean(axis=1)
    lower, upper = np.percentile(means, [2.5, 97.5])
    return float(lower), float(upper)


def summarize_results(
    backtest_results: pd.DataFrame,
    bootstrap_samples: int = 10_000,
    seed: int = 0,
) -> pd.DataFrame:
    if "excess_return_pct" not in backtest_results.columns:
        raise ValueError("Backtest results must contain excess_return_pct.")
    values = pd.to_numeric(
        backtest_results["excess_return_pct"], errors="coerce"
    ).dropna().to_numpy()
    if len(values) == 0:
        raise ValueError("Backtest results contain no valid excess_return_pct values.")

    if len(values) >= 2:
        p_value = float(stats.ttest_1samp(values, popmean=0.0, alternative="greater").pvalue)
        ci_lower, ci_upper = bootstrap_ci(values, bootstrap_samples, seed)
    else:
        p_value = np.nan
        ci_lower = np.nan
        ci_upper = np.nan

    summary = pd.DataFrame(
        [
            {
                "n_markets": int(len(values)),
                "mean_excess_return_pct": float(values.mean()),
                "median_excess_return_pct": float(np.median(values)),
                "win_rate": float((values > 0).mean()),
                "p_value_one_sided": p_value,
                "ci_95_lower_pct": ci_lower,
                "ci_95_upper_pct": ci_upper,
            }
        ],
        columns=SUMMARY_COLUMNS,
    )
    return summary


def main() -> None:
    args = parse_args()
    results = pd.read_csv(args.backtest_results)
    summary = summarize_results(results, args.bootstrap_samples, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.output, index=False)
    print(f"Wrote study summary to {args.output}")


if __name__ == "__main__":
    main()
