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
    Casamento HÍBRIDO Ads ↔ GA4, linha a linha:
      1. Cada linha de Ads tenta casar por (date, campaign_name) exato; se não,
         por nome normalizado. As linhas casadas recebem os números REAIS do GA4.
      2. O GA4 que sobrar (campanhas não casadas — ex.: Meta enviando o ID em vez
         do nome) é distribuído entre as linhas de Ads não-casadas, proporcional
         ao spend de cada dia.
    Assim o Google (que casa por nome) mantém a receita real mesmo quando o Meta
    não casa, evitando que o método global zere campanhas legítimas.
    '_merge_method' indica o método predominante (exact / hybrid / date_proportional / none).
    """
    if ads_df.empty or ga4_df.empty:
        return ads_df

    ga4_paid = _filter_paid(ga4_df)
    ga4_g = _ga4_agg(ga4_paid, ["date", "campaign_name"])
    if ga4_g.empty:
        out = ads_df.copy()
        out["_merge_method"] = "none"
        return out

    vol_cols  = [c for c in ["sessions", "ga4_conversions", "revenue"] if c in ga4_g.columns]
    rate_cols = [c for c in ["engagement_rate", "bounce_rate",
                             "avg_session_duration", "pages_per_session"] if c in ga4_g.columns]
    metric_cols = vol_cols + rate_cols

    ga4_g = ga4_g.reset_index(drop=True)
    ga4_g["_norm"] = ga4_g["campaign_name"].apply(_norm)

    exact_lookup, norm_lookup = {}, {}
    for i, g in ga4_g.iterrows():
        exact_lookup[(g["date"], g["campaign_name"])] = i
        norm_lookup.setdefault((g["date"], g["_norm"]), i)

    ads = ads_df.copy().reset_index(drop=True)
    ads["_norm"] = ads["campaign_name"].apply(_norm)

    claimed = set()
    methods = []
    metric_data = {c: [] for c in metric_cols}

    for _, r in ads.iterrows():
        idx = exact_lookup.get((r["date"], r["campaign_name"]))
        method = "exact"
        if idx is None:
            idx = norm_lookup.get((r["date"], r["_norm"]))
            method = "normalized"
        if idx is None or idx in claimed:
            for c in metric_cols:
                metric_data[c].append(None)
            methods.append("unmatched")
        else:
            claimed.add(idx)
            g = ga4_g.loc[idx]
            for c in metric_cols:
                metric_data[c].append(g[c])
            methods.append(method)

    for c in metric_cols:
        ads[c] = metric_data[c]
    ads["_row_method"] = methods

    # ── Distribui o GA4 não-reivindicado entre as linhas unmatched ──
    unmatched_mask = ads["_row_method"] == "unmatched"
    leftover = ga4_g[~ga4_g.index.isin(claimed)]
    if unmatched_mask.any() and not leftover.empty and vol_cols:
        leftover_by_date = leftover.groupby("date")[vol_cols].sum()
        um = ads[unmatched_mask]
        daily_spend = um.groupby("date")["spend"].transform("sum").replace(0, 1)
        weight = (um["spend"] / daily_spend).fillna(0)
        for c in vol_cols:
            day_tot = um["date"].map(leftover_by_date[c]).fillna(0.0)
            ads.loc[unmatched_mask, c] = (day_tot * weight).round(1)

    matched_n = int(ads["_row_method"].isin(["exact", "normalized"]).sum())
    if matched_n == len(ads):
        method = "exact"
    elif matched_n > 0:
        method = "hybrid"
    else:
        method = "date_proportional"

    ads["_merge_method"] = method
    return ads.drop(columns=["_norm", "_row_method"])


# ── Atribuição GA4 → plataforma por origem/mídia ───────────────
_META_SOURCES = {"ig", "instagram", "facebook", "fb", "meta", "igshopping",
                 "l.instagram.com", "an", "audiencenetwork", "fb.com"}
_META_MEDIUMS = {"social", "paidsocial", "paid_social", "paid-social"}
_PAID_LIKE    = {"cpc", "ppc", "paid", "cpm", "cpv", "display"}


def _ga4_platform(source, medium) -> str | None:
    """Mapeia (source, medium) do GA4 para a plataforma de mídia paga."""
    s = str(source).lower().strip()
    m = str(medium).lower().strip()
    if s == "google" and m in _PAID_LIKE:
        return "Google Ads"
    if s in _META_SOURCES or m in _META_MEDIUMS:
        return "Meta Ads"
    if m in _PAID_LIKE:
        return "Outros (pago)"
    return None


def build_platform_performance(ads_df: pd.DataFrame, ga4_df: pd.DataFrame) -> pd.DataFrame:
    """
    Performance por plataforma combinando o LADO Ads (spend/impr/clicks) com o
    LADO GA4 (sessões/conversões/receita) atribuído por origem/mídia — sem
    depender de casar nomes de campanha. Isso preserva a receita real do Google
    mesmo quando o Ads vem agregado e o Meta envia ID em vez de nome.
    """
    ads_cols = ["impressions", "clicks", "spend", "conversions"]
    if ads_df is not None and not ads_df.empty and "platform" in ads_df.columns:
        a = _ensure_cols(ads_df.copy())
        ads_part = a.groupby("platform", as_index=False).agg(
            impressions=("impressions", "sum"),
            clicks=("clicks", "sum"),
            spend=("spend", "sum"),
            conversions=("conversions", "sum"),
        )
    else:
        ads_part = pd.DataFrame(columns=["platform"] + ads_cols)

    ga4_part = pd.DataFrame(columns=["platform", "sessions", "ga4_conversions", "revenue"])
    if ga4_df is not None and not ga4_df.empty and "source" in ga4_df.columns:
        paid = _filter_paid(ga4_df).copy()
        paid["platform"] = [_ga4_platform(s, m) for s, m in zip(paid["source"], paid["medium"])]
        paid = paid[paid["platform"].notna()]
        if not paid.empty:
            ga4_part = paid.groupby("platform", as_index=False).agg(
                sessions=("sessions", "sum"),
                ga4_conversions=("ga4_conversions", "sum"),
                revenue=("revenue", "sum"),
            )

    df = ads_part.merge(ga4_part, on="platform", how="outer")
    for c in ["impressions", "clicks", "spend", "conversions", "sessions", "ga4_conversions", "revenue"]:
        if c not in df.columns:
            df[c] = 0.0
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    df["ctr"]  = (df["clicks"]  / df["impressions"].replace(0, 1) * 100).round(2)
    df["cpc"]  = (df["spend"]   / df["clicks"].replace(0, 1)).round(2)
    df["cpa"]  = (df["spend"]   / df["ga4_conversions"].replace(0, 1)).round(2)
    df["roas"] = (df["revenue"] / df["spend"].replace(0, 1)).round(2)
    return df.sort_values("spend", ascending=False).reset_index(drop=True)


def build_daily_performance(ads_df: pd.DataFrame, ga4_df: pd.DataFrame) -> pd.DataFrame:
    """Série diária: spend (Ads) + receita/sessões (GA4 pago real) por data."""
    spend_part = pd.DataFrame(columns=["date", "spend"])
    if ads_df is not None and not ads_df.empty and "date" in ads_df.columns:
        a = _ensure_cols(ads_df.copy())
        spend_part = a.groupby("date", as_index=False).agg(spend=("spend", "sum"))

    rev_part = pd.DataFrame(columns=["date", "revenue", "sessions"])
    if ga4_df is not None and not ga4_df.empty and "source" in ga4_df.columns:
        paid = _filter_paid(ga4_df).copy()
        paid["platform"] = [_ga4_platform(s, m) for s, m in zip(paid["source"], paid["medium"])]
        paid = paid[paid["platform"].notna()]
        if not paid.empty and "date" in paid.columns:
            rev_part = paid.groupby("date", as_index=False).agg(
                revenue=("revenue", "sum"), sessions=("sessions", "sum"))

    df = spend_part.merge(rev_part, on="date", how="outer")
    for c in ["spend", "revenue", "sessions"]:
        if c not in df.columns:
            df[c] = 0.0
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    return df.sort_values("date").reset_index(drop=True)


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
