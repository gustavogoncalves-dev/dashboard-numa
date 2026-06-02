import streamlit as st
import plotly.express as px
import pandas as pd
from utils.data import fmt_currency, fmt_pct

_COLORS = {"Google Ads": "#4285F4", "Meta Ads": "#FF6B35"}

def _L(**kw) -> dict:
    cfg = dict(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font_color="#C9D1D9", margin=dict(t=36, b=20, l=0, r=8),
        legend=dict(orientation="h", y=1.15, bgcolor="rgba(0,0,0,0)", font_size=11),
        hoverlabel=dict(bgcolor="#161B22", bordercolor="#30363D", font_size=12),
        xaxis=dict(gridcolor="#21262D", tickfont_size=11, zeroline=False),
        yaxis=dict(gridcolor="#21262D", tickfont_size=11, zeroline=False),
    )
    cfg.update(kw)
    return cfg

_LAYOUT = _L()  # backwards compat


def render_efficiency_scatter(df: pd.DataFrame) -> None:
    if df.empty or "sessions" not in df.columns:
        return
    st.subheader("Eficiência: Investimento vs. Sessões por campanha")

    agg = (
        df.fillna(0)
        .groupby(["platform", "campaign_name"], as_index=False)
        .agg(
            spend=("spend", "sum"),
            sessions=("sessions", "sum"),
            conversions=("conversions", "sum"),
            revenue=("revenue", "sum"),
        )
    )
    agg = agg[agg["spend"] > 0]
    if agg.empty:
        return
    agg["roas"] = (agg["revenue"] / agg["spend"]).round(2)

    fig = px.scatter(
        agg, x="spend", y="sessions",
        size="conversions", color="platform",
        hover_name="campaign_name",
        hover_data={"roas": ":.2f", "spend": ":.2f", "sessions": True},
        labels={"spend": "Investimento (R$)", "sessions": "Sessões (GA4)", "platform": "Plataforma"},
        color_discrete_map=_COLORS,
        size_max=40,
    )
    fig.update_layout(**_LAYOUT)
    st.plotly_chart(fig, use_container_width=True)


def render_ctr_vs_engagement(df: pd.DataFrame) -> None:
    if df.empty or "engagement_rate" not in df.columns:
        return
    st.subheader("CTR (pré-clique) vs. Taxa de Engajamento (pós-clique)")

    agg = (
        df.fillna(0)
        .groupby(["platform", "campaign_name"], as_index=False)
        .agg(ctr=("ctr", "mean"), engagement_rate=("engagement_rate", "mean"), spend=("spend", "sum"))
    )
    agg = agg[agg["spend"] > 0]
    if agg.empty:
        return

    avg_ctr = agg["ctr"].mean()
    avg_eng = agg["engagement_rate"].mean()

    fig = px.scatter(
        agg, x="ctr", y="engagement_rate",
        size="spend", color="platform",
        hover_name="campaign_name",
        labels={"ctr": "CTR médio (%)", "engagement_rate": "Engajamento GA4 (%)", "platform": "Plataforma"},
        color_discrete_map=_COLORS,
        size_max=40,
    )
    fig.add_hline(y=avg_eng, line_dash="dot", line_color="#9CA3AF", opacity=0.6,
                  annotation_text="Média engajamento", annotation_font_color="#9CA3AF")
    fig.add_vline(x=avg_ctr, line_dash="dot", line_color="#9CA3AF", opacity=0.6,
                  annotation_text="Média CTR", annotation_font_color="#9CA3AF")
    fig.update_layout(**_LAYOUT)
    st.plotly_chart(fig, use_container_width=True)
    st.caption("↗ Quadrante superior direito = alto CTR **e** alto engajamento pós-clique — as campanhas mais eficientes.")


def render_cost_per_session(df: pd.DataFrame) -> None:
    if df.empty or "sessions" not in df.columns:
        return
    st.subheader("Custo por Sessão (GA4) por campanha")

    agg = (
        df.fillna(0)
        .groupby(["platform", "campaign_name"], as_index=False)
        .agg(spend=("spend", "sum"), sessions=("sessions", "sum"))
    )
    agg = agg[agg["sessions"] > 0]
    if agg.empty:
        return
    agg["cost_per_session"] = (agg["spend"] / agg["sessions"]).round(2)
    agg = agg.sort_values("cost_per_session", ascending=False).head(20)

    fig = px.bar(
        agg, x="campaign_name", y="cost_per_session", color="platform",
        labels={"cost_per_session": "Custo/Sessão (R$)", "campaign_name": "Campanha", "platform": "Plataforma"},
        color_discrete_map=_COLORS,
    )
    fig.update_layout(**_LAYOUT, xaxis_tickangle=-35)
    st.plotly_chart(fig, use_container_width=True)
