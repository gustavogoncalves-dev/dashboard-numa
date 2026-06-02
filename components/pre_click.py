import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from utils.data import fmt_currency, fmt_pct, fmt_number, get_week_comparison, agg_totals

# Google azul, Meta laranja — cores visivelmente distintas
_COLORS = {"Google Ads": "#4285F4", "Meta Ads": "#FF6B35"}
_GREEN  = "#3FB950"
_RED    = "#F85149"


def _L(**kw) -> dict:
    """Chart layout factory — evita conflitos de kwargs duplicados."""
    cfg = dict(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="#C9D1D9",
        margin=dict(t=36, b=20, l=0, r=8),
        legend=dict(orientation="h", y=1.15, bgcolor="rgba(0,0,0,0)", font_size=11),
        hoverlabel=dict(bgcolor="#161B22", bordercolor="#30363D", font_size=12),
        xaxis=dict(gridcolor="#21262D", tickfont_size=11, zeroline=False, linecolor="#30363D"),
        yaxis=dict(gridcolor="#21262D", tickfont_size=11, zeroline=False, linecolor="#30363D"),
    )
    cfg.update(kw)
    return cfg


# ── KPIs ──────────────────────────────────────────────────────
def render_kpis(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("Sem dados de mídia para o período selecionado.")
        return

    imp  = df["impressions"].sum()
    clk  = df["clicks"].sum()
    spd  = df["spend"].sum()
    conv = df["conversions"].sum() if "conversions" in df.columns else 0
    rev  = df["revenue"].sum()        if ("revenue" in df.columns and df["revenue"].notna().any()) else 0
    ga4c = df["ga4_conversions"].sum() if ("ga4_conversions" in df.columns and df["ga4_conversions"].notna().any()) else 0

    ctr  = clk / imp * 100  if imp  else 0
    cpc  = spd / clk        if clk  else 0
    eff_conv = ga4c if ga4c > 0 else conv
    cpa  = spd / eff_conv   if eff_conv else 0
    roas = rev / spd        if spd and rev else 0

    roas_color = _GREEN if roas >= 1 else (_RED if roas > 0 else "#8B949E")
    rev_block = (
        f'<div style="flex:1;background:#0d2137;border:1px solid #1f4068;border-radius:12px;padding:20px 22px;">'
        f'<p style="font-size:11px;color:#8B949E;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px">Receita (GA4)</p>'
        f'<p style="font-size:34px;font-weight:900;color:{_GREEN};letter-spacing:-.03em;margin:0">{fmt_currency(rev)}</p>'
        f'<p style="font-size:11px;color:#8B949E;margin-top:6px">Atribuída no período</p></div>'
    ) if rev > 0 else ""

    st.markdown(f"""
    <div style="display:flex;gap:12px;margin-bottom:16px;flex-wrap:wrap;">
      <div style="flex:1;min-width:160px;background:linear-gradient(135deg,#0d2137,#0a1628);
                  border:1px solid #1f4068;border-radius:12px;padding:20px 22px;">
        <p style="font-size:11px;color:#8B949E;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px">ROAS</p>
        <p style="font-size:38px;font-weight:900;color:{roas_color};letter-spacing:-.03em;margin:0">{roas:.2f}x</p>
        <p style="font-size:11px;color:#8B949E;margin-top:6px">Receita / Investimento</p>
      </div>
      <div style="flex:1;min-width:160px;background:#161B22;border:1px solid #21262D;border-radius:12px;padding:20px 22px;">
        <p style="font-size:11px;color:#8B949E;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px">CPA</p>
        <p style="font-size:38px;font-weight:900;color:#E6EDF3;letter-spacing:-.03em;margin:0">{fmt_currency(cpa)}</p>
        <p style="font-size:11px;color:#8B949E;margin-top:6px">Custo por conversão</p>
      </div>
      <div style="flex:1;min-width:160px;background:#161B22;border:1px solid #21262D;border-radius:12px;padding:20px 22px;">
        <p style="font-size:11px;color:#8B949E;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px">Investimento</p>
        <p style="font-size:38px;font-weight:900;color:#E6EDF3;letter-spacing:-.03em;margin:0">{fmt_currency(spd)}</p>
        <p style="font-size:11px;color:#8B949E;margin-top:6px">Total no período</p>
      </div>
      {rev_block}
    </div>
    """, unsafe_allow_html=True)

    # Sessões GA4 só aparece se houver dados cruzados
    has_sessions = ("sessions" in df.columns and df["sessions"].notna().any() and df["sessions"].sum() > 0)
    sess_total   = df["sessions"].sum() if has_sessions else 0

    n_cols = 6 if has_sessions else 5
    cols = st.columns(n_cols)
    cols[0].metric("Impressões",  fmt_number(imp))
    cols[1].metric("Cliques",     fmt_number(clk))
    cols[2].metric("CTR",         fmt_pct(ctr))
    if has_sessions:
        cols[3].metric("Sessões GA4", fmt_number(sess_total))
        cols[4].metric("Conv. GA4",   fmt_number(ga4c))
        cols[5].metric("CPC Médio",   fmt_currency(cpc))
    else:
        cols[3].metric("CPC Médio",   fmt_currency(cpc))
        cols[4].metric("Conversões",  fmt_number(eff_conv))


# ── Funil completo ────────────────────────────────────────────
def render_full_funnel(df_ads: pd.DataFrame, ga4_display: pd.DataFrame) -> None:
    if df_ads.empty:
        return

    imp  = df_ads["impressions"].sum()
    clk  = df_ads["clicks"].sum()
    sess = ga4_display["sessions"].sum()       if (not ga4_display.empty and "sessions" in ga4_display.columns) else 0
    ga4c = ga4_display["ga4_conversions"].sum() if (not ga4_display.empty and "ga4_conversions" in ga4_display.columns) else 0

    all_stages = [
        ("Impressões",     imp,  "#4285F4"),
        ("Cliques",        clk,  "#A371F7"),
        ("Sessões (GA4)",  sess, "#D29922"),
        ("Conversões",     ga4c, "#3FB950"),
    ]
    pairs = [(s, v, c) for s, v, c in all_stages if v and v > 0]
    if len(pairs) < 2:
        return

    st.markdown("**Funil completo — Impressão até Conversão**")
    fig = go.Figure(go.Funnel(
        y=[s for s, v, c in pairs],
        x=[v for s, v, c in pairs],
        textposition="inside",
        textinfo="value+percent initial",
        marker=dict(color=[c for s, v, c in pairs], line=dict(width=0)),
        connector=dict(line=dict(color="#21262D", width=2)),
    ))
    fig.update_layout(**_L(height=300, margin=dict(t=10, b=10, l=0, r=0), showlegend=False))
    st.plotly_chart(fig, use_container_width=True)

    # Taxas de conversão entre etapas
    rate_labels = ["CTR (Imp→Clique)", "Click→Sessão", "Sessão→Conversão", "Clique→Conversão"]
    comparisons = [(pairs[i][1], pairs[i+1][1]) for i in range(len(pairs)-1)]
    if len(pairs) == 4:
        comparisons.append((pairs[1][1], pairs[3][1]))

    cols = st.columns(len(comparisons))
    for col, (prev_v, next_v), lbl in zip(cols, comparisons, rate_labels):
        rate = next_v / prev_v * 100 if prev_v > 0 else 0
        col.metric(lbl, f"{rate:.2f}%")


# ── Canal: investimento + ROAS ────────────────────────────────
def render_channel_performance(df_daily: pd.DataFrame, df_platform: pd.DataFrame) -> None:
    if df_daily.empty:
        return

    col1, col2 = st.columns([3, 2])

    with col1:
        st.markdown("**Investimento diário por canal**")
        fig = px.area(
            df_daily, x="date", y="spend", color="platform",
            color_discrete_map=_COLORS,
            labels={"spend": "R$", "date": "", "platform": ""},
        )
        fig.update_traces(line_width=1.5)
        fig.update_layout(**_L(height=260))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        if df_platform.empty:
            return
        st.markdown("**ROAS e CPA por canal**")

        # Agrupa métricas dos canais verticalmente
        ch_data = df_platform.to_dict("records")
        for ch in ch_data:
            color = _COLORS.get(ch.get("platform", ""), "#58A6FF")
            roas_v = ch.get("roas", 0)
            cpa_v  = ch.get("cpa", 0)
            st.markdown(f"""
            <div style="background:#161B22;border:1px solid #21262D;border-radius:10px;
                        padding:14px 18px;margin-bottom:10px;">
              <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">
                <div style="width:9px;height:9px;border-radius:50%;background:{color}"></div>
                <span style="font-size:13px;font-weight:700;color:#E6EDF3">{ch.get('platform','')}</span>
              </div>
              <div style="display:flex;gap:20px;">
                <div>
                  <p style="font-size:10px;color:#8B949E;text-transform:uppercase;letter-spacing:.06em">ROAS</p>
                  <p style="font-size:22px;font-weight:800;color:{'#3FB950' if roas_v>=1 else '#F85149'}">{roas_v:.2f}x</p>
                </div>
                <div>
                  <p style="font-size:10px;color:#8B949E;text-transform:uppercase;letter-spacing:.06em">CPA</p>
                  <p style="font-size:22px;font-weight:800;color:#E6EDF3">{fmt_currency(cpa_v)}</p>
                </div>
                <div>
                  <p style="font-size:10px;color:#8B949E;text-transform:uppercase;letter-spacing:.06em">Invest.</p>
                  <p style="font-size:22px;font-weight:800;color:#E6EDF3">{fmt_currency(ch.get('spend',0))}</p>
                </div>
              </div>
            </div>
            """, unsafe_allow_html=True)


# ── Semana vs semana anterior ─────────────────────────────────
def render_week_over_week(df: pd.DataFrame) -> None:
    curr, prev = get_week_comparison(df)
    if curr.empty or prev.empty:
        st.info("Dados insuficientes para comparar semanas (mínimo 14 dias de histórico).")
        return

    c = agg_totals(curr)
    p = agg_totals(prev)

    st.markdown("**Semana atual vs Semana anterior**")

    metrics_def = [
        ("Impressões",   "impressions", fmt_number,              "normal"),
        ("Cliques",      "clicks",      fmt_number,              "normal"),
        ("CTR",          "ctr",         fmt_pct,                 "normal"),
        ("Investimento", "spend",       fmt_currency,            "normal"),
        ("Conversões",   "conversions", fmt_number,              "normal"),
        ("CPA",          "cpa",         fmt_currency,            "inverse"),
        ("ROAS",         "roas",        lambda v: f"{v:.2f}x",   "normal"),
    ]

    cols = st.columns(len(metrics_def))
    for col, (label, key, fmt_fn, dc) in zip(cols, metrics_def):
        cv, pv = c[key], p[key]
        d_pct = (cv - pv) / pv * 100 if pv else 0
        d_str = f"{'+' if d_pct > 0 else ''}{d_pct:.1f}%"
        col.metric(label, fmt_fn(cv), delta=f"{d_str} vs sem. ant.", delta_color=dc)

    # Variação % como waterfall — mesma escala para todas as métricas
    changes = []
    for label, key, _, inverse in metrics_def:
        pv = p[key]
        if not pv:
            continue
        pct = (c[key] - pv) / pv * 100
        better = (pct < 0) if inverse else (pct > 0)
        changes.append({"Métrica": label, "Var %": pct, "cor": _GREEN if better else _RED})

    df_chg = pd.DataFrame(changes)
    if df_chg.empty:
        return
    fig = go.Figure(go.Bar(
        x=df_chg["Métrica"],
        y=df_chg["Var %"],
        marker_color=df_chg["cor"].tolist(),
        text=df_chg["Var %"].apply(lambda v: f"{v:+.1f}%"),
        textposition="outside",
    ))
    fig.add_hline(y=0, line_color="#30363D", line_width=1)
    fig.update_layout(**_L(
        height=240,
        showlegend=False,
        yaxis_title="Variação % WoW",
        margin=dict(t=10, b=20, l=0, r=8),
    ))
    st.plotly_chart(fig, use_container_width=True)


# ── Tabela de campanhas ───────────────────────────────────────
def render_campaign_table(df: pd.DataFrame) -> None:
    if df.empty:
        return
    if "platform" not in df.columns or "campaign_name" not in df.columns:
        return

    df = df.copy()
    for _c in ["impressions", "clicks", "spend", "conversions"]:
        if _c not in df.columns:
            df[_c] = 0.0

    has_sessions = "sessions"        in df.columns and df["sessions"].gt(0).any()
    has_ga4_conv = "ga4_conversions" in df.columns and df["ga4_conversions"].notna().any()
    has_revenue  = "revenue"         in df.columns and df["revenue"].gt(0).any()

    agg_dict: dict = dict(
        impressions=("impressions", "sum"),
        clicks=("clicks", "sum"),
        spend=("spend", "sum"),
        conversions=("conversions", "sum"),
    )
    if has_sessions:  agg_dict["sessions"]        = ("sessions",        "sum")
    if has_ga4_conv:  agg_dict["ga4_conversions"] = ("ga4_conversions", "sum")
    if has_revenue:   agg_dict["revenue"]          = ("revenue",         "sum")

    agg = df.groupby(["platform", "campaign_name"], as_index=False).agg(**agg_dict)

    # CPA — .where() substitui zeros por NaN; divisão por NaN retorna NaN (seguro)
    if has_ga4_conv:
        safe_conv = agg["ga4_conversions"].where(agg["ga4_conversions"] > 0)
    else:
        safe_conv = agg["conversions"].where(agg["conversions"] > 0)
    agg["cpa"] = (agg["spend"] / safe_conv).round(2)

    if has_revenue:
        agg["roas"] = (agg["revenue"] / agg["spend"].where(agg["spend"] > 0)).round(2)

    agg["ctr"] = (agg["clicks"] / agg["impressions"].where(agg["impressions"] > 0) * 100).round(2)
    agg = agg.sort_values("spend", ascending=False)

    # Monta rename e column_config na ordem desejada
    cols_order = ["platform", "campaign_name", "spend"]
    if has_sessions:
        cols_order.append("sessions")
    if has_ga4_conv:
        cols_order.append("ga4_conversions")
    cols_order += ["cpa"]
    if has_revenue:
        cols_order += ["revenue", "roas"]
    cols_order += ["impressions", "clicks", "ctr"]

    agg = agg[[c for c in cols_order if c in agg.columns]]

    rename = {
        "platform":        "Plataforma",
        "campaign_name":   "Campanha",
        "spend":           "Invest. R$",
        "sessions":        "Sessões GA4",
        "ga4_conversions": "Conv. GA4",
        "conversions":     "Conv. Ads",
        "cpa":             "CPA R$",
        "revenue":         "Receita R$",
        "roas":            "ROAS",
        "impressions":     "Impressões",
        "clicks":          "Cliques",
        "ctr":             "CTR %",
    }

    col_cfg = {
        "Invest. R$": st.column_config.NumberColumn(format="R$ %.2f"),
        "CPA R$":     st.column_config.NumberColumn(format="R$ %.2f"),
        "Receita R$": st.column_config.NumberColumn(format="R$ %.2f"),
        "ROAS":       st.column_config.NumberColumn(format="%.2fx"),
        "CTR %":      st.column_config.NumberColumn(format="%.2f%%"),
        "Sessões GA4":st.column_config.NumberColumn(format="%d"),
        "Conv. GA4":  st.column_config.NumberColumn(format="%d"),
    }

    st.markdown("**Performance por campanha** — CPA calculado sobre conversões GA4")
    st.dataframe(
        agg.rename(columns=rename),
        use_container_width=True,
        hide_index=True,
        column_config=col_cfg,
    )
