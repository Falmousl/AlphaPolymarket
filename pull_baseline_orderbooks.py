#!/usr/bin/env python3
"""Pull raw historical order books for the approved 100-market baseline registry."""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import duckdb
import pandas as pd

from pull_polymarket_orderbooks import (
    BASE_URL,
    fetch_filtered_rows,
    hourly_strings,
    validate_raw_schema,
)


ARCHIVE_START_UTC = pd.Timestamp("2026-04-20T22:00:00Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pull all baseline-market order books.")
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path("data/baseline_market_registry.csv"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/raw_orderbooks"),
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path("data/raw_orderbooks/_baseline_hours"),
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of archive chunks to fetch concurrently.",
    )
    parser.add_argument(
        "--chunk-hours",
        type=int,
        default=12,
        help="Number of consecutive archive hours to fetch in one DuckDB query.",
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def hour_string(timestamp: pd.Timestamp) -> str:
    return timestamp.floor("h").strftime("%Y-%m-%dT%H")


def active_registry(registry: pd.DataFrame) -> pd.DataFrame:
    out = registry.copy()
    out["start_time_utc"] = pd.to_datetime(out["start_time_utc"], utc=True)
    out["resolution_time_utc"] = pd.to_datetime(out["resolution_time_utc"], utc=True)
    out["effective_start_utc"] = out["start_time_utc"].clip(lower=ARCHIVE_START_UTC)
    return out[out["resolution_time_utc"] >= ARCHIVE_START_UTC].copy()


def write_hour_cache(
    registry: pd.DataFrame,
    work_dir: Path,
    overwrite: bool,
    workers: int,
    chunk_hours: int,
) -> list[Path]:
    if workers < 1:
        raise ValueError("--workers must be at least 1.")
    if chunk_hours < 1:
        raise ValueError("--chunk-hours must be at least 1.")

    work_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = work_dir / "_completed_hours.json"
    if checkpoint_path.exists() and not overwrite:
        completed_hours = set(json.loads(checkpoint_path.read_text()))
    else:
        completed_hours = set()

    start = registry["effective_start_utc"].min()
    end = registry["resolution_time_utc"].max()
    hours = list(hourly_strings(hour_string(start), hour_string(end)))
    all_asset_ids = registry["yes_token_id"].astype(str).tolist()

    pending_hours: list[str] = []
    for index, timestamp_hour in enumerate(hours, start=1):
        hourly_path = work_dir / f"{timestamp_hour}.parquet"
        if timestamp_hour in completed_hours and hourly_path.exists() and not overwrite:
            print(f"[{index}/{len(hours)}] skip {timestamp_hour}")
            continue
        pending_hours.append(timestamp_hour)

    pending_chunks = [
        pending_hours[start : start + chunk_hours]
        for start in range(0, len(pending_hours), chunk_hours)
    ]

    def fetch_one_chunk(timestamp_hours: list[str]) -> list[str]:
        conn = duckdb.connect()
        urls = ", ".join(repr(BASE_URL.format(timestamp_hour)) for timestamp_hour in timestamp_hours)
        placeholders = ", ".join(["?"] * len(all_asset_ids))
        query = f"SELECT * FROM read_parquet([{urls}]) WHERE asset_id IN ({placeholders})"
        try:
            rows = conn.execute(query, all_asset_ids).fetch_df()
        except duckdb.Error:
            frames = [
                fetch_filtered_rows(conn, timestamp_hour, all_asset_ids)
                for timestamp_hour in timestamp_hours
            ]
            rows = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        finally:
            conn.close()

        if not rows.empty:
            validate_raw_schema(rows)
            rows["timestamp"] = pd.to_datetime(rows["timestamp"], utc=True, errors="coerce")
            rows = rows.dropna(subset=["timestamp"])
            rows["_timestamp_hour"] = rows["timestamp"].dt.strftime("%Y-%m-%dT%H")

        for timestamp_hour in timestamp_hours:
            if rows.empty:
                hourly_rows = rows.copy()
            else:
                hourly_rows = rows[rows["_timestamp_hour"].eq(timestamp_hour)].drop(
                    columns="_timestamp_hour"
                )
            hourly_path = work_dir / f"{timestamp_hour}.parquet"
            hourly_rows.to_parquet(hourly_path, index=False)
        return timestamp_hours

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(fetch_one_chunk, timestamp_hours): timestamp_hours
            for timestamp_hours in pending_chunks
        }
        finished_count = len(hours) - len(pending_hours)
        for future in as_completed(futures):
            timestamp_hours = future.result()
            finished_count += len(timestamp_hours)
            completed_hours.update(timestamp_hours)
            checkpoint_path.write_text(json.dumps(sorted(completed_hours)))
            print(
                f"[{finished_count}/{len(hours)}] wrote "
                f"{timestamp_hours[0]}..{timestamp_hours[-1]}"
            )

    return [work_dir / f"{timestamp_hour}.parquet" for timestamp_hour in hours]


def materialize_market_files(
    registry: pd.DataFrame,
    hourly_paths: list[Path],
    output_dir: Path,
    overwrite: bool,
) -> None:
    existing_paths = [path for path in hourly_paths if path.exists()]
    if not existing_paths:
        raise ValueError("No baseline hourly cache files were found.")

    conn = duckdb.connect()
    hourly_literal = ", ".join(repr(str(path)) for path in existing_paths)
    source_sql = f"read_parquet([{hourly_literal}], union_by_name=true)"

    for index, row in enumerate(registry.itertuples(index=False), start=1):
        output_path = output_dir / f"{row.market_slug}.parquet"
        if output_path.exists() and not overwrite:
            print(f"[{index}/{len(registry)}] skip existing {output_path}")
            continue

        row_count = conn.execute(
            (
                f"SELECT COUNT(*) FROM {source_sql} "
                "WHERE CAST(asset_id AS VARCHAR) = ? "
                "AND timestamp BETWEEN ? AND ?"
            ),
            [str(row.yes_token_id), row.effective_start_utc, row.resolution_time_utc],
        ).fetchone()[0]
        if row_count == 0:
            print(f"[{index}/{len(registry)}] no rows {row.market_slug}")
            continue

        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.exists() and overwrite:
            output_path.unlink()
        escaped_output = str(output_path).replace("'", "''")
        conn.execute(
            (
                "COPY ("
                f"SELECT * FROM {source_sql} "
                "WHERE CAST(asset_id AS VARCHAR) = ? "
                "AND timestamp BETWEEN ? AND ? "
                "ORDER BY timestamp"
                f") TO '{escaped_output}' (FORMAT PARQUET)"
            ),
            [str(row.yes_token_id), row.effective_start_utc, row.resolution_time_utc],
        )
        print(f"[{index}/{len(registry)}] wrote {row_count:,} rows to {output_path}")

    conn.close()


def main() -> None:
    args = parse_args()
    registry = pd.read_csv(args.registry, dtype={"market_id": "string", "yes_token_id": "string"})
    registry = active_registry(registry)
    hourly_paths = write_hour_cache(
        registry,
        args.work_dir,
        args.overwrite,
        args.workers,
        args.chunk_hours,
    )
    materialize_market_files(registry, hourly_paths, args.output_dir, args.overwrite)


if __name__ == "__main__":
    main()
