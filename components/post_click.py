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
    if df.empty or "sessions" not in df.columns:
        st.info("Sem dados do GA4 para o período selecionado.")
        return

    df_filled = df.fillna(0)
    total_sessions    = df_filled["sessions"].sum()
    avg_engagement    = df_filled["engagement_rate"].mean()
    avg_bounce        = df_filled["bounce_rate"].mean()
    avg_duration      = df_filled["avg_session_duration"].mean()
    avg_pages         = df_filled["pages_per_session"].mean()
    total_conversions = df_filled["ga4_conversions"].sum()
    total_revenue     = df_filled["revenue"].sum()
    total_spend       = df_filled.get("spend", pd.Series([0])).sum() if "spend" in df_filled.columns else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Sessões (GA4)",        fmt_number(total_sessions))
    col2.metric("Taxa de Engajamento",  fmt_pct(avg_engagement))
    col3.metric("Taxa de Rejeição",     fmt_pct(avg_bounce))
    col4.metric("Duração Média",        f"{avg_duration:.0f}s")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Páginas / Sessão",     f"{avg_pages:.2f}")
    col6.metric("Conversões (GA4)",     fmt_number(total_conversions))
    col7.metric("Receita Total",        fmt_currency(total_revenue))
    if total_spend > 0:
        roas = total_revenue / total_spend
        col8.metric("ROAS Global", f"{roas:.2f}x")
    else:
        custo_por_sessao = 0.0
        col8.metric("Sessões / dia", f"{total_sessions / max((df_filled['date'].nunique() if 'date' in df_filled.columns else 1), 1):.1f}")


def render_engagement_chart(df: pd.DataFrame) -> None:
    if df.empty or "sessions" not in df.columns:
        return
    st.subheader("Sessões e Engajamento por campanha")
    agg = (
        df.fillna(0)
        .groupby(["campaign_name"] + (["platform"] if "platform" in df.columns else []), as_index=False)
        .agg(sessions=("sessions", "sum"), engagement_rate=("engagement_rate", "mean"))
    )
    agg = agg.sort_values("sessions", ascending=True).tail(15)

    color_col = "platform" if "platform" in agg.columns else None
    fig = px.bar(
        agg,
        x="sessions",
        y="campaign_name",
        color=color_col,
        orientation="h",
        labels={"sessions": "Sessões", "campaign_name": "Campanha", "platform": "Plataforma"},
        color_discrete_map=_COLORS,
    )
    fig.update_layout(**_LAYOUT)
    st.plotly_chart(fig, use_container_width=True)


def render_funnel(df: pd.DataFrame) -> None:
    if df.empty or "sessions" not in df.columns:
        return
    st.subheader("Funil de conversão")
    df_filled = df.fillna(0)

    stages = ["Sessões (GA4)", "Conversões (GA4)"]
    values = [df_filled["sessions"].sum(), df_filled["ga4_conversions"].sum()]

    if "impressions" in df_filled.columns and df_filled["impressions"].sum() > 0:
        stages = ["Impressões", "Cliques", "Sessões (GA4)", "Conversões (GA4)"]
        values = [
            df_filled["impressions"].sum(),
            df_filled["clicks"].sum(),
            df_filled["sessions"].sum(),
            df_filled["ga4_conversions"].sum(),
        ]

    fig = px.funnel(x=values, y=stages, color_discrete_sequence=["#4F8EF7"])
    fig.update_layout(**_LAYOUT)
    st.plotly_chart(fig, use_container_width=True)


def render_revenue_table(df: pd.DataFrame) -> None:
    if df.empty or "revenue" not in df.columns:
        return
    st.subheader("Receita e métricas por campanha")

    group_cols = ["campaign_name"]
    if "platform" in df.columns:
        group_cols = ["platform", "campaign_name"]

    agg_dict = dict(
        sessions=("sessions", "sum"),
        ga4_conversions=("ga4_conversions", "sum"),
        revenue=("revenue", "sum"),
        avg_bounce=("bounce_rate", "mean"),
        avg_pages=("pages_per_session", "mean"),
    )
    if "spend" in df.columns:
        agg_dict["spend"] = ("spend", "sum")

    agg = df.fillna(0).groupby(group_cols, as_index=False).agg(**agg_dict)

    if "spend" in agg.columns:
        agg["roas"]    = (agg["revenue"] / agg["spend"].replace(0, 1)).round(2)
        agg["cpa_ga4"] = (agg["spend"] / agg["ga4_conversions"].replace(0, 1)).round(2)

    agg = agg.sort_values("revenue", ascending=False)

    rename = {
        "platform": "Plataforma", "campaign_name": "Campanha",
        "spend": "Investimento (R$)", "sessions": "Sessões",
        "ga4_conversions": "Conv. GA4", "revenue": "Receita (R$)",
        "roas": "ROAS", "cpa_ga4": "CPA GA4 (R$)",
        "avg_bounce": "Bounce (%)", "avg_pages": "Págs/Sessão",
    }
    st.dataframe(agg.rename(columns=rename), use_container_width=True, hide_index=True)
