# Project Instructions

## Project Goal

Build a reproducible research pipeline that:

1. Reconstructs historical Polymarket order books for resolved markets.
2. Runs only the approved informed-trading formulas on hourly data.
3. Demonstrates proof of concept by flagging the clavicular-pregnancy market while not flagging a past major-league sports match market.
4. Extends the study to 10 resolved Polymarket events with clearly associated real-world tradable assets.
5. Backtests whether trading those associated assets after a Polymarket flag outperforms a broad benchmark investment.

The project is about testing whether flagged Polymarket events can generate alpha in real financial markets. It is not about maximizing the number of experimental features or producing speculative probability claims.

## Source Of Truth

- Read [PROJECT_PLAN.md](/Users/farisalmouslli/Downloads/clavicular-pregnancy-in-2026-dataset/PROJECT_PLAN.md) before making substantial changes.
- Treat the current approved formula list in `PROJECT_PLAN.md` as the source of truth.
- Do not add formulas, columns, flag tiers, or side analyses unless the user explicitly asks for them.
- Historical exploratory scripts and CSVs already in the repo may be useful references, but they are not automatically part of the final pipeline.

## Core Research Rules

- Use only historical resolved-market data for the study.
- For the negative comparison market, use a past major-league sports game. Do not use live game data.
- Use the clavicular-pregnancy market as the initial positive proof-of-concept example.
- Once the final formula and flag threshold are chosen for the 10-market backtest, freeze them before evaluating those 10 markets.
- A market is flagged when the approved final score crosses the fixed threshold:

```text
final_score >= 2.0
```

- For the final backtest, use one trade per Polymarket event:
  - enter on the first qualifying flag,
  - hold until the Polymarket resolution time,
  - produce one result row per event.
- Do not treat z-scores or score percentiles as probabilities of informed trading unless a separate calibrated probability model is built and validated.
- The p-value and confidence interval belong to the backtest-performance question, not to the market-flagging question.

## Approved V1 Formula Set

Implement only the approved rich formulas listed in `PROJECT_PLAN.md`:

1. `sustained_shock_score`
2. `fragile_repricing_score`
3. `spread_stress_score`
4. `impact_accepted_score`
5. `anti_noise_score`

Do not emit random intermediate equations or unsupported extra metrics in the final formula output. Each approved equation should be its own column.

## Data Layout Principles

Use separate raw files per market when that is natural, and consolidated research tables for study outputs.

Recommended layout:

```text
data/
  raw_orderbooks/
    one parquet file per market
  market_registry.csv

outputs/
  formula_scores.csv
  market_signal_results.csv
  backtest_results.csv
  study_summary.csv
```

### Raw Data

- Raw order-book data may remain one parquet file per market.
- Prefer parquet for raw market history because the data can be large and may include nested order-book fields.

### Consolidated Output Tables

- Do not create one final CSV per market unless the user explicitly requests it.
- Use shared CSVs that accumulate rows across markets.
- Keep output schemas lean. Retain only fields needed for:
  1. approved formulas,
  2. trade decisions,
  3. final statistical testing,
  4. minimal traceability.

## Final Output Discipline

### Hourly Formula Output

The official formula-score table should have:

- one row per market per hour,
- one column per approved equation,
- only the fields required to calculate or interpret those equations.

### Final Backtest Output

The final event-level backtest table should be intentionally small:

```text
market_id
market_slug
associated_asset
benchmark_asset
flag_time_utc
entry_time_utc
resolution_time_utc
associated_asset_return_pct
benchmark_return_pct
excess_return_pct
```

Do not add:

- duplicate exit-time fields when `resolution_time_utc` already defines exit,
- score columns when presence in the table already means the market was flagged,
- profit-dollar columns unless the user later asks for them,
- extra metadata that is not used downstream.

The only return variable used in the final statistical test is:

```text
excess_return_pct =
    associated_asset_return_pct
  - benchmark_return_pct
```

## Benchmark And Backtest Rules

- Use `SPY` as the default broad-market comparison investment for the primary study.
- For each flagged event, simulate:
  - `$100` in the associated asset,
  - `$100` in `SPY`,
  - both entered at the same backtest entry time,
  - both held until the Polymarket resolution time.
- The primary study tests whether the associated-asset trade outperforms `SPY`.
- Sector-specific benchmark checks may be added later as robustness tests only if requested.

## Implementation Guidance

- The official V1 pipeline has exactly five scripts:

```text
pull_polymarket_orderbooks.py
compute_formula_scores.py
select_market_signals.py
run_backtest.py
summarize_study.py
```

- Do not create additional pipeline scripts unless the user explicitly asks for them.
- The user has explicitly approved one separate support script for baseline construction:

```text
build_formula_baseline.py
```

- Keep `build_formula_baseline.py` outside the official five-step study pipeline. Its job is only to build the broad historical baseline mean and standard deviation used by the approved formula z-scores.
- The user has also approved one operational helper for pulling the raw files named by the baseline registry:

```text
pull_baseline_orderbooks.py
```

- Keep `pull_baseline_orderbooks.py` outside the official five-step study pipeline as well. It only automates repeated calls to the raw-orderbook puller for the approved baseline set.
- In V1, `run_backtest.py` is responsible for fetching or updating the shared `data/asset_prices.csv` file as part of the backtest workflow. Do not split that into a separate asset-price script unless the user later requests it.
- Prefer small, explicit Python scripts with clear CLI arguments.
- Use `pandas`, `numpy`, `pyarrow`, and `scipy` where appropriate.
- Prefer structured parsing over ad hoc string manipulation.
- Keep formulas readable and named exactly as in the project plan.
- Use safe math:
  - sort timestamps before lag/lead calculations,
  - avoid divide-by-zero,
  - leave unavailable warmup/future rows blank where required,
  - log-transform heavy-tailed variables where specified,
  - clip retention ratios only where the approved formula says to clip them.
- Add tests in proportion to risk:
  - formula correctness,
  - one-row-per-hour aggregation,
  - one-trade-per-event behavior,
  - excess-return calculation,
  - final statistics over the 10 event rows.

## Statistical Interpretation Rules

- The final hypothesis test is:

```text
H0: mean(excess_return_pct) = 0
H1: mean(excess_return_pct) > 0
```

- Use 10 flagged event-level `excess_return_pct` values for the final study.
- Report:
  - number of markets,
  - mean excess return,
  - median excess return,
  - win rate,
  - one-sided p-value,
  - 95% confidence interval for mean excess return.
- Prefer reporting both:
  - a one-sample t-test,
  - a bootstrap confidence interval,
  because 10 events is a small sample.

## Working Style For Agents

- Be conservative with scope.
- Reuse existing repo patterns when they are useful, but do not inherit exploratory clutter into the final pipeline.
- When in doubt, ask whether a field or formula will actually be used later. If not, leave it out.
- Keep explanations practical and easy to audit.
- If data availability breaks the planned design, surface that early rather than silently swapping in lower-quality substitutes.
