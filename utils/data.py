import pandas as pd

_NUMERIC_COLS = ["impressions", "clicks", "spend", "conversions", "reach",
                 "sessions", "revenue", "frequency", "ctr", "cpc", "cpa"]


def _ensure_cols(df: pd.DataFrame) -> pd.DataFrame:
    for col in _NUMERIC_COLS:
        if col not in df.columns:
            df[col] = 0.0
        else:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    return df


def merge_ads_with_ga4(ads_df: pd.DataFrame, ga4_df: pd.DataFrame) -> pd.DataFrame:
    if ads_df.empty or ga4_df.empty:
        return ads_df

    ga4_agg = (
        ga4_df
        .groupby(["date", "campaign_name"], as_index=False)
        .agg(
            sessions=("sessions", "sum"),
            engagement_rate=("engagement_rate", "mean"),
            bounce_rate=("bounce_rate", "mean"),
            avg_session_duration=("avg_session_duration", "mean"),
            pages_per_session=("pages_per_session", "mean"),
            ga4_conversions=("ga4_conversions", "sum"),
            revenue=("revenue", "sum"),
        )
    )
    return ads_df.merge(ga4_agg, on=["date", "campaign_name"], how="left")


def aggregate_by_platform(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = _ensure_cols(df.copy())
    agg = (
        df.groupby("platform", as_index=False)
        .agg(
            impressions=("impressions", "sum"),
            clicks=("clicks", "sum"),
            spend=("spend", "sum"),
            conversions=("conversions", "sum"),
            reach=("reach", "sum"),
            sessions=("sessions", "sum"),
            revenue=("revenue", "sum"),
        )
    )
    agg["ctr"] = (agg["clicks"] / agg["impressions"].replace(0, 1) * 100).round(2)
    agg["cpc"] = (agg["spend"] / agg["clicks"].replace(0, 1)).round(2)
    agg["cpa"] = (agg["spend"] / agg["conversions"].replace(0, 1)).round(2)
    agg["roas"] = (agg["revenue"] / agg["spend"].replace(0, 1)).round(2)
    return agg


def aggregate_by_date(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = _ensure_cols(df.copy())
    agg = (
        df.groupby(["date", "platform"], as_index=False)
        .agg(
            impressions=("impressions", "sum"),
            clicks=("clicks", "sum"),
            spend=("spend", "sum"),
            conversions=("conversions", "sum"),
            sessions=("sessions", "sum"),
            revenue=("revenue", "sum"),
        )
    )
    agg["ctr"] = (agg["clicks"] / agg["impressions"].replace(0, 1) * 100).round(2)
    agg["cpc"] = (agg["spend"] / agg["clicks"].replace(0, 1)).round(2)
    agg["cpa"] = (agg["spend"] / agg["conversions"].replace(0, 1)).round(2)
    return agg


def get_week_comparison(df: pd.DataFrame):
    """Returns (curr_week_df, prev_week_df) — last 7 days vs 7 days before that."""
    if df.empty or "date" not in df.columns:
        return pd.DataFrame(), pd.DataFrame()
    df = _ensure_cols(df.copy())
    max_date = df["date"].max()
    curr_start = max_date - pd.Timedelta(days=6)
    prev_end   = curr_start - pd.Timedelta(days=1)
    prev_start = prev_end   - pd.Timedelta(days=6)
    curr = df[df["date"] >= curr_start].copy()
    prev = df[(df["date"] >= prev_start) & (df["date"] <= prev_end)].copy()
    return curr, prev


def agg_totals(df: pd.DataFrame) -> dict:
    """Aggregate a DataFrame into a flat dict of total KPIs."""
    df = _ensure_cols(df.copy())
    imp  = df["impressions"].sum()
    clk  = df["clicks"].sum()
    spd  = df["spend"].sum()
    conv = df["conversions"].sum()
    sess = df["sessions"].sum() if "sessions" in df.columns else 0.0
    rev  = df["revenue"].sum()  if "revenue"  in df.columns else 0.0
    ga4c = df["ga4_conversions"].sum() if "ga4_conversions" in df.columns else 0.0
    return {
        "impressions": imp,
        "clicks":      clk,
        "spend":       spd,
        "conversions": conv,
        "sessions":    sess,
        "revenue":     rev,
        "ga4_conversions": ga4c,
        "ctr":  clk / imp  * 100 if imp  > 0 else 0.0,
        "cpc":  spd / clk        if clk  > 0 else 0.0,
        "cpa":  spd / conv       if conv > 0 else 0.0,
        "roas": rev / spd        if spd  > 0 else 0.0,
    }


def fmt_currency(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_pct(value: float) -> str:
    return f"{value:.2f}%"


def fmt_number(value: float) -> str:
    return f"{value:,.0f}".replace(",", ".")
