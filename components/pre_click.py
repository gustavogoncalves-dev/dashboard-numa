import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from utils.data import fmt_currency, fmt_pct, fmt_number

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
