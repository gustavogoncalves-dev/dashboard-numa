import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from utils.data import fmt_currency, fmt_pct, fmt_number, get_week_comparison, agg_totals

_COLORS = {"Google Ads": "#4285F4", "Meta Ads": "#1877F2"}
_LAYOUT = dict(
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    font_color="#E8EAED",
    margin=dict(t=40, b=20, l=0, r=0),
    legend=dict(orientation="h", y=1.12, bgcolor="rgba(0,0,0,0)"),
)


def render_kpis(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("Sem dados de mídia para o período selecionado.")
        return

    total_impressions = df["impressions"].sum()
    total_clicks      = df["clicks"].sum()
    total_spend       = df["spend"].sum()
    total_conversions = df["conversions"].sum()
    overall_ctr  = total_clicks / total_impressions * 100 if total_impressions else 0
    overall_cpc  = total_spend / total_clicks if total_clicks else 0
    overall_cpa  = total_spend / total_conversions if total_conversions else 0
    overall_reach = df["reach"].sum() if "reach" in df.columns else None
    overall_freq  = df["frequency"].mean() if "frequency" in df.columns else None

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Impressões",        fmt_number(total_impressions))
    col2.metric("Cliques",           fmt_number(total_clicks))
    col3.metric("CTR",               fmt_pct(overall_ctr))
    col4.metric("Investimento",      fmt_currency(total_spend))

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("CPC Médio",         fmt_currency(overall_cpc))
    col6.metric("Conversões (Ads)",  fmt_number(total_conversions))
    col7.metric("CPA",               fmt_currency(overall_cpa))
    if overall_reach and overall_reach > 0:
        col8.metric("Alcance",       fmt_number(overall_reach))
    elif overall_freq and overall_freq > 0:
        col8.metric("Frequência Média", f"{overall_freq:.2f}x")


def render_spend_chart(df_daily: pd.DataFrame) -> None:
    if df_daily.empty:
        return
    st.subheader("Investimento diário por plataforma")
    fig = px.bar(
        df_daily, x="date", y="spend", color="platform",
        barmode="group",
        labels={"spend": "Investimento (R$)", "date": "Data", "platform": "Plataforma"},
        color_discrete_map=_COLORS,
    )
    fig.update_layout(**_LAYOUT)
    st.plotly_chart(fig, use_container_width=True)


def render_ctr_trend(df_daily: pd.DataFrame) -> None:
    if df_daily.empty:
        return
    st.subheader("CTR ao longo do tempo")
    fig = px.line(
        df_daily, x="date", y="ctr", color="platform", markers=True,
        labels={"ctr": "CTR (%)", "date": "Data", "platform": "Plataforma"},
        color_discrete_map=_COLORS,
    )
    fig.update_traces(line=dict(width=2.5), marker=dict(size=5))
    fig.update_layout(**_LAYOUT)
    st.plotly_chart(fig, use_container_width=True)


def render_platform_comparison(df_platform: pd.DataFrame) -> None:
    if df_platform.empty:
        return
    st.subheader("Comparativo entre plataformas")
    col1, col2 = st.columns(2)

    with col1:
        fig_spend = go.Figure(go.Pie(
            labels=df_platform["platform"],
            values=df_platform["spend"],
            hole=0.5,
            marker_colors=["#4285F4", "#1877F2"],
            textfont_size=13,
        ))
        fig_spend.update_layout(
            title=dict(text="Share de Investimento", font_color="#E8EAED"),
            paper_bgcolor="rgba(0,0,0,0)",
            font_color="#E8EAED",
            legend=dict(bgcolor="rgba(0,0,0,0)"),
            margin=dict(t=50, b=10, l=10, r=10),
        )
        st.plotly_chart(fig_spend, use_container_width=True)

    with col2:
        fig_imp = go.Figure(go.Pie(
            labels=df_platform["platform"],
            values=df_platform["impressions"],
            hole=0.5,
            marker_colors=["#4285F4", "#1877F2"],
            textfont_size=13,
        ))
        fig_imp.update_layout(
            title=dict(text="Share de Impressões", font_color="#E8EAED"),
            paper_bgcolor="rgba(0,0,0,0)",
            font_color="#E8EAED",
            legend=dict(bgcolor="rgba(0,0,0,0)"),
            margin=dict(t=50, b=10, l=10, r=10),
        )
        st.plotly_chart(fig_imp, use_container_width=True)


def render_full_funnel(df_ads: pd.DataFrame, ga4_display: pd.DataFrame) -> None:
    """Funil completo: Impressões → Cliques → Sessões GA4 → Conversões GA4."""
    if df_ads.empty:
        return

    impressions = df_ads["impressions"].sum()
    clicks      = df_ads["clicks"].sum()

    sessions  = 0.0
    ga4_conv  = 0.0
    if not ga4_display.empty:
        if "sessions" in ga4_display.columns:
            sessions = ga4_display["sessions"].sum()
        if "ga4_conversions" in ga4_display.columns:
            ga4_conv = ga4_display["ga4_conversions"].sum()

    stages = ["Impressões", "Cliques", "Sessões (GA4)", "Conversões (GA4)"]
    values = [impressions, clicks, sessions, ga4_conv]
    colors = ["#58A6FF", "#A371F7", "#D29922", "#3FB950"]

    # Drop stages with zero value (GA4 not configured)
    pairs = [(s, v, c) for s, v, c in zip(stages, values, colors) if v and v > 0]
    if len(pairs) < 2:
        return

    st.subheader("Funil completo — Impressão até Conversão")
    fig = go.Figure(go.Funnel(
        y=[s for s, v, c in pairs],
        x=[v for s, v, c in pairs],
        textposition="inside",
        textinfo="value+percent initial",
        marker=dict(color=[c for s, v, c in pairs]),
        connector=dict(line=dict(color="#21262D", width=1)),
    ))
    fig.update_layout(
        **_LAYOUT,
        height=320,
        margin=dict(t=20, b=10, l=0, r=0),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Conversion rate callouts between stages
    if len(pairs) >= 2:
        rate_cols = st.columns(len(pairs) - 1)
        labels = ["CTR (Imp→Clique)", "Click → Sessão", "Taxa de Conv. (Sess→Conv)"]
        for i, col in enumerate(rate_cols):
            if i < len(pairs) - 1:
                prev_v = pairs[i][1]
                next_v = pairs[i + 1][1]
                rate = next_v / prev_v * 100 if prev_v > 0 else 0
                col.metric(labels[i] if i < len(labels) else f"Etapa {i+1}→{i+2}", f"{rate:.2f}%")


def render_week_over_week(df: pd.DataFrame) -> None:
    """Comparativo: semana atual vs semana anterior."""
    curr, prev = get_week_comparison(df)
    if curr.empty or prev.empty:
        st.info("Dados insuficientes para comparar semanas (mínimo 14 dias de histórico).")
        return

    c = agg_totals(curr)
    p = agg_totals(prev)

    st.subheader("Semana atual vs Semana anterior")

    # KPI delta row
    metrics = [
        ("Impressões",   "impressions", fmt_number,   "normal"),
        ("Cliques",      "clicks",      fmt_number,   "normal"),
        ("CTR",          "ctr",         fmt_pct,      "normal"),
        ("Investimento", "spend",       fmt_currency, "normal"),
        ("Conversões",   "conversions", fmt_number,   "normal"),
        ("CPA",          "cpa",         fmt_currency, "inverse"),  # menor = melhor
        ("ROAS",         "roas",        lambda v: f"{v:.2f}x", "normal"),
    ]

    cols = st.columns(len(metrics))
    for col, (label, key, fmt, dc) in zip(cols, metrics):
        cv, pv = c[key], p[key]
        d_pct = (cv - pv) / pv * 100 if pv else 0
        d_str = f"{'+' if d_pct > 0 else ''}{d_pct:.1f}%"
        col.metric(label, fmt(cv), delta=f"{d_str} vs sem. ant.", delta_color=dc)

    # Bar chart comparison
    bar_data = [
        {"Métrica": "Impressões",  "Semana atual": c["impressions"] / 1000, "Semana ant.": p["impressions"] / 1000},
        {"Métrica": "Cliques",     "Semana atual": c["clicks"]      / 1000, "Semana ant.": p["clicks"]      / 1000},
        {"Métrica": "Sessões GA4", "Semana atual": c["sessions"]    / 1000, "Semana ant.": p["sessions"]    / 1000},
        {"Métrica": "Conversões",  "Semana atual": c["conversions"],        "Semana ant.": p["conversions"]       },
    ]
    df_bar = pd.DataFrame(bar_data)
    fig = px.bar(
        df_bar.melt(id_vars="Métrica", var_name="Período", value_name="Valor"),
        x="Métrica", y="Valor", color="Período", barmode="group",
        color_discrete_map={"Semana atual": "#58A6FF", "Semana ant.": "#30363D"},
        labels={"Valor": "Volume (K onde aplicável)", "Métrica": ""},
    )
    fig.update_layout(**_LAYOUT, height=280)
    st.plotly_chart(fig, use_container_width=True)


def render_campaign_table(df: pd.DataFrame) -> None:
    if df.empty:
        return
    st.subheader("Performance por campanha")

    agg = (
        df.groupby(["platform", "campaign_name"], as_index=False)
        .agg(
            impressions=("impressions", "sum"),
            clicks=("clicks", "sum"),
            spend=("spend", "sum"),
            conversions=("conversions", "sum"),
        )
    )
    agg["ctr"] = (agg["clicks"] / agg["impressions"].replace(0, 1) * 100).round(2)
    agg["cpc"] = (agg["spend"] / agg["clicks"].replace(0, 1)).round(2)
    agg["cpa"] = (agg["spend"] / agg["conversions"].replace(0, 1)).round(2)
    agg = agg.sort_values("spend", ascending=False)

    st.dataframe(
        agg.rename(columns={
            "platform":    "Plataforma",
            "campaign_name": "Campanha",
            "impressions": "Impressões",
            "clicks":      "Cliques",
            "ctr":         "CTR (%)",
            "spend":       "Investimento (R$)",
            "cpc":         "CPC (R$)",
            "conversions": "Conversões",
            "cpa":         "CPA (R$)",
        }),
        use_container_width=True,
        hide_index=True,
    )
