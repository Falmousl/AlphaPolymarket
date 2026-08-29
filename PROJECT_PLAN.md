# Polymarket Informed-Trading Project Plan

## 1. Research Question

The project asks:

```text
Do Polymarket markets that show signs of informed trading generate actionable alpha in related real-world financial assets?
```

There are two linked but separate tasks:

1. Detect suspicious or informed-looking behavior inside Polymarket markets.
2. Test whether acting on those signals improves real-asset investment returns versus a broad benchmark.

The first task produces a signal. The second task tests whether that signal is economically useful.

## 2. Final Study Design

### 2.1 Proof Of Concept

Use two resolved historical Polymarkets:

1. **Positive example:** the clavicular-pregnancy market.
2. **Negative comparison example:** a **past** major-league sports match market.

The proof of concept succeeds if the approved formulas flag suspicious behavior in the clavicular market while not flagging the past major-league sports market.

Important constraint:

- Do not use live sports data for the proof of concept.
- Both markets should be reconstructed from historical order-book data using:
  - `https://github.com/YazRaso/polymarket_historical_orderbook_reconstruction`

Before building the full pipeline, verify that this historical-orderbook source can actually recover the chosen markets with the fields needed for the formulas.

### 2.2 Ten-Market Backtest

After the proof of concept is working:

1. Build a pool of eligible resolved Polymarkets with clearly associated real-world tradable assets.
2. Pull historical order-book data for the eligible pool.
3. Run the fixed scoring script using the frozen formula and threshold.
4. Take 10 independent events that actually pass the fixed flag rule.
5. Use the first qualifying flag in each selected market as the trade trigger.
6. Simulate a real-asset investment and a benchmark investment.
7. Compare returns across those 10 flagged markets.

The 10-market study is the actual test of whether the signal creates alpha.

## 3. Candidate Markets For The 10-Event Study

These are the preferred candidate types because the asset mapping is economically clear.

| Event Type | Example Associated Asset | Reason |
|---|---|---|
| Iran war / Strait of Hormuz escalation | `USO` | Direct oil-price exposure |
| OPEC production-cut decision | `USO` | Direct oil-price exposure |
| Fed rate-cut decision | `TLT` | Long-term Treasury prices respond to rate expectations |
| CPI inflation threshold | `TLT` | Inflation surprises affect rate expectations |
| Bitcoin ETF approval | `IBIT` or `BTC-USD` | Direct bitcoin exposure |
| Ethereum ETF approval | `ETH-USD` | Direct ether exposure |
| Nvidia earnings / revenue threshold | `NVDA` | Direct company-specific exposure |
| Tesla deliveries / earnings threshold | `TSLA` | Direct company-specific exposure |
| FDA approval for a public biotech company | issuer stock | Direct company-specific exposure |
| Broad recession / hard-landing event | `SPY` or `TLT` | Macro-market exposure |

### 3.1 Predeclared Primary List

Before evaluating fixed-rule flags, use the following 10 ordered primary event slots:

1. Iran escalation market -> `USO`
2. Strait of Hormuz closure market -> `USO`
3. OPEC production-cut market -> `USO`
4. Fed rate-cut market -> `TLT`
5. CPI threshold market -> `TLT`
6. Bitcoin ETF approval market -> `IBIT` or `BTC-USD`
7. Ethereum ETF approval market -> `ETH-USD`
8. Nvidia event market -> `NVDA`
9. Tesla event market -> `TSLA`
10. FDA approval market for a public biotech company -> issuer stock

### 3.2 Ordered Reserve List

Before evaluating fixed-rule flags, use the following 10 ordered reserve event slots:

1. Additional Iran escalation market -> `USO`
2. Additional Strait of Hormuz disruption market -> `USO`
3. Additional OPEC production-policy market -> `USO`
4. Additional Fed policy market -> `TLT`
5. Additional CPI inflation-threshold market -> `TLT`
6. Additional bitcoin ETF / bitcoin regulatory market -> `IBIT` or `BTC-USD`
7. Additional Ethereum ETF / ether regulatory market -> `ETH-USD`
8. Additional Nvidia earnings or revenue market -> `NVDA`
9. Additional Tesla deliveries or earnings market -> `TSLA`
10. Additional FDA approval market for a public biotech company -> issuer stock

These are predeclared event slots, not yet approved exact market IDs. An exact Polymarket becomes eligible only after it passes the inclusion checklist below and can be reconstructed from the historical-order-book source.

### 3.3 Market Inclusion Checklist

A candidate market is eligible only if all are true:

- resolved historical Polymarket,
- reconstructable order-book history,
- clear YES/NO outcome,
- enough historical coverage for the scoring period,
- associated asset has accessible historical market data,
- association between Polymarket event and asset is economically defensible,
- no need to use live data.

When one Polymarket event contains multiple eligible YES/NO child markets, choose the highest-volume eligible child market before evaluating formula scores. Do not choose the child market after seeing whether it flags. Exact study lists must contain unique event IDs so the final sample can preserve one trade per independent Polymarket event.

For the formal hypothesis test, the final sample must contain 10 **flagged** events, because the investment strategy is only activated after a flag.

### 3.4 Predeclared Replacement Rule

Use the 10 primary slots first. Move down the ordered reserve list only when a primary slot fails an objective inclusion requirement:

1. no reconstructable historical order-book history,
2. no clear YES/NO outcome,
3. insufficient scoring coverage,
4. no defensible associated-asset mapping,
5. no accessible historical associated-asset data,
6. no fixed-rule flag under the already-frozen threshold `final_suspicion_z >= 2.0`.

Do not rank or replace markets using realized asset returns, p-values, effect sizes, or how "interesting" the final result looks. If the 10 primary slots plus the 10 reserve slots still do not produce 10 qualifying flagged events, expand the eligible pool prospectively and document the next ordered reserve slots before evaluating them rather than weakening the rule after seeing the data.

### 3.5 Archive-Window Availability Audit

The historical order-book source currently available to this project begins at:

```text
2026-04-20 22:00:00 UTC
```

Before scoring any final-study markets, the initial slot audit found:

| Original Slot | Archive-Window Status |
|---|---|
| Iran escalation | no eligible resolved market found |
| Strait of Hormuz closure | no exact closure market found; one eligible resolved Hormuz-disruption market found |
| OPEC production cut | no eligible resolved market found |
| Fed rate cut | eligible resolved market found |
| CPI threshold | eligible resolved market found |
| Bitcoin ETF approval | no eligible resolved YES/NO market found |
| Ethereum ETF approval | no eligible resolved YES/NO market found |
| Nvidia event | eligible resolved market found |
| Tesla event | eligible resolved market found |
| FDA approval for a public biotech company | eligible resolved market found |

Because several preferred slots are unavailable inside the recoverable archive window, use the prospective archive-constrained exact lists below before evaluating final-study flags.

### 3.6 Archive-Constrained Exact Primary List

| Order | Event ID | Market ID | Market Slug | Associated Asset |
|---|---:|---:|---|---|
| 1 | `256854` | `1540766` | `strait-of-hormuz-traffic-returns-to-normal-by-april-30` | `USO` |
| 2 | `75478` | `669662` | `will-there-be-no-change-in-fed-interest-rates-after-the-april-2026-meeting` | `TLT` |
| 3 | `364599` | `1937959` | `will-annual-inflation-increase-by-3pt8-in-april` | `TLT` |
| 4 | `397935` | `2029346` | `will-bitcoin-reach-80k-april-20-26` | `BTC-USD` |
| 5 | `397949` | `2029406` | `will-ethereum-reach-2600-april-20-26` | `ETH-USD` |
| 6 | `257196` | `1542697` | `will-nvda-dip-to-168-in-april` | `NVDA` |
| 7 | `358469` | `1921507` | `tsla-quarterly-earnings-nongaap-eps-04-22-2026-0pt39` | `TSLA` |
| 8 | `382921` | `1993856` | `fda-approves-sanofis-sarclisa` | `SNY` |
| 9 | `390017` | `2009421` | `will-wti-reach-100-by-april-20-2026` | `USO` |
| 10 | `387384` | `2003554` | `aapl-quarterly-earnings-gaap-eps-04-30-2026-1pt94` | `AAPL` |

### 3.7 Archive-Constrained Ordered Reserve List

| Order | Event ID | Market ID | Market Slug | Associated Asset |
|---|---:|---:|---|---|
| 1 | `364618` | `1937991` | `will-monthly-inflation-increase-by-0pt6-in-april` | `TLT` |
| 2 | `422394` | `2091247` | `will-bitcoin-reach-84k-april-27-may-3` | `BTC-USD` |
| 3 | `422418` | `2091330` | `will-ethereum-reach-2500-april-27-may-3` | `ETH-USD` |
| 4 | `439120` | `2135067` | `will-nvda-reach-220-by-may-4-2026` | `NVDA` |
| 5 | `257185` | `1542610` | `will-tsla-reach-555-in-april` | `TSLA` |
| 6 | `400481` | `2036554` | `fda-approves-sanofis-dupixent` | `SNY` |
| 7 | `431116` | `2115652` | `fda-approves-argenxs-vyvgart` | `ARGX` |
| 8 | `387361` | `2003531` | `msft-quarterly-earnings-gaap-eps-04-29-2026-4pt05` | `MSFT` |
| 9 | `387362` | `2003532` | `meta-quarterly-earnings-gaap-eps-04-29-2026-6pt62` | `META` |
| 10 | `403287` | `2044093` | `amzn-quarterly-earnings-gaap-eps-04-29-2026-1pt65` | `AMZN` |

### 3.8 Additional Archive-Constrained Ordered Reserve List

If the exact primary plus ordered reserve list does not produce 10 qualifying flagged events, use the following additional ordered reserve events next. These were declared before evaluating their formula scores.

| Order | Event ID | Market ID | Market Slug | Associated Asset |
|---|---:|---:|---|---|
| 11 | `401604` | `2039908` | `mrna-quarterly-earnings-gaap-eps-05-01-2026-neg2pt67` | `MRNA` |
| 12 | `414619` | `2072221` | `will-wti-reach-115-by-april-27-2026` | `USO` |
| 13 | `439138` | `2135315` | `will-wti-dip-to-90-by-may-4-2026` | `USO` |
| 14 | `464369` | `2203271` | `will-wti-reach-105-by-may-11-2026` | `USO` |
| 15 | `389991` | `2009163` | `will-nvda-reach-204-by-april-20-2026` | `NVDA` |
| 16 | `389988` | `2009128` | `will-tsla-dip-to-382-50-by-april-20-2026` | `TSLA` |
| 17 | `400511` | `2036685` | `fda-approves-sanofis-tzield` | `SNY` |
| 18 | `400550` | `2036724` | `fda-approves-astrazenecas-truqap-capivasertib` | `AZN` |
| 19 | `400551` | `2036725` | `fda-approves-astrazenecas-camizestrant` | `AZN` |
| 20 | `305510` | `1807967` | `will-wti-crude-oil-wti-hit-high-200-in-april` | `USO` |

### 3.9 Second Additional Archive-Constrained Ordered Reserve List

The first 30 declared final-study events produced only 7 fixed-rule flags. Before evaluating any additional formula scores, use the following next ordered reserve events. These are direct crypto-price events, so the associated asset is the same underlying spot asset named by the Polymarket event.

During the pre-score inclusion check for this tranche:

- event `467399` kept the same event slot but moved to its highest-volume eligible child market after the initial child lacked usable midpoint or trade-price history,
- two initially considered events were dropped because their available reconstructed histories did not satisfy the scoring-coverage requirement,
- the replacement events below were selected before computing formula scores for this tranche.

| Order | Event ID | Market ID | Market Slug | Associated Asset |
|---|---:|---:|---|---|
| 21 | `467423` | `2214860` | `bitcoin-above-76k-on-may-16` | `BTC-USD` |
| 22 | `467399` | `2214725` | `ethereum-above-2200-on-may-16` | `ETH-USD` |
| 23 | `462407` | `2190024` | `xrp-above-1pt6-on-may-15` | `XRP-USD` |
| 24 | `472488` | `2227069` | `will-bitcoin-dip-to-78k-may-11-17` | `BTC-USD` |
| 25 | `462398` | `2189973` | `will-the-price-of-ethereum-be-between-2400-2500-on-may-15` | `ETH-USD` |
| 26 | `467470` | `2215181` | `xrp-above-1pt3-on-may-16` | `XRP-USD` |
| 27 | `462379` | `2189935` | `ethereum-above-2300-on-may-15` | `ETH-USD` |
| 28 | `438066` | `2132798` | `will-ethereum-dip-to-2200-in-may-2026` | `ETH-USD` |
| 29 | `467450` | `2215035` | `solana-above-80-on-may-16` | `SOL-USD` |
| 30 | `462381` | `2189932` | `will-the-price-of-bitcoin-be-between-80000-82000-on-may-15` | `BTC-USD` |

## 4. Associated Assets And Benchmark

### 4.1 Associated Assets

Use the real-world asset that most directly reflects the Polymarket event.

Examples:

| Asset | Meaning | Best Use |
|---|---|---|
| `USO` | oil-linked exchange-traded product | oil-supply or Iran-war markets |
| `TLT` | long-duration U.S. Treasury ETF | Fed or inflation markets |
| `IBIT` | bitcoin ETF | bitcoin-related markets |
| `BTC-USD` | spot bitcoin price | bitcoin-related markets |
| `ETH-USD` | spot ether price | ether-related markets |
| `NVDA` | Nvidia stock | Nvidia event markets |
| `TSLA` | Tesla stock | Tesla event markets |

Use the most direct asset where possible. For example:

- Iran war -> prefer `USO` over `XLE`
- Bitcoin ETF approval -> prefer `IBIT` or `BTC-USD` over `COIN`

### 4.2 General Comparative Investment

Use `SPY` as the primary benchmark investment.

For each flagged Polymarket event:

```text
$100 into the associated asset
$100 into SPY
```

Both trades:

- begin at the same entry time,
- end at the Polymarket resolution time.

Primary comparison:

```text
excess_return_pct =
    associated_asset_return_pct
  - benchmark_return_pct
```

This tells us whether the Polymarket-based trade beat a broad general-market investment over the same period.

## 5. Formula Set

The final scoring script must implement only the approved rich formulas below. Do not add unsupported equations or extra output columns.

### 5.1 Shared Variables

Use hourly data. For hour `t`:

```text
price_t = market midpoint where available
hourly_trade_notional_t = dollar volume traded in hour t
hourly_trade_volume_t = share volume traded in hour t
top_bid_size_t = size available at best bid
top_ask_size_t = size available at best ask
touch_depth_t = top_bid_size_t + top_ask_size_t
relative_spread_t =
    (best_ask_t - best_bid_t)
    /
    ((best_ask_t + best_bid_t) / 2)
initial_move_t = price_t - price_{t-1}
retained_move_6h_t = price_{t+6h} - price_{t-1}
retention_ratio_6h_t =
    retained_move_6h_t / initial_move_t
```

Use:

```text
clipped_retention_ratio_6h_t =
    clip(retention_ratio_6h_t, -1, 2)
```

when the formula calls for clipped retention.

### 5.2 Formula 1: Sustained Shock Score

```text
sustained_shock_score =
    0.40 * zscore(|price_t - price_{t-1}|)
  + 0.30 * zscore(log(1 + hourly_trade_notional_t))
  + 0.30 * zscore(
        clip(
            (price_{t+6h} - price_{t-1})
            /
            (price_t - price_{t-1}),
            -1,
            2
        )
    )
```

Interpretation:

- rewards a large move,
- rewards meaningful trading,
- rewards the move remaining in place after six hours.

### 5.3 Formula 2: Fragile Repricing Score

```text
fragile_repricing_score =
    0.35 * zscore(|price_t - price_{t-1}|)
  + 0.25 * zscore(log(1 + hourly_trade_notional_t))
  + 0.20 * -zscore(
        log(
            (top_bid_size_t + top_ask_size_t)
            /
            hourly_trade_volume_t
        )
    )
  + 0.20 * zscore(
        clip(
            (price_{t+6h} - price_{t-1})
            /
            (price_t - price_{t-1}),
            -1,
            2
        )
    )
```

Interpretation:

- rewards a large move,
- rewards meaningful volume,
- rewards thin top-of-book liquidity relative to traded volume,
- rewards the new level holding.

### 5.4 Formula 3: Spread-Stress Repricing Score

```text
spread_stress_score =
    0.35 * zscore(|price_t - price_{t-1}|)
  + 0.25 * zscore(log(1 + hourly_trade_notional_t))
  + 0.20 * zscore(
        (best_ask_t - best_bid_t)
        /
        ((best_ask_t + best_bid_t) / 2)
    )
  + 0.20 * zscore(
        clip(
            (price_{t+6h} - price_{t-1})
            /
            (price_t - price_{t-1}),
            -1,
            2
        )
    )
```

Interpretation:

- rewards a large move,
- rewards meaningful volume,
- rewards a wide relative spread,
- rewards persistence of the move.

### 5.5 Formula 4: Price-Impact Accepted Move Score

```text
impact_accepted_score =
    0.35 * zscore(|price_t - price_{t-1}|)
  + 0.25 * zscore(log(1 + hourly_trade_notional_t))
  + 0.20 * zscore(
        log(
            |price_t - price_{t-1}|
            /
            hourly_trade_notional_t
        )
    )
  + 0.20 * zscore(
        clip(
            (price_{t+6h} - price_{t-1})
            /
            (price_t - price_{t-1}),
            -1,
            2
        )
    )
```

Interpretation:

- rewards a large move,
- rewards meaningful volume,
- rewards high price impact per dollar traded,
- rewards the market accepting the new price afterward.

### 5.6 Formula 5: Anti-Noise Score

```text
anti_noise_score =
    0.35 * zscore(|price_t - price_{t-1}|)
  + 0.25 * zscore(log(1 + hourly_trade_notional_t))
  + 0.25 * zscore(
        clip(
            (price_{t+6h} - price_{t-1})
            /
            (price_t - price_{t-1}),
            -1,
            2
        )
    )
  - 0.15 * zscore(
        log(
            1
            +
            (
                sum(|price_{t+i} - price_{t+i-1}| for i = 1 to 6)
                /
                |price_{t+6h} - price_t|
            )
        )
    )
```

Interpretation:

- rewards a large move,
- rewards meaningful volume,
- rewards persistence,
- penalizes noisy back-and-forth movement after the initial jump.

## 6. Scoring And Flagging Rules

### 6.1 Hourly Scoring

- Use a one-hour interval.
- Score every eligible hour for each market.
- Sort data by timestamp before computing lags and leads.
- Leave rows blank where historical or future windows are unavailable.

### 6.2 Baselines And Z-Scores

The preferred production setup is:

- use a baseline built from a pool of comparable historical Polymarkets,
- not just the target market itself,
- because a market that is suspicious from the beginning can make within-market z-scores look deceptively ordinary.

For V1, the mean and standard deviation used in every formula z-score should come from a broader historical baseline pool, not from only the proof-of-concept pair or from the target markets being scored.

Use 100 resolved binary YES/NO markets from varied categories with reasonable historical volume for the baseline pool. For each feature:

1. calculate one mean and one standard deviation per baseline market,
2. take the average of the 100 market-level means as the baseline mean,
3. take the average of the 100 market-level standard deviations as the baseline standard deviation.

Comparable baseline markets should match where possible on:

- binary structure,
- similar volume/liquidity,
- similar market age,
- same broad category when available.

### 6.3 Final Flag Threshold

The final score is already fixed before the formal proof-of-concept reproduction:

```text
move_weight =
    abs_initial_move
    /
    (abs_initial_move + 0.10)

volume_weight =
    hourly_trade_notional
    /
    (hourly_trade_notional + 1000)

retention_weight =
    clip(
        (clipped_retention_ratio_6h + 1)
        /
        3,
        0,
        1
    )

quality_weight =
    move_weight
  * volume_weight
  * retention_weight

final_suspicion_score =
    average(
        sustained_shock_score * quality_weight,
        fragile_repricing_score * quality_weight,
        spread_stress_score * quality_weight,
        impact_accepted_score * quality_weight,
        anti_noise_score * quality_weight
    )

final_suspicion_z =
    zscore(final_suspicion_score)
```

For V1, the mean and standard deviation used to compute `final_suspicion_z` must come from the same frozen 100-market historical baseline pool used for the component z-scores, not from the proof-of-concept pair or from the markets being scored.

Use a fixed threshold:

```text
flag if final_suspicion_z >= 2.0
```

For the 10-market backtest:

- use the first hour where `final_suspicion_z` crosses `2.0`,
- store that as `flag_time_utc`,
- do not change the threshold after seeing the 10-market results.

The proof-of-concept stage is a reproduction check for this already-fixed combined score, not a formula-selection exercise.

## 7. Data Pipeline

The official V1 implementation should contain exactly five scripts:

```text
pull_polymarket_orderbooks.py
compute_formula_scores.py
select_market_signals.py
run_backtest.py
summarize_study.py
```

Do not add extra pipeline scripts unless the user explicitly requests them.

One separate support script is explicitly approved for baseline construction:

```text
build_formula_baseline.py
```

This support script is not part of the five-step study pipeline. It is responsible for:

1. discovering or accepting 100 resolved historical binary markets from varied categories with reasonable volume,
2. using their historical raw order-book data,
3. calculating one mean and one standard deviation per market for each feature,
4. averaging those market-level means and standard deviations into the feature-level baseline used by formula z-scores.

Store the reusable baseline outputs in:

```text
data/baseline_market_registry.csv
data/formula_baseline_stats.csv
```

One separate operational helper is also approved:

```text
pull_baseline_orderbooks.py
```

It only automates historical raw-data pulls for the approved baseline registry and is not part of the official five-step study pipeline.

## 7.1 Historical Polymarket Data Acquisition

Script:

```text
pull_polymarket_orderbooks.py
```

### Inputs

- market metadata,
- YES/NO token identifiers,
- historical order-book reconstruction source,
- resolved market dates.

### Outputs

```text
data/raw_orderbooks/{market_slug}.parquet
```

### Requirements

- one raw parquet per market is acceptable,
- include the fields needed for the approved formulas,
- no live sports data in the proof-of-concept pair.

## 7.2 Market Registry

Create one shared CSV:

```text
data/market_registry.csv
```

Recommended columns:

```text
market_id
market_slug
market_question
event_category
associated_asset
benchmark_asset
resolution_time_utc
source_data_path
yes_token_id
study_group
```

Where:

- `study_group` is one of:
  - `proof_of_concept_positive`
  - `proof_of_concept_negative`
  - `backtest_10`

Do not add columns unless they are needed later.

## 7.3 Formula Scoring Script

Script:

```text
compute_formula_scores.py
```

Create a script that:

1. reads the raw historical order-book data,
2. aggregates to one row per hour,
3. applies the frozen broad-market baseline mean and standard deviation from `data/formula_baseline_stats.csv`,
4. computes only the five approved formulas,
5. writes a consolidated output table.

Primary output:

```text
outputs/formula_scores.csv
```

Recommended columns:

```text
market_id
market_slug
timestamp_utc
sustained_shock_score
fragile_repricing_score
spread_stress_score
impact_accepted_score
anti_noise_score
final_suspicion_z
```

Only add helper columns if they are actually needed for debugging during development. Do not carry them into the final official output unless the user asks for them.

## 7.4 Signal Selection Script

Script:

```text
select_market_signals.py
```

Create a script that:

1. reads `outputs/formula_scores.csv`,
2. applies the frozen final score and threshold,
3. selects the first qualifying flag per market,
4. writes one consolidated signal table.

Primary output:

```text
outputs/market_signal_results.csv
```

Recommended columns:

```text
market_id
market_slug
flag_time_utc
```

This table should contain only markets that were actually flagged.

## 7.5 Asset Price Data

For associated assets and `SPY`, fetch historical market prices from an external market-data API.

The study can begin with daily data for simplicity:

- enter on the first tradable session after the flag,
- exit at the session aligned with Polymarket resolution.

Later, the project can upgrade to intraday asset data if needed.

Store data in a reusable shared table rather than one CSV per market:

```text
data/asset_prices.csv
```

Recommended V1 columns:

```text
asset
timestamp_utc
close
```

Use only the columns needed by the backtest implementation. If a later intraday version needs additional fields, add them deliberately at that time.

## 7.6 Backtest Script

Script:

```text
run_backtest.py
```

Create a script that:

1. reads `market_signal_results.csv`,
2. joins market metadata from `market_registry.csv`,
3. fetches or updates the shared `data/asset_prices.csv` file when needed,
4. loads historical prices for the associated asset and `SPY`,
5. determines the entry time,
6. holds until the market resolution time,
7. computes one row per flagged event.

Primary output:

```text
outputs/backtest_results.csv
```

Final lean columns:

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

- duplicate exit time,
- signal score,
- dollar-profit fields,
- unused metadata.

## 7.7 Study Summary Script

Script:

```text
summarize_study.py
```

Create a final script that:

1. reads `outputs/backtest_results.csv`,
2. uses only `excess_return_pct` across the event rows,
3. computes the final study statistics.

Primary output:

```text
outputs/study_summary.csv
```

Recommended columns:

```text
n_markets
mean_excess_return_pct
median_excess_return_pct
win_rate
p_value_one_sided
ci_95_lower_pct
ci_95_upper_pct
```

## 8. Statistical Plan

## 8.1 Experimental Unit

The experimental unit is:

```text
one Polymarket event
```

Not:

- one hourly flag,
- one token side,
- one market row.

Each flagged event contributes one backtest observation.

## 8.2 Tested Variable

The final statistical test uses only:

```text
excess_return_pct
```

Where:

```text
excess_return_pct =
    associated_asset_return_pct
  - benchmark_return_pct
```

## 8.3 Hypotheses

```text
H0: mean(excess_return_pct) = 0
H1: mean(excess_return_pct) > 0
```

This means:

- null hypothesis: flagged Polymarket events do not generate alpha over the benchmark,
- alternative hypothesis: flagged Polymarket events do generate positive alpha.

## 8.4 P-Value

The p-value answers:

```text
If the strategy truly had no alpha, how surprising would the observed mean excess return be?
```

It does **not** mean:

- the probability that a specific market was informed,
- the probability that the null hypothesis is true.

## 8.5 95% Confidence Interval

The 95% confidence interval estimates a plausible range for the true average excess return of the strategy.

Because the sample is small (`n = 10`), report:

1. a one-sample t-test p-value,
2. a bootstrap 95% confidence interval.

## 8.6 Interpretation Example

If the 10-flagged-event study reports:

```text
mean excess return = +4.2%
95% CI = [+0.8%, +7.6%]
p-value = 0.02
```

Then the correct interpretation is:

- the associated-asset trades beat `SPY` by 4.2 percentage points per event on average,
- the estimated true average effect is plausibly positive,
- results this strong would be unlikely if the strategy had no real edge.

## 9. Development Phases

### Phase 1: Formalize The Study

- Create `AGENTS.md`
- Create `PROJECT_PLAN.md`
- Lock the approved formulas
- Lock the lean output schemas

### Phase 2: Historical Data Validation

- Verify reconstruction of:
  - clavicular-pregnancy market,
  - past major-league sports market.
- Confirm required order-book fields exist.
- Confirm no live-game dependency.

### Phase 3: Proof Of Concept

- Build the formula-scoring script.
- Run the already-fixed final combined score on both proof-of-concept markets.
- Confirm:
  - clavicular market flags,
  - major-league sports comparison market does not.
- Reproduce the expected proof-of-concept result using `final_suspicion_z`.

### Phase 4: Select The 10 Backtest Markets

- Finalize the 10 markets using the inclusion checklist.
- Record them in `market_registry.csv`.
- Pull historical order-book data for all 10.

### Phase 5: Backtest Implementation

- Build signal-selection script.
- Build asset-price ingestion.
- Build backtest script.
- Produce one event-level row per flagged market.

### Phase 6: Final Statistical Study

- Build study-summary script.
- Compute:
  - mean excess return,
  - median excess return,
  - win rate,
  - p-value,
  - 95% confidence interval.
- Interpret the results as investment-performance evidence, not as proof that any single market was informed.

## 10. Explicit Non-Goals For V1

The first formal version should not include:

- live market detection,
- open-interest features,
- wallet-level trader attribution,
- holder-distribution equations,
- news API integration,
- calibrated probability-of-informed-trading outputs,
- multiple benchmark families,
- separate final CSV files per market,
- extra formula families that are not in the approved list.

These can be future extensions, but they should not dilute the first clean study.

## 11. Future Extensions After V1

Potential later additions, only after the core study works:

1. **News-aware classification**
   - classify flags as:
     - public-news-explained,
     - unexplained suspicious.
   - use only backward-looking news windows in real time.

2. **Intraday backtesting**
   - use exact flag-hour entries instead of next-session daily entries.

3. **Alternative benchmarks**
   - sector-specific or asset-class-specific robustness checks.

4. **Probability calibration**
   - convert abnormality scores into validated probabilities only after building a labeled dataset.

5. **Additional formula research**
   - only after the approved V1 pipeline is complete and interpretable.
