import math

import pandas as pd


def _score(series: pd.Series, lower_is_better: bool = False) -> pd.Series:
    if series.nunique(dropna=True) <= 1:
        return pd.Series(3, index=series.index, dtype="int64")
    scores = series.rank(method="average", pct=True).map(
        lambda percentile: min(5, max(1, math.ceil(percentile * 5)))
    ).astype("int64")
    return 6 - scores if lower_is_better else scores


def _segment(recency: int, frequency: int, monetary: int) -> str:
    if recency >= 4 and frequency >= 4 and monetary >= 4:
        return "Champions"
    if recency >= 3 and frequency >= 4:
        return "Loyal customers"
    if recency >= 4 and frequency <= 1:
        return "New customers"
    if recency >= 4 and frequency >= 2:
        return "Potential loyalists"
    if recency <= 2 and frequency >= 3:
        return "At risk"
    if recency <= 2 and frequency <= 2:
        return "Hibernating"
    return "Regular customers"


def analyze_customer_data(
    df: pd.DataFrame,
    customer_column: str,
    date_column: str,
    monetary_column: str,
    transaction_column: str | None = None,
) -> dict:
    selected_columns = [customer_column, date_column, monetary_column]
    if transaction_column:
        selected_columns.append(transaction_column)
    if len(set(selected_columns)) != len(selected_columns):
        raise ValueError("Choose a different column for each field.")

    missing_columns = [column for column in selected_columns if column not in df.columns]
    if missing_columns:
        raise ValueError("One or more selected columns are not in this dataset.")
    if df.empty:
        raise ValueError("This dataset has no rows to analyze.")
    if pd.api.types.is_numeric_dtype(df[date_column]):
        raise ValueError("Purchase date must be a date/time column, not a numeric column.")

    customers = df[customer_column].astype("string").str.strip()
    dates = pd.to_datetime(df[date_column], errors="coerce", utc=True).dt.tz_localize(None)
    monetary = pd.to_numeric(df[monetary_column], errors="coerce")
    valid = customers.notna() & customers.ne("") & dates.notna() & monetary.notna()
    if not valid.any():
        raise ValueError("No valid rows found. Check the customer, date, and monetary columns.")

    data = pd.DataFrame({
        "customer": customers.loc[valid].astype(str).to_numpy(),
        "date": dates.loc[valid].to_numpy(),
        "monetary": monetary.loc[valid].astype(float).to_numpy(),
    }).reset_index(drop=True)

    if transaction_column:
        transactions = df.loc[valid, transaction_column].astype("string").str.strip().reset_index(drop=True)
        fallback_ids = pd.Series([f"missing-{index}" for index in range(len(data))])
        data["transaction"] = transactions.mask(transactions.isna() | transactions.eq(""), fallback_ids).astype(str)
        frequency = data.groupby("customer")["transaction"].nunique()
    else:
        frequency = data.groupby("customer").size()
    transaction_count = int(frequency.sum())

    customer_summary = data.groupby("customer").agg(
        last_purchase=("date", "max"),
        monetary=("monetary", "sum"),
    )
    customer_summary["frequency"] = frequency
    analysis_date = data["date"].max().normalize() + pd.Timedelta(days=1)
    customer_summary["recency"] = (analysis_date - customer_summary["last_purchase"]).dt.days.astype(int)
    customer_summary["r_score"] = _score(customer_summary["recency"], lower_is_better=True)
    customer_summary["f_score"] = _score(customer_summary["frequency"])
    customer_summary["m_score"] = _score(customer_summary["monetary"])
    customer_summary["score"] = (
        customer_summary["r_score"].astype(str)
        + customer_summary["f_score"].astype(str)
        + customer_summary["m_score"].astype(str)
    )
    customer_summary["segment"] = [
        _segment(int(row.r_score), int(row.f_score), int(row.m_score))
        for row in customer_summary.itertuples()
    ]

    data["activity_month"] = data["date"].dt.to_period("M").astype(str)
    first_purchase = data.groupby("customer")["activity_month"].min()
    data["cohort_month"] = data["customer"].map(first_purchase)
    monthly_activity = data[["customer", "activity_month", "cohort_month"]].drop_duplicates()
    activity_periods = pd.PeriodIndex(monthly_activity["activity_month"], freq="M")
    cohort_periods = pd.PeriodIndex(monthly_activity["cohort_month"], freq="M")
    monthly_activity["period"] = (
        (activity_periods.year * 12 + activity_periods.month)
        - (cohort_periods.year * 12 + cohort_periods.month)
    )
    activity_counts = monthly_activity.groupby(["cohort_month", "period"])["customer"].nunique()
    cohort_sizes = first_purchase.value_counts()
    latest_month = data["date"].max().to_period("M")
    latest_period_number = latest_month.year * 12 + latest_month.month
    cohort_rows = []
    for cohort in sorted(cohort_sizes.index)[-24:]:
        cohort_period = pd.Period(cohort, freq="M")
        elapsed = latest_period_number - (cohort_period.year * 12 + cohort_period.month)
        size = int(cohort_sizes[cohort])
        retention = []
        for period in range(12):
            if period > elapsed:
                retention.append(None)
            else:
                active = int(activity_counts.get((cohort, period), 0))
                retention.append(round(active / size * 100, 1) if size else 0.0)
        cohort_rows.append({"month": cohort, "customers": size, "retention": retention})

    segment_summary = customer_summary.groupby("segment").agg(
        customers=("segment", "size"),
        monetary=("monetary", "sum"),
    ).reset_index().sort_values(["customers", "monetary"], ascending=False)
    total_customers = len(customer_summary)
    segments = [{
        "name": row.segment,
        "customers": int(row.customers),
        "share_pct": round(int(row.customers) / total_customers * 100, 1),
        "monetary": round(float(row.monetary), 2),
    } for row in segment_summary.itertuples()]

    top_customers = customer_summary.sort_values(
        ["monetary", "frequency"], ascending=[False, False]
    ).head(20)
    customer_rows = [{
        "customer": str(customer),
        "recency_days": int(row.recency),
        "frequency": int(row.frequency),
        "monetary": round(float(row.monetary), 2),
        "score": row.score,
        "segment": row.segment,
    } for customer, row in top_customers.iterrows()]

    monetary_total = float(data["monetary"].sum())
    return {
        "summary": {
            "customers": total_customers,
            "transactions": transaction_count,
            "monetary_total": round(monetary_total, 2),
            "average_transaction_value": round(monetary_total / transaction_count, 2) if transaction_count else 0,
            "rows_used": len(data),
            "rows_skipped": int(len(df) - len(data)),
            "analysis_date": analysis_date.strftime("%Y-%m-%d"),
            "date_from": data["date"].min().strftime("%Y-%m-%d"),
            "date_to": data["date"].max().strftime("%Y-%m-%d"),
        },
        "cohort": {
            "periods": [f"M{period}" for period in range(12)],
            "rows": cohort_rows,
        },
        "rfm": {
            "segments": segments,
            "customers": customer_rows,
        },
    }