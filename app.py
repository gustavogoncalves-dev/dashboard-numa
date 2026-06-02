import os
import streamlit as st
import pandas as pd
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()

from api.google_ads import fetch_campaign_stats as fetch_google
from api.meta_ads import fetch_campaign_stats as fetch_meta
from api.google_analytics import fetch_session_stats as fetch_ga4
from utils.data import merge_ads_with_ga4, aggregate_by_platform, aggregate_by_date
import components.pre_click as pre_click
import components.post_click as post_click
import components.cross_data as cross_data
import components.executive as executive

st.set_page_config(
    page_title="Media Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    /* KPI cards */
    [data-testid="metric-container"] {
        background: #1A1F2E;
        border: 1px solid #2A3050;
        border-radius: 10px;
        padding: 20px 16px 14px 16px;
    }
    [data-testid="metric-container"]:hover { border-color: #4F8EF7; }
    [data-testid="stMetricValue"] { font-size: 1.55rem !important; font-weight: 700 !important; }
    [data-testid="stMetricLabel"] { font-size: 0.78rem !important; color: #9CA3AF !important; font-weight: 500 !important; text-transform: uppercase; letter-spacing: 0.04em; }

    /* Sidebar */
    [data-testid="stSidebar"] { border-right: 1px solid #2A3050; }
    [data-testid="stSidebar"] .stButton > button { border-radius: 8px; font-weight: 600; }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid #2A3050; }
    .stTabs [data-baseweb="tab"] { font-weight: 600; font-size: 0.9rem; border-radius: 6px 6px 0 0; }

    /* Dataframe */
    [data-testid="stDataFrame"] { border-radius: 8px; border: 1px solid #2A3050 !important; }

    /* Section header */
    .section-header {
        font-size: 1rem;
        font-weight: 700;
        color: #9CA3AF;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 16px;
        margin-top: 8px;
    }

    /* Status badge */
    .badge-ok   { display:inline-block; background:#064E3B; color:#34D399; border-radius:20px; padding:2px 10px; font-size:0.75rem; font-weight:600; }
    .badge-warn { display:inline-block; background:#78350F; color:#FCD34D; border-radius:20px; padding:2px 10px; font-size:0.75rem; font-weight:600; }
    .badge-err  { display:inline-block; background:#7F1D1D; color:#FCA5A5; border-radius:20px; padding:2px 10px; font-size:0.75rem; font-weight:600; }

    /* Divider */
    hr { border-color: #2A3050 !important; margin: 1rem 0; }
</style>
""", unsafe_allow_html=True)


# ── Sidebar ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📊 Media Dashboard")
    st.caption("Análise integrada de mídia paga + GA4")
    st.divider()

    col_s, col_e = st.columns(2)
    start_date = col_s.date_input("De", value=date.today() - timedelta(days=30))
    end_date = col_e.date_input("Até", value=date.today() - timedelta(days=1))

    platforms = st.multiselect(
        "Plataformas",
        options=["Google Ads", "Meta Ads"],
        default=["Google Ads", "Meta Ads"],
    )

    st.divider()
    run_btn = st.button("🔄  Atualizar dados", type="primary", use_container_width=True)

    if "source_status" in st.session_state:
        st.divider()
        st.caption("**Status das fontes**")
        for src, info in st.session_state["source_status"].items():
            if info["status"] == "ok":
                st.markdown(f'<span class="badge-ok">✓ {src} — {info["rows"]} linhas</span>', unsafe_allow_html=True)
            elif info["status"] == "empty":
                st.markdown(f'<span class="badge-warn">○ {src} — sem dados</span>', unsafe_allow_html=True)
            else:
                st.markdown(f'<span class="badge-err">✗ {src} — erro</span>', unsafe_allow_html=True)
            st.write("")

    # Diagnóstico de casamento Ads ↔ GA4
    if "df_merged" in st.session_state:
        _dm = st.session_state["df_merged"]
        if not _dm.empty and "_merge_method" in _dm.columns:
            _method = _dm["_merge_method"].iloc[0]
            _labels = {
                "exact":            ("badge-ok",   "GA4 ↔ Ads: nome exato"),
                "normalized":       ("badge-warn", "GA4 ↔ Ads: nome normalizado"),
                "date_proportional":("badge-warn", "GA4 ↔ Ads: distribuição por data"),
                "none":             ("badge-err",  "GA4 ↔ Ads: sem match"),
            }
            _cls, _txt = _labels.get(_method, ("badge-err", f"GA4 ↔ Ads: {_method}"))
            st.divider()
            st.markdown(f'<span class="{_cls}">{_txt}</span>', unsafe_allow_html=True)
            if _method in ("date_proportional", "none"):
                with st.expander("Ver campanhas (Ads vs GA4)", expanded=False):
                    _dga4 = st.session_state.get("df_ga4", pd.DataFrame())
                    if not _dga4.empty and "campaign_name" in _dga4.columns:
                        st.caption("Nomes no GA4 (`sessionCampaignName`)")
                        st.dataframe(_dga4[["campaign_name"]].drop_duplicates().sort_values("campaign_name"), hide_index=True)
                    if "campaign_name" in _dm.columns:
                        st.caption("Nomes nos Ads")
                        st.dataframe(_dm[["platform","campaign_name"]].drop_duplicates().sort_values("campaign_name"), hide_index=True)


# ── Data loading ─────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_all(start: date, end: date, plats: tuple):
    frames = []
    errors = []
    status = {}

    if "Google Ads" in plats:
        try:
            df_g = fetch_google(start, end)
            if df_g.empty:
                status["Google Ads"] = {"status": "empty", "rows": 0}
            else:
                frames.append(df_g)
                status["Google Ads"] = {"status": "ok", "rows": len(df_g)}
        except Exception as e:
            errors.append(f"Google Ads: {e}")
            status["Google Ads"] = {"status": "error", "rows": 0}

    if "Meta Ads" in plats:
        try:
            df_m = fetch_meta(start, end)
            if df_m.empty:
                status["Meta Ads"] = {"status": "empty", "rows": 0}
            else:
                frames.append(df_m)
                status["Meta Ads"] = {"status": "ok", "rows": len(df_m)}
        except Exception as e:
            errors.append(f"Meta Ads: {e}")
            status["Meta Ads"] = {"status": "error", "rows": 0}

    ads_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    ga4_id = os.environ.get("GA4_PROPERTY_ID", "")
    if not ga4_id or ga4_id == "123456789":
        ga4_df = pd.DataFrame()
        status["GA4"] = {"status": "empty", "rows": 0}
    else:
        try:
            ga4_df = fetch_ga4(start, end)
            if ga4_df.empty:
                status["GA4"] = {"status": "empty", "rows": 0}
            else:
                status["GA4"] = {"status": "ok", "rows": len(ga4_df)}
        except Exception as e:
            errors.append(f"GA4: {e}")
            ga4_df = pd.DataFrame()
            status["GA4"] = {"status": "error", "rows": 0}

    merged = merge_ads_with_ga4(ads_df, ga4_df)
    return merged, ga4_df, errors, status


# ── Initial state ─────────────────────────────────────────────
if not run_btn and "df_merged" not in st.session_state:
    st.markdown('<p class="section-header">Bem-vindo ao Media Dashboard</p>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    col1.info("**Pré-clique**\nInvestimento, impressões, cliques, CTR, CPC por campanha")
    col2.info("**Pós-clique (GA4)**\nSessões, engajamento, conversões, receita e ROAS")
    col3.info("**Cruzamento**\nAnálise integrada: custo vs. resultado real no site")
    st.markdown("---")
    st.caption("Configure o período e as plataformas na barra lateral, depois clique em **🔄 Atualizar dados**.")
    st.stop()

if run_btn:
    _fetch_all.clear()
    with st.spinner("Buscando dados..."):
        df_merged, df_ga4, errors, source_status = _fetch_all(start_date, end_date, tuple(platforms))
    st.session_state["df_merged"] = df_merged
    st.session_state["df_ga4"] = df_ga4
    st.session_state["source_status"] = source_status
    if errors:
        for err in errors:
            st.error(err)

df_merged = st.session_state.get("df_merged", pd.DataFrame())
df_ga4 = st.session_state.get("df_ga4", pd.DataFrame())

if df_merged.empty and df_ga4.empty:
    st.warning("Nenhum dado retornado para o período selecionado. Verifique as credenciais e o intervalo de datas.")
    st.stop()

# Agrupamentos (só se tiver ads)
df_platform = aggregate_by_platform(df_merged) if not df_merged.empty else pd.DataFrame()
df_daily = aggregate_by_date(df_merged) if not df_merged.empty else pd.DataFrame()

# GA4 display: usa merged se tiver sessões cruzadas, senão usa ga4 puro
has_merged_ga4 = (
    not df_merged.empty
    and "sessions" in df_merged.columns
    and df_merged["sessions"].notna().any()
    and df_merged["sessions"].sum() > 0
)
if has_merged_ga4:
    _ga4_display = df_merged
elif not df_ga4.empty:
    _ga4_display = df_ga4.copy()
    for _c in ["spend", "impressions", "clicks", "conversions"]:
        if _c not in _ga4_display.columns:
            _ga4_display[_c] = 0.0
else:
    _ga4_display = pd.DataFrame()


# ── Tabs ──────────────────────────────────────────────────────
tab_exec, tab_detail, tab_week = st.tabs([
    "📊  Executivo",
    "🔍  Detalhe por campanha",
    "📅  Semana vs Semana",
])

with tab_exec:
    executive.render(df_merged, _ga4_display, df_daily, df_platform)

with tab_detail:
    if df_merged.empty:
        st.info("Sem dados de mídia paga para o período.")
    else:
        pre_click.render_kpis(df_merged)
        st.divider()
        pre_click.render_full_funnel(df_merged, _ga4_display)
        st.divider()
        pre_click.render_channel_performance(df_daily, df_platform)
        st.divider()
        pre_click.render_campaign_table(df_merged)
        if not _ga4_display.empty:
            st.divider()
            post_click.render_kpis(_ga4_display)
            col1, col2 = st.columns(2)
            with col1:
                post_click.render_funnel(_ga4_display)
            with col2:
                post_click.render_engagement_chart(_ga4_display)
            post_click.render_revenue_table(_ga4_display)
        if has_merged_ga4:
            st.divider()
            cross_data.render_ctr_vs_engagement(df_merged)
            cross_data.render_efficiency_scatter(df_merged)
            cross_data.render_cost_per_session(df_merged)

with tab_week:
    if df_merged.empty:
        st.info("Sem dados para o comparativo semanal.")
    else:
        pre_click.render_week_over_week(df_merged)

# ── Footer ────────────────────────────────────────────────────
st.divider()
col_f1, col_f2, col_f3 = st.columns(3)
col_f1.caption(f"Período: {start_date} → {end_date}")
col_f2.caption(f"Linhas ads: {len(df_merged)} | Linhas GA4: {len(df_ga4)}")
col_f3.caption("Cache: 1h | Atualizado manualmente")
