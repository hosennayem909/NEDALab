"""Hypothesis testing engine with effect size measures."""
import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import pearsonr, spearmanr
from statsmodels.stats.multicomp import pairwise_tukeyhsd


def _sf(v, d=6):
    try:
        f = float(v)
        if np.isnan(f) or np.isinf(f):
            return None
        return round(f, d)
    except (TypeError, ValueError):
        return None


def _sig(p):
    if p is None:
        return ""
    if p < 0.001: return "***"
    if p < 0.01: return "**"
    if p < 0.05: return "*"
    if p < 0.1: return "."
    return ""


def _reject(p, alpha=0.05):
    if p is None:
        return None
    return bool(p < alpha)


def _numeric(s: pd.Series) -> np.ndarray:
    return pd.to_numeric(s, errors="coerce").dropna().to_numpy(dtype=float)


# ============================================================
# Effect Size Interpreters
# ============================================================
def _interpret_cohens_d(d):
    if d is None: return None
    ad = abs(d)
    if ad < 0.2: return "Negligible effect"
    if ad < 0.5: return "Small effect"
    if ad < 0.8: return "Medium effect"
    return "Large effect"


def _interpret_eta_sq(e):
    if e is None: return None
    if e < 0.01: return "Negligible effect"
    if e < 0.06: return "Small effect"
    if e < 0.14: return "Medium effect"
    return "Large effect"


def _interpret_rank_biserial(r):
    if r is None: return None
    ar = abs(r)
    if ar < 0.1: return "Negligible effect"
    if ar < 0.3: return "Small effect"
    if ar < 0.5: return "Medium effect"
    return "Large effect"


def _interpret_cramers_v(v):
    if v is None: return None
    if v < 0.1: return "Negligible association"
    if v < 0.3: return "Small association"
    if v < 0.5: return "Medium association"
    return "Large association"


def _interpret_r2(r2):
    if r2 is None: return None
    if r2 < 0.01: return "Negligible relationship"
    if r2 < 0.09: return "Small relationship"
    if r2 < 0.25: return "Medium relationship"
    return "Large relationship"


# ============================================================
# t-tests
# ============================================================
def one_sample_ttest(df, column, popmean):
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found")
    x = _numeric(df[column])
    if len(x) < 3:
        raise ValueError("Need at least 3 numeric values")
    if popmean is None:
        raise ValueError("popmean required")

    t, p = stats.ttest_1samp(x, popmean)
    sample_mean = float(x.mean())
    sample_std = float(x.std(ddof=1)) if len(x) > 1 else 0.0

    # Cohen's d (one-sample)
    cohens_d = None
    if sample_std > 0:
        cohens_d = (sample_mean - popmean) / sample_std

    return {
        "test": "One-sample t-test",
        "n": int(len(x)),
        "sample_mean": _sf(sample_mean, 4),
        "popmean": _sf(popmean, 4),
        "t_statistic": _sf(t, 4),
        "p_value": _sf(p, 6),
        "degrees_of_freedom": int(len(x) - 1),
        "significance": _sig(p),
        "reject_null": _reject(p),
        # Effect sizes
        "cohens_d": _sf(cohens_d, 4),
        "cohens_d_interpretation": _interpret_cohens_d(cohens_d),
        "interpretation": (
            f"Mean ({_sf(sample_mean,4)}) is significantly different from {popmean} (p={_sf(p,6)})"
            if _reject(p) else
            f"No significant difference from {popmean} (p={_sf(p,6)})"
        ),
    }


def two_sample_ttest(df, column, group_column, equal_var=True):
    if column not in df.columns or group_column not in df.columns:
        raise ValueError("Column not found")
    sub = df[[column, group_column]].dropna()
    sub[column] = pd.to_numeric(sub[column], errors="coerce")
    sub = sub.dropna()
    groups = sub[group_column].unique()
    if len(groups) != 2:
        raise ValueError(f"Group column must have exactly 2 unique values, got {len(groups)}")

    g1 = sub[sub[group_column] == groups[0]][column].to_numpy(dtype=float)
    g2 = sub[sub[group_column] == groups[1]][column].to_numpy(dtype=float)
    if len(g1) < 3 or len(g2) < 3:
        raise ValueError("Each group needs at least 3 values")

    t, p = stats.ttest_ind(g1, g2, equal_var=equal_var)

    # Cohen's d (two-sample pooled)
    n1, n2 = len(g1), len(g2)
    m1, m2 = float(g1.mean()), float(g2.mean())
    s1, s2 = float(g1.std(ddof=1)), float(g2.std(ddof=1))
    pooled_std = np.sqrt(((n1 - 1) * s1 ** 2 + (n2 - 1) * s2 ** 2) / (n1 + n2 - 2))
    cohens_d = (m1 - m2) / pooled_std if pooled_std > 0 else None

    # Hedges' g (bias-corrected)
    hedges_g = None
    if cohens_d is not None:
        correction = 1 - 3 / (4 * (n1 + n2) - 9)
        hedges_g = cohens_d * correction

    return {
        "test": "Two-sample t-test (independent)",
        "group_column": str(group_column),
        "groups": [str(groups[0]), str(groups[1])],
        "n_group1": int(n1),
        "n_group2": int(n2),
        "mean_group1": _sf(m1, 4),
        "mean_group2": _sf(m2, 4),
        "std_group1": _sf(s1, 4),
        "std_group2": _sf(s2, 4),
        "t_statistic": _sf(t, 4),
        "p_value": _sf(p, 6),
        "significance": _sig(p),
        "reject_null": _reject(p),
        "equal_variance_assumed": bool(equal_var),
        # Effect sizes
        "cohens_d": _sf(cohens_d, 4),
        "cohens_d_interpretation": _interpret_cohens_d(cohens_d),
        "hedges_g": _sf(hedges_g, 4),
        "hedges_g_interpretation": _interpret_cohens_d(hedges_g),
        "interpretation": (
            f"Significant difference between '{groups[0]}' and '{groups[1]}' (p={_sf(p,6)})"
            if _reject(p) else
            f"No significant difference between groups (p={_sf(p,6)})"
        ),
    }


def paired_ttest(df, column_a, column_b):
    if column_a not in df.columns or column_b not in df.columns:
        raise ValueError("Column not found")
    sub = df[[column_a, column_b]].apply(pd.to_numeric, errors="coerce").dropna()
    if len(sub) < 3:
        raise ValueError("Need at least 3 paired observations")

    a = sub[column_a].to_numpy(dtype=float)
    b = sub[column_b].to_numpy(dtype=float)
    t, p = stats.ttest_rel(a, b)
    diff = a - b
    mean_diff = float(diff.mean())
    std_diff = float(diff.std(ddof=1))

    # Cohen's d (paired)
    cohens_d = mean_diff / std_diff if std_diff > 0 else None

    return {
        "test": "Paired t-test",
        "column_a": str(column_a),
        "column_b": str(column_b),
        "n_pairs": int(len(sub)),
        "mean_a": _sf(a.mean(), 4),
        "mean_b": _sf(b.mean(), 4),
        "mean_diff": _sf(mean_diff, 4),
        "std_diff": _sf(std_diff, 4),
        "t_statistic": _sf(t, 4),
        "p_value": _sf(p, 6),
        "significance": _sig(p),
        "reject_null": _reject(p),
        # Effect sizes
        "cohens_d": _sf(cohens_d, 4),
        "cohens_d_interpretation": _interpret_cohens_d(cohens_d),
        "interpretation": (
            f"Significant difference between paired measurements (p={_sf(p,6)})"
            if _reject(p) else
            f"No significant difference in paired measurements (p={_sf(p,6)})"
        ),
    }


# ============================================================
# ANOVA
# ============================================================
def one_way_anova(df, column, group_column):
    if column not in df.columns or group_column not in df.columns:
        raise ValueError("Column not found")
    sub = df[[column, group_column]].dropna()
    sub[column] = pd.to_numeric(sub[column], errors="coerce")
    sub = sub.dropna()

    groups_list = []
    group_names = []
    for name, grp in sub.groupby(group_column):
        vals = grp[column].to_numpy(dtype=float)
        if len(vals) >= 2:
            groups_list.append(vals)
            group_names.append(str(name))

    if len(groups_list) < 2:
        raise ValueError("Need at least 2 groups with >= 2 observations each")

    f, p = stats.f_oneway(*groups_list)

    # Group stats
    group_stats = []
    for name, g in zip(group_names, groups_list):
        group_stats.append({
            "group": name,
            "n": int(len(g)),
            "mean": _sf(g.mean(), 4),
            "std": _sf(g.std(ddof=1), 4) if len(g) > 1 else None,
        })

    # Effect Sizes: Eta-squared and Omega-squared
    k = len(groups_list)
    n_total = sum(len(g) for g in groups_list)
    grand_mean = float(sub[column].mean())

    ss_between = sum(len(g) * (float(g.mean()) - grand_mean) ** 2 for g in groups_list)
    ss_within = sum(float(((g - g.mean()) ** 2).sum()) for g in groups_list)
    ss_total = ss_between + ss_within

    df_between = k - 1
    df_within = n_total - k
    ms_within = ss_within / df_within if df_within > 0 else 0.0

    eta_sq = ss_between / ss_total if ss_total > 0 else None
    # Omega-squared (less biased)
    if ss_total > 0 and ms_within > 0 and df_within > 0:
        omega_sq = (ss_between - df_between * ms_within) / (ss_total + ms_within)
    else:
        omega_sq = None

    return {
        "test": "One-way ANOVA",
        "column": str(column),
        "group_column": str(group_column),
        "n_groups": int(k),
        "total_n": int(n_total),
        "f_statistic": _sf(f, 4),
        "p_value": _sf(p, 6),
        "significance": _sig(p),
        "reject_null": _reject(p),
        "group_stats": group_stats,
        # Effect sizes
        "eta_squared": _sf(eta_sq, 4),
        "eta_squared_interpretation": _interpret_eta_sq(eta_sq),
        "omega_squared": _sf(omega_sq, 4),
        "omega_squared_interpretation": _interpret_eta_sq(omega_sq),
        "interpretation": (
            f"Significant difference across {k} groups (p={_sf(p,6)})"
            if _reject(p) else
            f"No significant difference across groups (p={_sf(p,6)})"
        ),
    }


# ============================================================
# Chi-Square
# ============================================================
def chi_square_independence(df, column_a, column_b):
    if column_a not in df.columns or column_b not in df.columns:
        raise ValueError("Column not found")
    sub = df[[column_a, column_b]].dropna()
    if len(sub) < 10:
        raise ValueError("Need at least 10 valid rows")

    contingency = pd.crosstab(sub[column_a], sub[column_b])
    if contingency.size < 4:
        raise ValueError("Need at least 2x2 contingency table")

    chi2, p, dof, expected = stats.chi2_contingency(contingency)
    n = int(contingency.values.sum())

    # Cramér's V
    try:
        cramers_v = float(np.sqrt(chi2 / (n * (min(contingency.shape) - 1))))
    except Exception:
        cramers_v = None

    # Odds Ratio (only for 2x2)
    odds_ratio = None
    if contingency.shape == (2, 2):
        try:
            a_ = contingency.iloc[0, 0]
            b_ = contingency.iloc[0, 1]
            c_ = contingency.iloc[1, 0]
            d_ = contingency.iloc[1, 1]
            if b_ * c_ > 0:
                odds_ratio = float((a_ * d_) / (b_ * c_))
        except Exception:
            odds_ratio = None

    return {
        "test": "Chi-Square Test of Independence",
        "column_a": str(column_a),
        "column_b": str(column_b),
        "n": n,
        "table_shape": [int(contingency.shape[0]), int(contingency.shape[1])],
        "chi2_statistic": _sf(chi2, 4),
        "p_value": _sf(p, 6),
        "degrees_of_freedom": int(dof),
        "significance": _sig(p),
        "reject_null": _reject(p),
        # Effect sizes
        "cramers_v": _sf(cramers_v, 4) if cramers_v is not None else None,
        "cramers_v_interpretation": _interpret_cramers_v(cramers_v),
        "odds_ratio": _sf(odds_ratio, 4) if odds_ratio is not None else None,
        "contingency_table": {
            "index": [str(i) for i in contingency.index.tolist()],
            "columns": [str(c) for c in contingency.columns.tolist()],
            "values": contingency.values.tolist(),
        },
        "interpretation": (
            f"'{column_a}' and '{column_b}' are significantly associated (p={_sf(p,6)})"
            if _reject(p) else
            f"No significant association between '{column_a}' and '{column_b}' (p={_sf(p,6)})"
        ),
    }


# ============================================================
# Non-parametric
# ============================================================
def mann_whitney(df, column, group_column):
    if column not in df.columns or group_column not in df.columns:
        raise ValueError("Column not found")
    sub = df[[column, group_column]].dropna()
    sub[column] = pd.to_numeric(sub[column], errors="coerce")
    sub = sub.dropna()
    groups = sub[group_column].unique()
    if len(groups) != 2:
        raise ValueError(f"Need exactly 2 groups, got {len(groups)}")

    g1 = sub[sub[group_column] == groups[0]][column].to_numpy(dtype=float)
    g2 = sub[sub[group_column] == groups[1]][column].to_numpy(dtype=float)

    u, p = stats.mannwhitneyu(g1, g2, alternative="two-sided")

    # Rank-Biserial Correlation (effect size)
    n1, n2 = len(g1), len(g2)
    rank_biserial = None
    if n1 > 0 and n2 > 0:
        rank_biserial = 1 - (2 * u) / (n1 * n2)

    return {
        "test": "Mann-Whitney U Test",
        "group_column": str(group_column),
        "groups": [str(groups[0]), str(groups[1])],
        "n_group1": int(n1),
        "n_group2": int(n2),
        "median_group1": _sf(np.median(g1), 4),
        "median_group2": _sf(np.median(g2), 4),
        "u_statistic": _sf(u, 4),
        "p_value": _sf(p, 6),
        "significance": _sig(p),
        "reject_null": _reject(p),
        # Effect size
        "rank_biserial": _sf(rank_biserial, 4),
        "rank_biserial_interpretation": _interpret_rank_biserial(rank_biserial),
        "interpretation": (
            f"Significant distributional difference between groups (p={_sf(p,6)})"
            if _reject(p) else
            f"No significant distributional difference (p={_sf(p,6)})"
        ),
    }


def kruskal_wallis(df, column, group_column):
    if column not in df.columns or group_column not in df.columns:
        raise ValueError("Column not found")
    sub = df[[column, group_column]].dropna()
    sub[column] = pd.to_numeric(sub[column], errors="coerce")
    sub = sub.dropna()

    groups_list = []
    group_names = []
    for name, grp in sub.groupby(group_column):
        vals = grp[column].to_numpy(dtype=float)
        if len(vals) >= 2:
            groups_list.append(vals)
            group_names.append(str(name))

    if len(groups_list) < 2:
        raise ValueError("Need at least 2 groups with >= 2 observations each")

    h, p = stats.kruskal(*groups_list)
    n_total = int(sub.shape[0])

    # Epsilon-squared (effect size for Kruskal-Wallis)
    epsilon_sq = None
    if n_total > 1 and len(groups_list) > 1:
        epsilon_sq = (h - len(groups_list) + 1) / (n_total - len(groups_list))

    return {
        "test": "Kruskal-Wallis H Test",
        "column": str(column),
        "group_column": str(group_column),
        "n_groups": int(len(groups_list)),
        "group_names": group_names,
        "h_statistic": _sf(h, 4),
        "p_value": _sf(p, 6),
        "significance": _sig(p),
        "reject_null": _reject(p),
        # Effect size
        "epsilon_squared": _sf(epsilon_sq, 4),
        "epsilon_squared_interpretation": _interpret_eta_sq(epsilon_sq),
        "interpretation": (
            f"Significant difference across groups (p={_sf(p,6)})"
            if _reject(p) else
            f"No significant difference across groups (p={_sf(p,6)})"
        ),
    }


# ============================================================
# Assumption tests
# ============================================================
def shapiro_wilk(df, column):
    if column not in df.columns:
        raise ValueError("Column not found")
    x = _numeric(df[column])
    if len(x) < 3:
        raise ValueError("Need at least 3 values")
    sample = x if len(x) <= 5000 else np.random.RandomState(42).choice(x, 5000, replace=False)

    w, p = stats.shapiro(sample)
    return {
        "test": "Shapiro-Wilk Normality Test",
        "column": str(column),
        "n": int(len(sample)),
        "w_statistic": _sf(w, 6),
        "p_value": _sf(p, 6),
        "is_normal": bool(p > 0.05),
        "significance": _sig(p),
        "interpretation": (
            f"Data is normally distributed (p={_sf(p,6)})"
            if p > 0.05 else
            f"Data is NOT normally distributed (p={_sf(p,6)}) — consider non-parametric tests"
        ),
    }


def levene_test(df, column, group_column):
    if column not in df.columns or group_column not in df.columns:
        raise ValueError("Column not found")
    sub = df[[column, group_column]].dropna()
    sub[column] = pd.to_numeric(sub[column], errors="coerce")
    sub = sub.dropna()

    groups_list = []
    for name, grp in sub.groupby(group_column):
        vals = grp[column].to_numpy(dtype=float)
        if len(vals) >= 2:
            groups_list.append(vals)

    if len(groups_list) < 2:
        raise ValueError("Need at least 2 groups with >= 2 values")

    stat, p = stats.levene(*groups_list)
    return {
        "test": "Levene's Test for Equal Variances",
        "column": str(column),
        "group_column": str(group_column),
        "n_groups": int(len(groups_list)),
        "w_statistic": _sf(stat, 4),
        "p_value": _sf(p, 6),
        "equal_variances": bool(p > 0.05),
        "significance": _sig(p),
        "interpretation": (
            f"Variances are equal across groups (p={_sf(p,6)})"
            if p > 0.05 else
            f"Variances are NOT equal (p={_sf(p,6)}) — use Welch's t-test"
        ),
    }


# ============================================================
# Correlation & Post-hoc Tests
# ============================================================
def correlation(df, column_a, column_b):
    if column_a not in df.columns or column_b not in df.columns:
        raise ValueError("Column not found")

    sub = df[[column_a, column_b]].apply(pd.to_numeric, errors="coerce").dropna()
    if len(sub) < 3:
        raise ValueError("Need at least 3 valid paired observations")

    a = sub[column_a].to_numpy(dtype=float)
    b = sub[column_b].to_numpy(dtype=float)

    pearson_r, pearson_p = pearsonr(a, b)
    spearman_r, spearman_p = spearmanr(a, b)

    # r-squared (coefficient of determination)
    r_squared = float(pearson_r ** 2) if pearson_r is not None else None

    return {
        "test": "Pearson & Spearman Correlation",
        "column_a": str(column_a),
        "column_b": str(column_b),
        "n": int(len(sub)),
        "pearson_r": _sf(pearson_r, 4),
        "pearson_p": _sf(pearson_p, 6),
        "spearman_r": _sf(spearman_r, 4),
        "spearman_p": _sf(spearman_p, 6),
        "significance": _sig(pearson_p),
        "reject_null": _reject(pearson_p),
        # Effect size
        "r_squared": _sf(r_squared, 4),
        "r_squared_interpretation": _interpret_r2(r_squared),
        "interpretation": (
            f"Significant correlation found (p={_sf(pearson_p,6)})"
            if _reject(pearson_p) else
            f"No significant correlation found (p={_sf(pearson_p,6)})"
        ),
    }


def tukey_hsd(df, column, group_column):
    if column not in df.columns or group_column not in df.columns:
        raise ValueError("Column not found")

    sub = df[[column, group_column]].dropna()
    sub[column] = pd.to_numeric(sub[column], errors="coerce")
    sub = sub.dropna()

    if len(sub) < 3:
        raise ValueError("Need at least 3 valid rows")

    try:
        tukey = pairwise_tukeyhsd(endog=sub[column], groups=sub[group_column], alpha=0.05)
    except Exception as e:
        raise ValueError(f"Tukey HSD failed to run: {str(e)}")

    comparisons = []
    for row in tukey.summary().data[1:]:
        comparisons.append({
            "group1": str(row[0]),
            "group2": str(row[1]),
            "meandiff": _sf(row[2], 4),
            "p_adj": _sf(row[3], 6),
            "significant": bool(row[6]),
        })

    return {
        "test": "Tukey HSD Post-hoc Test",
        "column": str(column),
        "group_column": str(group_column),
        "n_groups": int(sub[group_column].nunique()),
        "comparisons": comparisons,
        "interpretation": "Tukey HSD test completed. Check the 'significant' flag for each pair.",
    }