#!/usr/bin/env python3
"""Run one event-level associated-asset trade per flagged Polymarket event."""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests


PRICE_COLUMNS = ["asset", "timestamp_utc", "close"]
BACKTEST_COLUMNS = [
    "market_id",
    "market_slug",
    "associated_asset",
    "benchmark_asset",
    "flag_time_utc",
    "entry_time_utc",
    "resolution_time_utc",
    "associated_asset_return_pct",
    "benchmark_return_pct",
    "excess_return_pct",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the event-level asset backtest.")
    parser.add_argument(
        "--signals",
        type=Path,
        default=Path("outputs/market_signal_results.csv"),
    )
    parser.add_argument("--registry", type=Path, default=Path("data/market_registry.csv"))
    parser.add_argument(
        "--asset-prices",
        type=Path,
        default=Path("data/asset_prices.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/backtest_results.csv"),
    )
    return parser.parse_args()


def load_price_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=PRICE_COLUMNS)
    prices = pd.read_csv(path)
    required = set(PRICE_COLUMNS)
    missing = sorted(required - set(prices.columns))
    if missing:
        raise ValueError(f"Asset price table missing required columns: {', '.join(missing)}")
    prices["timestamp_utc"] = pd.to_datetime(prices["timestamp_utc"], utc=True, errors="coerce")
    prices["close"] = pd.to_numeric(prices["close"], errors="coerce")
    return prices.dropna(subset=["asset", "timestamp_utc", "close"])


def yahoo_symbol(asset: str) -> str:
    return asset


def fetch_price_bars(asset: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    start_day = start.normalize()
    end_day = end.normalize() + pd.Timedelta(days=1)
    params = {
        "period1": int(start_day.timestamp()),
        "period2": int(end_day.timestamp()),
        # A shared 30-minute grid lets 24/7 crypto assets and U.S. sessions
        # enter at the same timestamp when the benchmark is tradable.
        "interval": "30m",
        "events": "history",
    }
    response = requests.get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol(asset)}",
        params=params,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    result = payload.get("chart", {}).get("result") or []
    if not result:
        raise ValueError(f"No daily price data returned for asset={asset}.")

    chart = result[0]
    timestamps = chart.get("timestamp") or []
    closes = ((chart.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
    prices = pd.DataFrame(
        {
            "asset": asset,
            "timestamp_utc": pd.to_datetime(timestamps, unit="s", utc=True),
            "close": closes,
        }
    )
    prices["close"] = pd.to_numeric(prices["close"], errors="coerce")
    return prices.dropna(subset=["timestamp_utc", "close"]).loc[:, PRICE_COLUMNS]


def update_asset_prices(
    price_path: Path,
    assets: Iterable[str],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    existing = load_price_table(price_path)
    fetched = [fetch_price_bars(asset, start, end) for asset in sorted(set(assets))]
    combined = pd.concat([existing, *fetched], ignore_index=True)
    combined = (
        combined.drop_duplicates(subset=["asset", "timestamp_utc"], keep="last")
        .sort_values(["asset", "timestamp_utc"])
        .reset_index(drop=True)
    )
    price_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(price_path, index=False)
    return combined


def normalize_inputs(
    signals: pd.DataFrame,
    registry: pd.DataFrame,
    prices: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    signals = signals.copy()
    registry = registry.copy()
    prices = prices.copy()

    signals["market_id"] = signals["market_id"].astype("string")
    registry["market_id"] = registry["market_id"].astype("string")
    signals["flag_time_utc"] = pd.to_datetime(signals["flag_time_utc"], utc=True, errors="coerce")
    registry["resolution_time_utc"] = pd.to_datetime(
        registry["resolution_time_utc"], utc=True, errors="coerce"
    )
    prices["timestamp_utc"] = pd.to_datetime(prices["timestamp_utc"], utc=True, errors="coerce")
    prices["close"] = pd.to_numeric(prices["close"], errors="coerce")
    return signals, registry, prices


def pick_shared_entry_prices(
    associated_prices: pd.DataFrame,
    benchmark_prices: pd.DataFrame,
    flag_time: pd.Timestamp,
) -> tuple[pd.Series, pd.Series]:
    associated_after_flag = associated_prices[
        associated_prices["timestamp_utc"] > flag_time
    ][["timestamp_utc", "close"]]
    benchmark_after_flag = benchmark_prices[
        benchmark_prices["timestamp_utc"] > flag_time
    ][["timestamp_utc", "close"]]
    shared_entries = associated_after_flag.merge(
        benchmark_after_flag,
        on="timestamp_utc",
        how="inner",
        suffixes=("_associated", "_benchmark"),
    ).sort_values("timestamp_utc")
    if shared_entries.empty:
        raise ValueError("No shared tradable entry session exists after the flag time.")
    entry = shared_entries.iloc[0]
    associated_entry = pd.Series(
        {"timestamp_utc": entry["timestamp_utc"], "close": entry["close_associated"]}
    )
    benchmark_entry = pd.Series(
        {"timestamp_utc": entry["timestamp_utc"], "close": entry["close_benchmark"]}
    )
    return associated_entry, benchmark_entry


def pick_exit_price(
    asset_prices: pd.DataFrame,
    entry_time: pd.Timestamp,
    resolution_time: pd.Timestamp,
) -> pd.Series:
    ordered = asset_prices.sort_values("timestamp_utc")
    exit_candidates = ordered[ordered["timestamp_utc"] <= resolution_time]
    if exit_candidates.empty:
        raise ValueError("No session exists on or before the resolution time.")
    exit_row = exit_candidates.iloc[-1]
    if exit_row["timestamp_utc"] < entry_time:
        raise ValueError("Resolution occurs before the first tradable entry session.")
    return exit_row


def pct_return(entry_close: float, exit_close: float) -> float:
    return (exit_close / entry_close - 1.0) * 100.0


def build_backtest_results(
    signals: pd.DataFrame,
    registry: pd.DataFrame,
    prices: pd.DataFrame,
) -> pd.DataFrame:
    signals, registry, prices = normalize_inputs(signals, registry, prices)
    joined = signals.merge(registry, on=["market_id", "market_slug"], how="left", validate="one_to_one")
    required = {"associated_asset", "benchmark_asset", "resolution_time_utc"}
    missing = sorted(required - set(joined.columns))
    if missing:
        raise ValueError(f"Joined signal table missing required columns: {', '.join(missing)}")
    if joined[list(required)].isna().any().any():
        raise ValueError("Flagged markets must have associated asset, benchmark, and resolution time.")

    rows: list[dict[str, object]] = []
    for row in joined.itertuples(index=False):
        associated_prices = prices[prices["asset"].eq(row.associated_asset)]
        benchmark_prices = prices[prices["asset"].eq(row.benchmark_asset)]
        associated_entry, benchmark_entry = pick_shared_entry_prices(
            associated_prices, benchmark_prices, row.flag_time_utc
        )
        associated_exit = pick_exit_price(
            associated_prices, associated_entry["timestamp_utc"], row.resolution_time_utc
        )
        benchmark_exit = pick_exit_price(
            benchmark_prices, benchmark_entry["timestamp_utc"], row.resolution_time_utc
        )

        associated_return = pct_return(associated_entry["close"], associated_exit["close"])
        benchmark_return = pct_return(benchmark_entry["close"], benchmark_exit["close"])
        rows.append(
            {
                "market_id": row.market_id,
                "market_slug": row.market_slug,
                "associated_asset": row.associated_asset,
                "benchmark_asset": row.benchmark_asset,
                "flag_time_utc": row.flag_time_utc,
                "entry_time_utc": associated_entry["timestamp_utc"],
                "resolution_time_utc": row.resolution_time_utc,
                "associated_asset_return_pct": associated_return,
                "benchmark_return_pct": benchmark_return,
                "excess_return_pct": associated_return - benchmark_return,
            }
        )
    return pd.DataFrame(rows, columns=BACKTEST_COLUMNS)


def main() -> None:
    args = parse_args()
    signals = pd.read_csv(args.signals, dtype={"market_id": "string"})
    registry = pd.read_csv(args.registry, dtype={"market_id": "string"})
    normalized_signals, normalized_registry, _ = normalize_inputs(
        signals, registry, pd.DataFrame(columns=PRICE_COLUMNS)
    )
    joined = normalized_signals.merge(
        normalized_registry,
        on=["market_id", "market_slug"],
        how="left",
        validate="one_to_one",
    )
    assets = joined["associated_asset"].dropna().tolist() + joined["benchmark_asset"].dropna().tolist()
    if not assets:
        raise ValueError("No assets found for flagged markets.")
    start = joined["flag_time_utc"].min() - pd.Timedelta(days=7)
    end = joined["resolution_time_utc"].max() + pd.Timedelta(days=7)
    prices = update_asset_prices(args.asset_prices, assets, start, end)
    results = build_backtest_results(signals, registry, prices)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(args.output, index=False)
    print(f"Wrote {len(results):,} event rows to {args.output}")


if __name__ == "__main__":
    main()
