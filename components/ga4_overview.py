"""
GA4 Overview — visão geral de conversões e receita por Origem / Mídia.

IMPORTANTE: usa o df_ga4 BRUTO (todas as origens, sem filtro de mídia paga).
É por isso que os totais aqui batem com a interface do GA4, enquanto a aba
Executivo mostra apenas o tráfego pago casado com os Ads.
"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from utils.data import fmt_currency, fmt_pct, fmt_number

_GREEN  = "#3FB950"
_BLUE   = "#4285F4"
_PURPLE = "#A371F7"
_TEXT   = "#E6EDF3"
_MUTED  = "#8B949E"
_CARD   = "#161B22"
_BORDER = "#21262D"


def _L(**kw) -> dict:
    base = dict(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font_color=_TEXT, margin=dict(t=28, b=16, l=0, r=8),
        hoverlabel=dict(bgcolor=_CARD, bordercolor=_BORDER, font_size=12),
        xaxis=dict(gridcolor=_BORDER, tickfont_size=11, zeroline=False),
        yaxis=dict(gridcolor=_BORDER, tickfont_size=11, zeroline=False),
    )
    base.update(kw)
    return base


def _channel_agg(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega o GA4 bruto por origem/mídia."""
    src = df["source"].fillna("(not set)").replace("", "(not set)") if "source" in df.columns else "(not set)"
    med = df["medium"].fillna("(none)").replace("", "(none)") if "medium" in df.columns else "(none)"
    g = df.assign(source=src, medium=med)

    agg = g.groupby(["source", "medium"], as_index=False).agg(
        sessions=("sessions", "sum"),
        conversions=("ga4_conversions", "sum"),
        revenue=("revenue", "sum"),
    )
    agg["canal"] = agg["source"] + " / " + agg["medium"]
    agg["conv_rate"] = (agg["conversions"] / agg["sessions"].replace(0, 1) * 100).round(2)
    total_rev = agg["revenue"].sum()
    total_cnv = agg["conversions"].sum()
    agg["rev_share"] = (agg["revenue"] / total_rev * 100).round(1) if total_rev > 0 else 0.0
    agg["cnv_share"] = (agg["conversions"] / total_cnv * 100).round(1) if total_cnv > 0 else 0.0
    return agg.sort_values("revenue", ascending=False)


def render(df_ga4: pd.DataFrame) -> None:
    if df_ga4 is None or df_ga4.empty or "source" not in df_ga4.columns:
        st.info("Sem dados do GA4 para o período. Verifique `GA4_PROPERTY_ID` e o intervalo de datas.")
        return

    df = df_ga4.fillna({"sessions": 0, "ga4_conversions": 0, "revenue": 0})
    agg = _channel_agg(df)

    total_sessions = df["sessions"].sum()
    total_conv     = df["ga4_conversions"].sum()
    total_revenue  = df["revenue"].sum()
    overall_cvr    = total_conv / total_sessions * 100 if total_sessions > 0 else 0.0
    n_channels     = len(agg)

    st.markdown(
        f"""<div style="padding:14px 20px;background:{_CARD};border-left:4px solid {_BLUE};
        border-radius:0 10px 10px 0;margin-bottom:18px;">
        <p style="font-size:11px;color:{_MUTED};text-transform:uppercase;letter-spacing:.1em;margin:0 0 4px">
        Visão geral GA4 · todas as origens</p>
        <p style="font-size:13px;color:{_TEXT};margin:0;line-height:1.5">
        Números <b>não filtrados</b> — incluem orgânico, direto, referral e e-mail, além da mídia paga.
        Por isso batem com a interface do GA4 e diferem da aba <b>Executivo</b> (apenas mídia paga casada com os Ads).</p>
        </div>""",
        unsafe_allow_html=True,
    )

    # ── KPIs ──────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sessões (GA4)",     fmt_number(total_sessions))
    c2.metric("Conversões (GA4)",  fmt_number(total_conv))
    c3.metric("Receita Total",     fmt_currency(total_revenue))
    c4.metric("Taxa de Conversão", fmt_pct(overall_cvr), help="Conversões / Sessões — média geral do período")

    st.divider()

    # ── Gráficos: conversões e receita por canal ──────────
    top = agg.head(12)
    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("**Conversões por origem / mídia**")
        d = top[top["conversions"] > 0].sort_values("conversions", ascending=True)
        if d.empty:
            st.caption("Sem conversões registradas no período.")
        else:
            fig = go.Figure(go.Bar(
                x=d["conversions"], y=d["canal"], orientation="h",
                marker_color=_PURPLE,
                text=[fmt_number(v) for v in d["conversions"]],
                textposition="auto",
            ))
            fig.update_layout(**_L(height=max(280, 26 * len(d)), showlegend=False,
                                   xaxis=dict(visible=False)))
            st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.markdown("**Receita por origem / mídia**")
        d = top[top["revenue"] > 0].sort_values("revenue", ascending=True)
        if d.empty:
            st.caption("Sem receita registrada no período.")
        else:
            fig = go.Figure(go.Bar(
                x=d["revenue"], y=d["canal"], orientation="h",
                marker_color=_GREEN,
                text=[fmt_currency(v) for v in d["revenue"]],
                textposition="auto",
            ))
            fig.update_layout(**_L(height=max(280, 26 * len(d)), showlegend=False,
                                   xaxis=dict(visible=False)))
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Tabela detalhada ──────────────────────────────────
    st.markdown("**Detalhamento por origem / mídia**")
    table = agg[[
        "source", "medium", "sessions", "conversions", "conv_rate",
        "revenue", "rev_share", "cnv_share",
    ]].copy()
    table["sessions"]    = table["sessions"].map(fmt_number)
    table["conversions"] = table["conversions"].map(fmt_number)
    table["conv_rate"]   = table["conv_rate"].map(lambda v: f"{v:.2f}%")
    table["revenue"]     = table["revenue"].map(fmt_currency)
    table["rev_share"]   = table["rev_share"].map(lambda v: f"{v:.1f}%")
    table["cnv_share"]   = table["cnv_share"].map(lambda v: f"{v:.1f}%")

    table = table.rename(columns={
        "source":      "Origem",
        "medium":      "Mídia",
        "sessions":    "Sessões",
        "conversions": "Conversões",
        "conv_rate":   "Taxa Conv.",
        "revenue":     "Receita",
        "rev_share":   "% Receita",
        "cnv_share":   "% Conv.",
    })
    st.dataframe(table, use_container_width=True, hide_index=True)
    st.caption(
        f"{n_channels} combinações de origem/mídia · "
        f"Receita total {fmt_currency(total_revenue)} · "
        f"{fmt_number(total_conv)} conversões · dados brutos do GA4 (sem filtro de mídia paga)"
    )
