#!/usr/bin/env python3
"""Pull filtered historical Polymarket order-book rows into one market parquet."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Iterable

import duckdb
import pandas as pd


BASE_URL = "https://r2v2.pmxt.dev/polymarket_orderbook_{}.parquet"
REQUIRED_RAW_COLUMNS = {
    "timestamp",
    "event_type",
    "asset_id",
    "bids",
    "asks",
    "price",
    "size",
    "best_bid",
    "best_ask",
}
RAW_NUMERIC_COLUMNS = ["price", "size", "best_bid", "best_ask"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pull historical Polymarket order-book rows for one market."
    )
    parser.add_argument("--market-slug", required=True)
    parser.add_argument(
        "--asset-ids",
        required=True,
        help="Comma-separated token ids to retain from the historical source.",
    )
    parser.add_argument("--start", required=True, help="Inclusive UTC hour: YYYY-MM-DDTHH")
    parser.add_argument("--end", required=True, help="Inclusive UTC hour: YYYY-MM-DDTHH")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/raw_orderbooks"),
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path("data/raw_orderbooks/_hourly"),
    )
    parser.add_argument(
        "--chunk-hours",
        type=int,
        default=4,
        help="Number of consecutive archive hours to fetch in one DuckDB query.",
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def hourly_strings(start: str, end: str) -> Iterable[str]:
    start_dt = dt.datetime.strptime(start, "%Y-%m-%dT%H")
    end_dt = dt.datetime.strptime(end, "%Y-%m-%dT%H")
    if end_dt < start_dt:
        raise ValueError("--end must be greater than or equal to --start.")
    current = start_dt
    while current <= end_dt:
        yield current.strftime("%Y-%m-%dT%H")
        current += dt.timedelta(hours=1)


def parse_asset_ids(raw: str) -> list[str]:
    asset_ids = [value.strip() for value in raw.split(",") if value.strip()]
    if not asset_ids:
        raise ValueError("--asset-ids must contain at least one token id.")
    return asset_ids


def fetch_filtered_rows(
    conn: duckdb.DuckDBPyConnection,
    timestamp_hour: str,
    asset_ids: list[str],
) -> pd.DataFrame:
    placeholders = ", ".join(["?"] * len(asset_ids))
    url = BASE_URL.format(timestamp_hour)
    query = (
        f"SELECT * FROM read_parquet('{url}') "
        f"WHERE asset_id IN ({placeholders})"
    )
    try:
        return conn.execute(query, asset_ids).fetch_df()
    except duckdb.Error as exc:
        print(f"warning: unreadable or unavailable archive hour {timestamp_hour}: {exc}")
        return pd.DataFrame()


def validate_raw_schema(df: pd.DataFrame) -> None:
    missing = sorted(REQUIRED_RAW_COLUMNS - set(df.columns))
    if missing:
        raise ValueError(f"Historical source is missing required columns: {', '.join(missing)}")


def normalize_raw_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for column in RAW_NUMERIC_COLUMNS:
        if column in out.columns:
            out[column] = pd.to_numeric(out[column], errors="coerce")
    return out


def pull_market_rows(
    market_slug: str,
    asset_ids: list[str],
    start: str,
    end: str,
    work_dir: Path,
    overwrite: bool,
    chunk_hours: int,
) -> pd.DataFrame:
    if chunk_hours < 1:
        raise ValueError("--chunk-hours must be at least 1.")

    conn = duckdb.connect()
    hours = list(hourly_strings(start, end))
    hourly_dir = work_dir / market_slug
    hourly_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = hourly_dir / "_completed_hours.json"
    if checkpoint_path.exists() and not overwrite:
        completed_hours = set(json.loads(checkpoint_path.read_text()))
    else:
        completed_hours = set()

    pending_hours: list[str] = []
    for index, timestamp_hour in enumerate(hours, start=1):
        hourly_path = hourly_dir / f"{timestamp_hour}.parquet"
        if timestamp_hour in completed_hours and hourly_path.exists() and not overwrite:
            print(f"[{index}/{len(hours)}] skip {timestamp_hour}")
            continue
        pending_hours.append(timestamp_hour)

    for start_index in range(0, len(pending_hours), chunk_hours):
        timestamp_hours = pending_hours[start_index : start_index + chunk_hours]
        for timestamp_hour in timestamp_hours:
            hourly_path = hourly_dir / f"{timestamp_hour}.parquet"
            url = BASE_URL.format(timestamp_hour)
            escaped_path = str(hourly_path).replace("'", "''")
            placeholders = ", ".join(["?"] * len(asset_ids))
            query = (
                "COPY ("
                f"SELECT * FROM read_parquet('{url}') "
                f"WHERE asset_id IN ({placeholders})"
                f") TO '{escaped_path}' (FORMAT PARQUET)"
            )
            try:
                conn.execute(query, asset_ids)
            except duckdb.Error:
                rows = fetch_filtered_rows(conn, timestamp_hour, asset_ids)
                if not rows.empty:
                    validate_raw_schema(rows)
                rows.to_parquet(hourly_path, index=False)
            completed_hours.add(timestamp_hour)
        checkpoint_path.write_text(json.dumps(sorted(completed_hours)))
        print(
            f"[{len(completed_hours)}/{len(hours)}] wrote "
            f"{timestamp_hours[0]}..{timestamp_hours[-1]}"
        )

    hourly_paths = [hourly_dir / f"{timestamp_hour}.parquet" for timestamp_hour in hours]
    frames = [pd.read_parquet(path) for path in hourly_paths if path.exists()]
    nonempty_frames = [frame for frame in frames if not frame.empty]
    if not nonempty_frames:
        raise ValueError(f"No rows recovered for market_slug={market_slug}.")

    combined = pd.concat(nonempty_frames, ignore_index=True)
    combined["timestamp"] = pd.to_datetime(combined["timestamp"], utc=True, errors="coerce")
    combined = normalize_raw_numeric_columns(combined)
    combined = combined.dropna(subset=["timestamp"]).sort_values("timestamp")
    return combined.reset_index(drop=True)


def write_market_parquet(df: pd.DataFrame, output_path: Path, overwrite: bool) -> None:
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"{output_path} already exists. Pass --overwrite to replace it.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)


def main() -> None:
    args = parse_args()
    asset_ids = parse_asset_ids(args.asset_ids)
    rows = pull_market_rows(
        args.market_slug,
        asset_ids,
        args.start,
        args.end,
        args.work_dir,
        args.overwrite,
        args.chunk_hours,
    )
    output_path = args.output_dir / f"{args.market_slug}.parquet"
    write_market_parquet(rows, output_path, args.overwrite)
    print(f"Wrote {len(rows):,} rows to {output_path}")


if __name__ == "__main__":
    main()
