#!/usr/bin/env python3
"""
Scoring constants for scout_engine.py: every hardcoded weight, threshold,
and hyperparameter used in scoring logic. Values are unchanged from their
prior inline locations - this file only names the numbers.
"""

# ==============================================================================
# COMPOSITE_INDEX  (calculate_composite_index, composite_description,
# compute_multiseason_features, _trajectory_label)
# ==============================================================================

COMPOSITE_ZSCORE_WEIGHT = 0.40     # weight of the position-pool z-score aggregate component
COMPOSITE_STYLE_WEIGHT = 0.30      # weight of the style-category percentile average component
COMPOSITE_POWER_WEIGHT = 0.30      # weight of the league power-rating component

CATEGORY_COVERAGE_DIVISOR = 2      # a style category only counts if a player has data for >= 1/this-many of its metrics

# composite_description() tiers - checked top-down; below the last one is "Poor"
COMPOSITE_TIER_WORLD_CLASS = 90
COMPOSITE_TIER_ELITE = 80
COMPOSITE_TIER_EXCELLENT = 70
COMPOSITE_TIER_GOOD = 60
COMPOSITE_TIER_AVERAGE = 50
COMPOSITE_TIER_BELOW_AVERAGE = 40

MULTISEASON_DEFAULT_LOOKBACK = 3       # compute_multiseason_features: default number of prior seasons to include
MULTISEASON_DEFAULT_MIN_MINUTES = 270  # compute_multiseason_features: minimum minutes for a season to count

BREAKOUT_SCORE_DELTA = 8           # 'breakout' fires when latest-season z exceeds the prior-seasons average by at least this

TRAJECTORY_VOLATILE_STD = 10       # consistency_std above this -> 'Volatile' trajectory label
TRAJECTORY_RISING_SLOPE = 2        # trajectory_slope >= this -> 'Rising' trajectory label
TRAJECTORY_DECLINING_SLOPE = -2    # trajectory_slope <= this -> 'Declining' trajectory label

# ==============================================================================
# GEMS  (cmd_get_hidden_gems - the 7 hidden-gem detection methods, cmd_backtest_gems)
# ==============================================================================

GEM_MV_CEILING_DEFAULT = 40_000_000    # market value at/above which a player can never be flagged a "hidden gem"

# Minutes floor before gem scoring runs on a position pool at all
GEM_MIN_MINUTES = {'GK': 270, 'DF': 450, 'MF': 450, 'FW': 450}
GEM_MIN_MINUTES_DEFAULT = 450          # fallback minutes floor for a position not in GEM_MIN_MINUTES

GEM_PCTL_OUTLIER_COMPOSITE = 80        # Method 1 (Percentile Outlier): composite above this fires

GEM_ZSCORE_OUTLIER_Z = 1.5             # Method 2 (Z-Score): composite z-score above this fires

VALUE_RATIO_SCALE = 50                 # value_ratio = (composite / wage_percentile) * this; also reused by cmd_get_moneyball_score and cmd_get_squad_optimizer
GEM_VALUE_RATIO_THRESHOLD = 60         # Method 3 (Value Ratio): value_ratio above this (on real wage data only) fires

GEM_AGE_POTENTIAL_YOUNG_AGE = 23       # age < this -> GEM_AGE_POTENTIAL_YOUNG_MULT
GEM_AGE_POTENTIAL_YOUNG_MULT = 1.3
GEM_AGE_POTENTIAL_RISING_AGE = 26      # age < this (and >= young age) -> GEM_AGE_POTENTIAL_RISING_MULT
GEM_AGE_POTENTIAL_RISING_MULT = 1.1
GEM_AGE_POTENTIAL_VETERAN_AGE = 30     # age > this -> GEM_AGE_POTENTIAL_VETERAN_MULT
GEM_AGE_POTENTIAL_VETERAN_MULT = 0.9
GEM_AGE_POTENTIAL_DEFAULT_MULT = 1.0   # age otherwise in between (26-30 inclusive)
GEM_AGE_GEM_MAX_AGE = 24               # Method 4 (Age-Weighted Potential): age must be below this to fire
GEM_AGE_GEM_MIN_POTENTIAL = 85         # Method 4: age_potential must exceed this to fire

GEM_MONEYBALL_THRESHOLD = 65           # Method 5 (Composite Score): moneyball score above this fires

GEM_ANOMALY_PERCENTILE = 90            # Method 6 (Statistical Anomaly): a style category counts as "top" above this percentile
GEM_ANOMALY_MIN_CATEGORIES = 2         # Method 6: this many "top" categories fires the anomaly signal

GEM_ALREADY_EXPENSIVE_WAGE_PCTL = 85   # real (non-estimated) wage percentile at/above which a player is excluded as "already expensive"
GEM_MIN_METHODS_TRIGGERED = 2          # minimum number of the 7 detection methods that must fire to qualify as a gem

GEM_BACKTEST_GOOD_Z = 60.0             # cmd_backtest_gems: outcome z-score at/above which a flagged gem "stayed good"

# ==============================================================================
# MONEYBALL  (calculate_moneyball)
# ==============================================================================

MONEYBALL_PERFORMANCE_WEIGHT = 0.5         # weight on raw composite performance
MONEYBALL_VALUE_EFFICIENCY_WEIGHT = 0.3    # weight on value-for-wage efficiency
MONEYBALL_CONTRACT_WEIGHT = 0.2            # weight on contract-opportunity score

# ==============================================================================
# CONTRACT_URGENCY  (contract_opportunity_breakdown, _tag_availability)
# ==============================================================================

CONTRACT_URGENCY_UNKNOWN = 20      # urgency score when contract expiry is unknown
CONTRACT_URGENCY_EXPIRED = 60      # urgency score when months remaining <= 0

# (months-remaining ceiling, urgency score at/below that ceiling)
CONTRACT_MONTHS_TIER_6 = 6
CONTRACT_URGENCY_LT_6M = 55
CONTRACT_MONTHS_TIER_12 = 12
CONTRACT_URGENCY_LT_12M = 45
CONTRACT_MONTHS_TIER_18 = 18
CONTRACT_URGENCY_LT_18M = 30
CONTRACT_MONTHS_TIER_24 = 24
CONTRACT_URGENCY_LT_24M = 15
CONTRACT_URGENCY_GE_24M = 5        # urgency score when more than CONTRACT_MONTHS_TIER_24 months remain

CONTRACT_CLAUSE_SCORE_NONE = 0     # clause discount score when there is no release clause / market value on file

# (release-clause / market-value ratio ceiling, clause discount score below that ceiling)
CONTRACT_CLAUSE_RATIO_50 = 0.5
CONTRACT_CLAUSE_SCORE_50 = 40
CONTRACT_CLAUSE_RATIO_75 = 0.75
CONTRACT_CLAUSE_SCORE_75 = 30
CONTRACT_CLAUSE_RATIO_100 = 1.0
CONTRACT_CLAUSE_SCORE_100 = 20
CONTRACT_CLAUSE_RATIO_125 = 1.25
CONTRACT_CLAUSE_SCORE_125 = 10     # ratio >= 1.25 scores 0 (CONTRACT_CLAUSE_SCORE_NONE)

AVAILABILITY_FREE_MAX_MONTHS = 6       # _tag_availability: months remaining at/below this tags a similar player 'free'
AVAILABILITY_EXPIRING_MAX_MONTHS = 12  # _tag_availability: months remaining at/below this (and above the free bound) tags 'expiring'

# ==============================================================================
# MARKET_VALUE_HEURISTIC  (calculate_player_market_value, get_wage_value,
# _mv_features_dict)
# ==============================================================================

# Power-rating base value bands: base = MV_BASE_x + (power_rating - MV_PR_x) * MV_INCR_x
MV_PR_90 = 90
MV_BASE_90 = 6_000_000
MV_INCR_90 = 600_000
MV_PR_80 = 80
MV_BASE_80 = 3_000_000
MV_INCR_80 = 300_000
MV_PR_70 = 70
MV_BASE_70 = 1_500_000
MV_INCR_70 = 150_000
MV_PR_60 = 60
MV_BASE_60 = 750_000
MV_INCR_60 = 75_000
MV_PR_50 = 50
MV_BASE_50 = 300_000
MV_INCR_50 = 45_000
MV_BASE_UNDER_50 = 100_000          # base value for power_rating < 50
MV_PR_FLOOR_40 = 40                 # rating floor below which the below-50 increment no longer applies
MV_INCR_UNDER_50 = 20_000

MV_POSITION_MULTIPLIERS = {'FW': 1.15, 'MF': 1.05, 'DF': 0.95, 'GK': 0.85}
MV_POSITION_MULTIPLIER_DEFAULT = 1.0

# Age multiplier bands (checked top-down; ages 21-23 use '<', 24+ use '<=')
MV_AGE_U21_MAX = 21
MV_AGE_MULT_U21 = 1.2
MV_AGE_U24_MAX = 24
MV_AGE_MULT_U24 = 1.3
MV_AGE_26_MAX = 26
MV_AGE_MULT_26 = 1.2
MV_AGE_28_MAX = 28
MV_AGE_MULT_28 = 1.0
MV_AGE_30_MAX = 30
MV_AGE_MULT_30 = 0.8
MV_AGE_32_MAX = 32
MV_AGE_MULT_32 = 0.5
MV_AGE_MULT_OVER_32 = 0.3

MV_FATIGUE_MULT_DEFAULT = 1.0
MV_HIGH_MINUTES_PER_GAME = 80       # avg minutes/game above this boosts the estimate
MV_HIGH_MINUTES_MULT = 1.1
MV_LOW_MINUTES_PER_GAME = 45        # avg minutes/game below this discounts the estimate
MV_LOW_MINUTES_MULT = 0.8

MV_PERF_MULT_DEFAULT = 1.0
MV_PERF_MULT_EXPONENT = 2.0         # performance scaling curve: (performance/100) ** this
MV_PERF_MULT_MIN = 0.04             # floor on the performance multiplier
MV_PERF_MULT_MAX = 1.1              # ceiling on the performance multiplier

WAGE_ESTIMATE_MV_FACTOR = 0.004     # estimated weekly wage = market_value * this / 52 weeks
WAGE_ESTIMATE_FLOOR = 500           # minimum estimated weekly wage (EUR)

# Data-driven MV model (train_mv_models) feature engineering
MV_MODEL_CONTRACT_MONTHS_DEFAULT = 30.0   # neutral imputed contract-months-remaining when unknown (mid-contract)
MV_MODEL_CONTRACT_MONTHS_MIN = 0.0
MV_MODEL_CONTRACT_MONTHS_MAX = 60.0

MV_PREDICTION_MIN = 50_000.0            # floor clamp on a model-predicted market value (EUR)
MV_PREDICTION_MAX = 250_000_000.0       # ceiling clamp on a model-predicted market value (EUR)

# Prior-market-value brackets (EUR) the GBM's reliability is broken down
# by - bucketed by PRIOR value (an actual model input), not outcome
# value, since outcome bucketing conflates model bias with mean-reversion.
MV_PRIOR_MV_CONFIDENCE_BRACKETS = (0, 2_000_000, 10_000_000, 30_000_000, 60_000_000, 100_000_000, None)

# Qualitative confidence tier by training-bracket sample size (n of real,
# labeled rows backing that bracket - see mdape_pct_by_prior_bracket). 'low'
# is calibrated to flag the thinnest (100M+) bracket specifically.
MV_CONFIDENCE_TIER_HIGH_MIN_N = 5000
MV_CONFIDENCE_TIER_MEDIUM_MIN_N = 500

# ==============================================================================
# SQUAD_PROFILE  (backend.scoring.squad_profile.build_squad_profile,
# backend.routers.squad - GET /teams/{team}/squad-profile)
# ==============================================================================

SQUAD_PROFILE_MIN_DEPTH = 3                # a position with fewer rostered players than this is flagged "thin"

SQUAD_PROFILE_AGING_THRESHOLD = 30         # age at/above which a player counts toward a position's "aging" count

# Contract cliff: two independently-configurable lookahead windows (months
# remaining on contract). within_long_window implies within_short_window
# whenever a player also clears the shorter bar.
SQUAD_PROFILE_CONTRACT_CLIFF_SHORT_MONTHS = 6
SQUAD_PROFILE_CONTRACT_CLIFF_LONG_MONTHS = 12

# Style diversity: "style-similar" means every assignable rostered player at a
# position landed in the same ml.style_clustering archetype (no separate
# threshold constant needed here).

# ==============================================================================
# PLAYER_RISK  (backend.scoring.risk - four independent risk flags exposed
# via GET /teams/{team}/squad-profile's high_risk_players section and
# GET /players/{id})
# ==============================================================================

# Contract risk has no thresholds of its own - "expiring soon" reuses
# CONTRACT_MONTHS_TIER_12 and "meaningful value" reuses COMPOSITE_TIER_GOOD,
# so it can't silently drift into a second definition of either word.

# Mileage/decline risk: age gate, then either heavy career minutes or a
# pace-dependent style profile. Deliberately stricter than
# SQUAD_PROFILE_AGING_THRESHOLD (30), which targets squad composition, not physical decline.
RISK_MILEAGE_AGE_THRESHOLD = 32
RISK_MILEAGE_CAREER_MINUTES_THRESHOLD = 25000   # roughly 10 full seasons as a regular starter
# Matched by keyword, not a hardcoded list, since the style-category set
# shifts as metrics are retired (see composite.py's RETIRED_METRICS/ORPHAN_METRICS).
RISK_PACE_CATEGORY_KEYWORDS = ('dribbl', 'take-on', '1v1', 'carrying', 'carries', 'pace')
RISK_PACE_STYLE_PERCENTILE_THRESHOLD = 70       # avg percentile across matched categories at/above this = "leans on pace"

# Sell-high risk fires when BOTH hold: current real value is at/near its
# own historical peak, AND ml.sell_high_risk predicts a high on-field
# deterioration probability. 0.5 matches the model's own saved eval threshold.
RISK_SELL_HIGH_DETERIORATION_PROB_THRESHOLD = 0.5
RISK_SELL_HIGH_PEAK_RATIO = 0.9                 # current real value >= this fraction of career-peak real value = "at/near peak"

# Financial risk: value_efficiency (backend.scoring.moneyball's formula)
# at/below this counts as overpaid relative to output. 50 is neutral in that
# formula; 25 is meaningfully below it, not just a shade under.
RISK_FINANCIAL_VALUE_EFF_THRESHOLD = 25.0

# ==============================================================================
# SELL_HIGH_ML  (ml.sell_high_risk.* - the at/near-peak condition above is
# unchanged and NOT touched by this model)
# ==============================================================================

# Current-season minutes floor for a row to enter training at all (same
# floor compute_multiseason_features uses) - garbage-time minutes shouldn't
# produce a trustworthy output_score.
SELL_HIGH_MIN_MINUTES = MULTISEASON_DEFAULT_MIN_MINUTES

# Minutes floor for compute_reference_distributions' frozen per-position
# z-score reference - deliberately the same floor as SELL_HIGH_MIN_MINUTES,
# computed across all seasons regardless of market-value availability.
SELL_HIGH_REFERENCE_MIN_MINUTES = MULTISEASON_DEFAULT_MIN_MINUTES

# NEXT-season minutes floor for the deterioration LABEL - stricter than
# SELL_HIGH_MIN_MINUTES. Falling below it (role collapse) IS itself a
# maximal-deterioration outcome - excluding these would miss the worst cases.
SELL_HIGH_DETERIORATION_MINUTES_FLOOR = 450

# Among players who stayed above the floor, an output_score drop at/above
# this quantile counts as "significant deterioration" - a data-grounded
# cutoff (worst quartile) chosen to avoid raw-delta's mean-reversion bias.
SELL_HIGH_DECLINE_QUANTILE = 0.75

# Most recent N label-seasons held out entirely for a genuine forward-in-
# time check - same rationale as MV_TEMPORAL_HOLDOUT_SEASONS.
SELL_HIGH_TEMPORAL_HOLDOUT_SEASONS = 2

# Small GBM hyperparameter grid, same shape/sizing rationale as
# GBM_GRID_* above.
SELL_HIGH_GRID_N_ESTIMATORS = (100, 200, 300)
SELL_HIGH_GRID_MAX_DEPTH = (2, 3, 4)
SELL_HIGH_GRID_LEARNING_RATE = (0.03, 0.05, 0.1)

# ==============================================================================
# GBM_HYPERPARAMS  (train_mv_models)
# ==============================================================================

# Small grid (via GroupKFold) for boosting-stage count/tree depth/
# shrinkage rate - not exhaustive, since the labeled dataset is small and
# a larger grid risks overfitting the SELECTION itself. 3x3x3 = 27 combos.
GBM_GRID_N_ESTIMATORS = [100, 200, 300]
GBM_GRID_MAX_DEPTH = [2, 3, 4]
GBM_GRID_LEARNING_RATE = [0.03, 0.05, 0.1]

# Fixed seed for every GradientBoostingRegressor fit in train_mv_models -
# makes retrains COMPARABLE: without it, a changed prediction between
# retrains can't be attributed to a real feature/data change vs. fit randomness.
MV_GBM_RANDOM_STATE = 42

# How many of the most-recent real-labeled seasons train_mv_models holds
# out for a genuine TEMPORAL evaluation - GroupKFold(player) alone
# doesn't catch temporal leakage (later rows could sit in a training fold).
MV_TEMPORAL_HOLDOUT_SEASONS = 2

# ==============================================================================
# IMPACT_SCORE  (backend.scoring.impact.impact_breakdown,
# scout_engine.cmd_get_impact_score - GET /players/{id}/impact)
# ==============================================================================

# On/off-pitch team differentials are a team-level signal riding on a
# single player's sample of games - noisier than an individual per90 stat,
# so this gate runs higher than GEM_MIN_MINUTES.
IMPACT_SCORE_MIN_MINUTES = {'GK': 630, 'DF': 900, 'MF': 900, 'FW': 900}
IMPACT_SCORE_MIN_MINUTES_DEFAULT = 900

# impact_breakdown() tiers - checked top-down; below the last one is "Strongly Negative Impact"
IMPACT_TIER_STRONGLY_POSITIVE = 70
IMPACT_TIER_POSITIVE = 58
IMPACT_TIER_NEUTRAL = 42
IMPACT_TIER_NEGATIVE = 30

# ==============================================================================
# STYLE_CLUSTERING  (ml.style_clustering.*)
# ==============================================================================

# Reuses compute_multiseason_features' minutes floor, so garbage-time
# minutes don't pull a cluster centroid toward noise.
STYLE_CLUSTER_MIN_MINUTES = MULTISEASON_DEFAULT_MIN_MINUTES

# K search range per position group: fit every K in range, best kept by
# silhouette score. Same range for every group, so archetype counts are
# a like-for-like comparison across positions.
STYLE_CLUSTER_K_RANGE = range(3, 9)

# Per-position override of the silhouette-argmax K choice - a deliberate
# human call. Silhouette is still computed/reported for every K; this
# only changes which already-fitted K gets persisted.
STYLE_CLUSTER_K_OVERRIDE = {'FW': 5, 'DF': 6}

# Per-position clustering distance metric. 'cosine' L2-normalizes first
# (Euclidean K-means on unit vectors == cosine similarity), chosen per
# position from face-validity checks. NOTE: distance_to_centroid's scale is bounded (0-2) for cosine, unbounded for Euclidean - never compare across metrics.
STYLE_CLUSTER_DISTANCE_METRIC = {'MF': 'cosine', 'FW': 'cosine', 'DF': 'cosine'}

# Per-position down-weighting of negative (deficient) deviations before
# normalization - without it, a single large weakness can outweigh a
# larger total strength signal. FW has no weight - it collapsed hybrid labels without fixing real cases there.
STYLE_CLUSTER_NEGATIVE_WEIGHT = {'MF': 0.3, 'DF': 0.3}

STYLE_CLUSTER_RANDOM_STATE = 42

# Clustering fits on each player's category percentiles CENTERED on
# their own mean (relative shape, not absolute level) - a centroid's
# centered value must exceed this margin to count as "elevated". Label text still reports the real ABSOLUTE percentile.
STYLE_CLUSTER_ELEVATED_MARGIN = 8

# Human-facing display name for a trained archetype, layered on top of
# its algorithmic label. Keyed by the EXACT algorithmic string, not
# cluster id (unstable across retrains) - diff new meta's labels against these keys after any retrain.
ARCHETYPE_NAME_OVERRIDES = {
    'MF': {
        'Defensive Contribution / Passing & Distribution': 'The Anchor',
        'Creativity & Chance Creation': 'The Provider',
        'Limited Creativity & Chance Creation': 'The Carrier',
        'Creativity & Chance Creation / Goal Threat & Shooting': 'The Number 10',
        'Expected Goals (xG) / Goal Threat & Shooting': 'The Goal-Getter',
        'Goal Threat & Shooting': 'The Box-Crasher',
        'Dribbling & Take-Ons': 'The Ball-Carrier',
        'Balanced / Well-Rounded': 'The Generalist',
    },
    'FW': {
        'Finishing & Clinical': 'The Finisher',
        'Expected Goals (xG) & Efficiency / Finishing & Clinical': 'The Efficient Scorer',
        'Creativity & Assists / Finishing & Clinical': 'The Complete Forward',
        'Creativity & Assists': 'The Creator',
        'Defensive Work / Ball Control & Touch / Dribbling & 1v1 Skills': 'The Two-Way Dribbler',
    },
    'DF': {
        'Interceptions & Blocks': 'The Reader',
        'Ball Playing & Passing': 'The Ball-Player',
        'Dribbling & Take-Ons': 'The Carrier',
        'Attacking Contribution': 'The Attacking Outlet',
        'Expected Goals (xG) & xA / Attacking Contribution': 'The Goal Threat',
        'Limited Attacking Contribution': 'The Stopper',
    },
}
