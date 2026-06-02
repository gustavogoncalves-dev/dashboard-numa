import re
import pandas as pd

_NUMERIC_COLS = [
    "impressions", "clicks", "spend", "conversions", "reach",
    "sessions", "revenue", "frequency", "ctr", "cpc", "cpa",
    "ga4_conversions",  # incluído para _ensure_cols limpar NaN após merge
]

_GA4_METRICS = dict(
    sessions=("sessions", "sum"),
    engagement_rate=("engagement_rate", "mean"),
    bounce_rate=("bounce_rate", "mean"),
    avg_session_duration=("avg_session_duration", "mean"),
    pages_per_session=("pages_per_session", "mean"),
    ga4_conversions=("ga4_conversions", "sum"),
    revenue=("revenue", "sum"),
)


def _ensure_cols(df: pd.DataFrame) -> pd.DataFrame:
    for col in _NUMERIC_COLS:
        if col not in df.columns:
            df[col] = 0.0
        else:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    return df


def _norm(s) -> str:
    """Normaliza nome de campanha para matching fuzzy: minúsculo + separadores uniformes."""
    s = str(s).lower().strip()
    s = re.sub(r"[\s_\-]+", " ", s)   # espaços/underlines/traços → espaço
    s = re.sub(r"[^\w\s]", "", s)     # remove caracteres especiais
    return s.strip()


def _ga4_agg(ga4_df: pd.DataFrame, group_cols: list) -> pd.DataFrame:
    """Agrega ga4_df pelos group_cols usando apenas colunas disponíveis."""
    agg_kw = {k: v for k, v in _GA4_METRICS.items() if v[0] in ga4_df.columns}
    if not agg_kw:
        return pd.DataFrame()
    return ga4_df.groupby(group_cols, as_index=False).agg(**agg_kw)


_PAID_MEDIUMS = {"cpc", "cpm", "paid", "ppc", "paidsocial", "paid_social",
                  "paid-social", "paid_cpc", "cpv", "display"}


def _filter_paid(ga4_df: pd.DataFrame) -> pd.DataFrame:
    """
    Filtra GA4 para apenas sessões de mídia paga (medium=cpc/paid/etc).
    Garante que ROAS e Receita reflitam apenas tráfego originado por Ads.
    """
    if "medium" not in ga4_df.columns:
        return ga4_df
    paid = ga4_df[ga4_df["medium"].str.lower().str.strip().isin(_PAID_MEDIUMS)].copy()
    if paid.empty:
        # Fallback: remove tráfego "(not set)" e orgânico óbvio
        paid = ga4_df[
            (ga4_df["campaign_name"] != "(not set)") &
            (~ga4_df["medium"].str.lower().isin({"organic", "(none)", "referral", "email", "direct"}))
        ].copy()
    return paid if not paid.empty else ga4_df


def merge_ads_with_ga4(ads_df: pd.DataFrame, ga4_df: pd.DataFrame) -> pd.DataFrame:
    """
    Tenta casar dados de Ads com GA4 em 3 passes progressivos:
      1. Exact match em date + campaign_name
      2. Normalized match (case-insensitive, separadores uniformes)
      3. Fallback date-only: distribui totais diários do GA4 proporcionalmente ao spend
    Retorna também '_merge_method' como coluna de diagnóstico.
    """
    if ads_df.empty or ga4_df.empty:
        return ads_df

    # Filtra apenas tráfego de mídia paga antes de qualquer merge
    ga4_df = _filter_paid(ga4_df)

    # ── Pass 1: exact ─────────────────────────────────────────
    ga4_exact = _ga4_agg(ga4_df, ["date", "campaign_name"])
    result = ads_df.merge(ga4_exact, on=["date", "campaign_name"], how="left")
    match_rate = result["sessions"].notna().mean() if "sessions" in result.columns else 0.0

    if match_rate >= 0.05:
        result["_merge_method"] = "exact"
        return result

    # ── Pass 2: normalized names ───────────────────────────────
    ads_norm = ads_df.copy()
    ga4_norm = ga4_exact.copy()
    ads_norm["_norm"] = ads_norm["campaign_name"].apply(_norm)
    ga4_norm["_norm"] = ga4_norm["campaign_name"].apply(_norm)
    ga4_norm = ga4_norm.drop(columns=["campaign_name"])

    result2 = ads_norm.merge(ga4_norm, on=["date", "_norm"], how="left")
    result2 = result2.drop(columns=["_norm"])
    match_rate2 = result2["sessions"].notna().mean() if "sessions" in result2.columns else 0.0

    if match_rate2 >= 0.05:
        result2["_merge_method"] = "normalized"
        return result2

    # ── Pass 3: date-only proportional ────────────────────────
    # Distribui totais GA4 do dia proporcionalmente ao spend de cada campanha
    ga4_date = _ga4_agg(ga4_df, ["date"])
    if ga4_date.empty:
        ads_df["_merge_method"] = "none"
        return ads_df

    ads_w = ads_df.copy()
    daily_spend = ads_df.groupby("date")["spend"].transform("sum")
    ads_w["_weight"] = (ads_df["spend"] / daily_spend.replace(0, 1)).fillna(0)

    result3 = ads_w.merge(ga4_date, on="date", how="left")

    # Métricas de volume: multiplica pelo peso
    for col in ["sessions", "ga4_conversions", "revenue"]:
        if col in result3.columns:
            result3[col] = (result3[col] * result3["_weight"]).round(1)

    result3 = result3.drop(columns=["_weight"])
    result3["_merge_method"] = "date_proportional"
    return result3


def aggregate_by_platform(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = _ensure_cols(df.copy())
    has_ga4 = "ga4_conversions" in df.columns and df["ga4_conversions"].gt(0).any()

    agg_kw = dict(
        impressions=("impressions", "sum"),
        clicks=("clicks", "sum"),
        spend=("spend", "sum"),
        conversions=("conversions", "sum"),
        reach=("reach", "sum"),
        sessions=("sessions", "sum"),
        revenue=("revenue", "sum"),
    )
    if has_ga4:
        agg_kw["ga4_conversions"] = ("ga4_conversions", "sum")

    agg = df.groupby("platform", as_index=False).agg(**agg_kw)
    agg["ctr"]  = (agg["clicks"] / agg["impressions"].replace(0, 1) * 100).round(2)
    agg["cpc"]  = (agg["spend"]  / agg["clicks"].replace(0, 1)).round(2)

    eff_conv = agg["ga4_conversions"] if has_ga4 else agg["conversions"]
    agg["cpa"]  = (agg["spend"] / eff_conv.replace(0, 1)).round(2)
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
    agg["cpc"] = (agg["spend"]  / agg["clicks"].replace(0, 1)).round(2)
    agg["cpa"] = (agg["spend"]  / agg["conversions"].replace(0, 1)).round(2)
    return agg


def get_week_comparison(df: pd.DataFrame):
    if df.empty or "date" not in df.columns:
        return pd.DataFrame(), pd.DataFrame()
    df = _ensure_cols(df.copy())
    max_date = df["date"].max()
    if pd.isnull(max_date):
        return pd.DataFrame(), pd.DataFrame()
    curr_start = max_date - pd.Timedelta(days=6)
    prev_end   = curr_start - pd.Timedelta(days=1)
    prev_start = prev_end   - pd.Timedelta(days=6)
    curr = df[df["date"] >= curr_start].copy()
    prev = df[(df["date"] >= prev_start) & (df["date"] <= prev_end)].copy()
    return curr, prev


def agg_totals(df: pd.DataFrame) -> dict:
    df = _ensure_cols(df.copy())
    imp  = df["impressions"].sum()
    clk  = df["clicks"].sum()
    spd  = df["spend"].sum()
    conv = df["conversions"].sum()
    sess = df["sessions"].sum()        if "sessions"        in df.columns else 0.0
    rev  = df["revenue"].sum()         if "revenue"         in df.columns else 0.0
    ga4c = df["ga4_conversions"].sum() if "ga4_conversions" in df.columns else 0.0
    eff_conv = ga4c if ga4c > 0 else conv
    return {
        "impressions":     imp,
        "clicks":          clk,
        "spend":           spd,
        "conversions":     conv,
        "sessions":        sess,
        "revenue":         rev,
        "ga4_conversions": ga4c,
        "ctr":  clk / imp      * 100 if imp      > 0 else 0.0,
        "cpc":  spd / clk           if clk      > 0 else 0.0,
        "cpa":  spd / eff_conv      if eff_conv > 0 else 0.0,
        "roas": rev / spd           if spd      > 0 else 0.0,
    }


def fmt_currency(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_pct(value: float) -> str:
    return f"{value:.2f}%"


def fmt_number(value: float) -> str:
    return f"{value:,.0f}".replace(",", ".")
