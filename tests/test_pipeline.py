from __future__ import annotations

from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from build_formula_baseline import compute_baseline_stats
from compute_formula_scores import (
    add_baseline_zscores,
    add_final_suspicion_z,
    apply_final_suspicion_score,
    apply_formula_scores,
    build_hourly_market_frame,
)
from pull_polymarket_orderbooks import hourly_strings, normalize_raw_numeric_columns
from run_backtest import build_backtest_results
from select_market_signals import filter_scores_by_study_group_prefix, select_first_flags
from summarize_study import summarize_results


def test_hourly_aggregation_returns_one_row_per_hour() -> None:
    raw = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2026-01-01T00:05:00Z",
                    "2026-01-01T00:10:00Z",
                    "2026-01-01T01:15:00Z",
                    "2026-01-01T01:20:00Z",
                ]
            ),
            "event_type": ["book", "last_trade_price", "book", "last_trade_price"],
            "bids": [
                '[["0.40","10"]]',
                None,
                '[["0.45","12"]]',
                None,
            ],
            "asks": [
                '[["0.60","20"]]',
                None,
                '[["0.55","18"]]',
                None,
            ],
            "best_bid": [np.nan, 0.40, np.nan, 0.45],
            "best_ask": [np.nan, 0.60, np.nan, 0.55],
            "price": [np.nan, 0.50, np.nan, 0.52],
            "size": [np.nan, 5.0, np.nan, 7.0],
        }
    )

    hourly = build_hourly_market_frame(raw)

    assert list(hourly["timestamp_utc"]) == list(
        pd.to_datetime(["2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z"])
    )
    assert hourly.loc[0, "hourly_trade_volume"] == 5.0
    assert hourly.loc[1, "touch_depth"] == 30.0


def test_hour_string_range_is_inclusive() -> None:
    assert list(hourly_strings("2026-01-01T00", "2026-01-01T02")) == [
        "2026-01-01T00",
        "2026-01-01T01",
        "2026-01-01T02",
    ]


def test_raw_numeric_columns_are_normalized_before_parquet_write() -> None:
    raw = pd.DataFrame(
        {
            "price": [Decimal("0.10"), 0.20],
            "size": [Decimal("1.50"), 2.0],
            "best_bid": [Decimal("0.09"), 0.19],
            "best_ask": [Decimal("0.11"), 0.21],
        }
    )

    normalized = normalize_raw_numeric_columns(raw)

    for column in ["price", "size", "best_bid", "best_ask"]:
        assert pd.api.types.is_numeric_dtype(normalized[column])


def test_formula_weights_match_project_plan() -> None:
    zscored = pd.DataFrame(
        {
            "z_abs_initial_move": [1.0],
            "z_log_trade_notional": [2.0],
            "z_clipped_retention_ratio_6h": [3.0],
            "z_log_touch_depth_over_trade_volume": [4.0],
            "z_relative_spread": [5.0],
            "z_log_price_impact_per_dollar": [6.0],
            "z_log_noise_ratio_6h": [7.0],
        }
    )

    scored = apply_formula_scores(zscored)

    assert scored.loc[0, "sustained_shock_score"] == pytest.approx(1.9)
    assert scored.loc[0, "fragile_repricing_score"] == pytest.approx(0.65)
    assert scored.loc[0, "spread_stress_score"] == pytest.approx(2.45)
    assert scored.loc[0, "impact_accepted_score"] == pytest.approx(2.65)
    assert scored.loc[0, "anti_noise_score"] == pytest.approx(0.55)


def test_final_suspicion_score_uses_quality_weighted_average() -> None:
    scored = pd.DataFrame(
        {
            "abs_initial_move": [0.10],
            "hourly_trade_notional": [1000.0],
            "clipped_retention_ratio_6h": [0.5],
            "sustained_shock_score": [1.0],
            "fragile_repricing_score": [2.0],
            "spread_stress_score": [3.0],
            "impact_accepted_score": [4.0],
            "anti_noise_score": [5.0],
        }
    )

    final = apply_final_suspicion_score(scored)

    assert final.loc[0, "quality_weight"] == pytest.approx(0.125)
    assert final.loc[0, "final_suspicion_score"] == pytest.approx(0.375)


def test_final_suspicion_z_uses_external_baseline_stats() -> None:
    scored = pd.DataFrame({"final_suspicion_score": [0.75]})
    baseline_stats = pd.DataFrame(
        {
            "feature": ["final_suspicion_score"],
            "mean": [0.25],
            "std": [0.25],
        }
    )

    final = add_final_suspicion_z(scored, baseline_stats)

    assert final.loc[0, "final_suspicion_z"] == pytest.approx(2.0)


def test_baseline_stats_capture_feature_mean_and_std() -> None:
    feature_rows = pd.DataFrame(
        {
            "market_id": ["a", "a", "b", "b"],
            "abs_initial_move": [1.0, 3.0, 5.0, 9.0],
            "log_trade_notional": [2.0, 4.0, 6.0, 10.0],
            "log_touch_depth_over_trade_volume": [3.0, 5.0, 7.0, 11.0],
            "relative_spread": [4.0, 6.0, 8.0, 12.0],
            "log_price_impact_per_dollar": [5.0, 7.0, 9.0, 13.0],
            "clipped_retention_ratio_6h": [6.0, 8.0, 10.0, 14.0],
            "log_noise_ratio_6h": [7.0, 9.0, 11.0, 15.0],
        }
    )

    stats = compute_baseline_stats(feature_rows).set_index("feature")

    assert stats.loc["abs_initial_move", "mean"] == pytest.approx(4.5)
    assert stats.loc["abs_initial_move", "std"] == pytest.approx(1.5)
    assert stats.loc["abs_initial_move", "n_markets_mean"] == 2
    assert stats.loc["abs_initial_move", "n_markets_std"] == 2
    assert stats.loc["abs_initial_move", "n_hourly_rows"] == 4


def test_zscores_use_external_baseline_stats() -> None:
    features = pd.DataFrame(
        {
            "abs_initial_move": [11.0],
            "log_trade_notional": [12.0],
            "log_touch_depth_over_trade_volume": [13.0],
            "relative_spread": [14.0],
            "log_price_impact_per_dollar": [15.0],
            "clipped_retention_ratio_6h": [16.0],
            "log_noise_ratio_6h": [17.0],
        }
    )
    baseline_stats = pd.DataFrame(
        {
            "feature": [
                "abs_initial_move",
                "log_trade_notional",
                "log_touch_depth_over_trade_volume",
                "relative_spread",
                "log_price_impact_per_dollar",
                "clipped_retention_ratio_6h",
                "log_noise_ratio_6h",
            ],
            "mean": [1.0] * 7,
            "std": [2.0] * 7,
        }
    )

    zscored = add_baseline_zscores(features, baseline_stats)

    assert zscored.loc[0, "z_abs_initial_move"] == pytest.approx(5.0)
    assert zscored.loc[0, "z_log_trade_notional"] == pytest.approx(5.5)
    assert zscored.loc[0, "z_log_noise_ratio_6h"] == pytest.approx(8.0)


def test_signal_selection_keeps_first_flag_per_market() -> None:
    scores = pd.DataFrame(
        {
            "market_id": ["1", "1", "2"],
            "market_slug": ["a", "a", "b"],
            "timestamp_utc": pd.to_datetime(
                [
                    "2026-01-01T01:00:00Z",
                    "2026-01-01T03:00:00Z",
                    "2026-01-01T02:00:00Z",
                ]
            ),
            "sustained_shock_score": [2.1, 3.0, 2.5],
        }
    )

    selected = select_first_flags(scores, "sustained_shock_score", threshold=2.0)

    assert len(selected) == 2
    assert selected.loc[selected["market_id"].eq("1"), "flag_time_utc"].iloc[0] == pd.Timestamp(
        "2026-01-01T01:00:00Z"
    )


def test_signal_filter_keeps_only_requested_study_group_prefix() -> None:
    scores = pd.DataFrame(
        {
            "market_id": ["1", "2", "3"],
            "market_slug": ["proof", "primary", "reserve"],
            "timestamp_utc": pd.to_datetime(
                [
                    "2026-01-01T01:00:00Z",
                    "2026-01-01T02:00:00Z",
                    "2026-01-01T03:00:00Z",
                ]
            ),
            "final_suspicion_z": [3.0, 3.0, 3.0],
        }
    )
    registry = pd.DataFrame(
        {
            "market_id": ["1", "2", "3"],
            "market_slug": ["proof", "primary", "reserve"],
            "study_group": [
                "proof_of_concept_positive",
                "final_study_primary",
                "final_study_reserve",
            ],
        }
    )

    filtered = filter_scores_by_study_group_prefix(scores, registry, "final_study")

    assert list(filtered["market_slug"]) == ["primary", "reserve"]


def test_backtest_uses_one_event_row_and_excess_return() -> None:
    signals = pd.DataFrame(
        {
            "market_id": ["1"],
            "market_slug": ["event-a"],
            "flag_time_utc": ["2026-01-01T12:00:00Z"],
        }
    )
    registry = pd.DataFrame(
        {
            "market_id": ["1"],
            "market_slug": ["event-a"],
            "associated_asset": ["AAA"],
            "benchmark_asset": ["SPY"],
            "resolution_time_utc": ["2026-01-03T23:00:00Z"],
        }
    )
    prices = pd.DataFrame(
        {
            "asset": ["AAA", "AAA", "SPY", "SPY"],
            "timestamp_utc": pd.to_datetime(
                [
                    "2026-01-02T00:00:00Z",
                    "2026-01-03T00:00:00Z",
                    "2026-01-02T00:00:00Z",
                    "2026-01-03T00:00:00Z",
                ]
            ),
            "close": [100.0, 110.0, 100.0, 105.0],
        }
    )

    results = build_backtest_results(signals, registry, prices)

    assert len(results) == 1
    assert results.loc[0, "associated_asset_return_pct"] == pytest.approx(10.0)
    assert results.loc[0, "benchmark_return_pct"] == pytest.approx(5.0)
    assert results.loc[0, "excess_return_pct"] == pytest.approx(5.0)


def test_backtest_uses_first_shared_entry_timestamp() -> None:
    signals = pd.DataFrame(
        {
            "market_id": ["1"],
            "market_slug": ["event-a"],
            "flag_time_utc": ["2026-01-01T12:00:00Z"],
        }
    )
    registry = pd.DataFrame(
        {
            "market_id": ["1"],
            "market_slug": ["event-a"],
            "associated_asset": ["BTC-USD"],
            "benchmark_asset": ["SPY"],
            "resolution_time_utc": ["2026-01-01T16:00:00Z"],
        }
    )
    prices = pd.DataFrame(
        {
            "asset": ["BTC-USD", "BTC-USD", "BTC-USD", "SPY", "SPY"],
            "timestamp_utc": pd.to_datetime(
                [
                    "2026-01-01T12:30:00Z",
                    "2026-01-01T13:30:00Z",
                    "2026-01-01T15:30:00Z",
                    "2026-01-01T13:30:00Z",
                    "2026-01-01T15:30:00Z",
                ]
            ),
            "close": [100.0, 101.0, 110.0, 100.0, 105.0],
        }
    )

    results = build_backtest_results(signals, registry, prices)

    assert results.loc[0, "entry_time_utc"] == pd.Timestamp("2026-01-01T13:30:00Z")
    assert results.loc[0, "associated_asset_return_pct"] == pytest.approx(
        (110.0 / 101.0 - 1.0) * 100.0
    )
    assert results.loc[0, "benchmark_return_pct"] == pytest.approx(5.0)


def test_summary_uses_ten_event_level_excess_returns() -> None:
    returns = pd.DataFrame({"excess_return_pct": [1, 2, 3, 4, 5, 1, 2, 3, 4, 5]})

    summary = summarize_results(returns, bootstrap_samples=1_000, seed=0)

    assert summary.loc[0, "n_markets"] == 10
    assert summary.loc[0, "mean_excess_return_pct"] == 3.0
    assert summary.loc[0, "median_excess_return_pct"] == 3.0
    assert summary.loc[0, "win_rate"] == 1.0
    assert 0.0 <= summary.loc[0, "p_value_one_sided"] <= 1.0
