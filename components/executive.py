"""
CEO Full-Funnel Dashboard Component
Narrativa: Investimento → Awareness → Consideração → Conversão → Receita → ROI
"""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from utils.data import fmt_currency, fmt_number, fmt_pct

_GREEN  = "#3FB950"
_BLUE   = "#4285F4"
_ORANGE = "#FF6B35"
_PURPLE = "#A371F7"
_YELLOW = "#D29922"
_RED    = "#F85149"
_ACCENT = "#58A6FF"
_TEXT   = "#E6EDF3"
_MUTED  = "#8B949E"
_CARD   = "#161B22"
_BORDER = "#21262D"

_COLORS = {"Google Ads": _BLUE, "Meta Ads": _ORANGE}


def _L(**kw) -> dict:
    base = dict(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font_color=_TEXT, margin=dict(t=24, b=16, l=0, r=8),
        hoverlabel=dict(bgcolor=_CARD, bordercolor=_BORDER, font_size=12),
        xaxis=dict(gridcolor=_BORDER, tickfont_size=11, zeroline=False),
        yaxis=dict(gridcolor=_BORDER, tickfont_size=11, zeroline=False),
    )
    base.update(kw)
    return base


def _pull_metrics(df_merged: pd.DataFrame, ga4_display: pd.DataFrame) -> dict:
    """Extrai todos os KPIs necessários de um único lugar."""
    spd = df_merged["spend"].sum() if not df_merged.empty else 0
    imp = df_merged["impressions"].sum() if not df_merged.empty else 0
    clk = df_merged["clicks"].sum() if not df_merged.empty else 0

    # GA4 — prioriza ga4_display, fallback para colunas no df_merged
    def _col(df, col):
        return df[col].sum() if (not df.empty and col in df.columns and df[col].notna().any()) else 0

    sess = _col(ga4_display, "sessions") or _col(df_merged, "sessions")
    ga4c = _col(ga4_display, "ga4_conversions") or _col(df_merged, "ga4_conversions")
    rev  = _col(ga4_display, "revenue")         or _col(df_merged, "revenue")

    roas      = rev / spd          if spd > 0 and rev > 0 else 0
    cpa       = spd / ga4c         if ga4c > 0 else 0
    cpm       = spd / imp * 1000   if imp  > 0 else 0
    cpc       = spd / clk          if clk  > 0 else 0
    cpv       = spd / sess         if sess > 0 else 0
    ctr       = clk / imp  * 100   if imp  > 0 else 0
    c2s       = sess / clk * 100   if clk  > 0 else 0
    cvr       = ga4c / sess * 100  if sess > 0 else 0
    aov       = rev  / ga4c        if ga4c > 0 else 0

    return dict(
        spd=spd, imp=imp, clk=clk, sess=sess, ga4c=ga4c, rev=rev,
        roas=roas, cpa=cpa, cpm=cpm, cpc=cpc, cpv=cpv,
        ctr=ctr, c2s=c2s, cvr=cvr, aov=aov,
    )


# ── 1. Veredicto ─────────────────────────────────────────────
def _render_verdict(m: dict) -> None:
    roas = m["roas"]
    if roas >= 3:
        msg   = f"Máquina eficiente: cada R$ 1,00 investido retornou R$ {roas:.2f}"
        color = _GREEN
        icon  = "●"
    elif roas >= 1.5:
        msg   = f"Retorno positivo: ROAS {roas:.2f}x — {fmt_currency(m['rev'])} gerados sobre {fmt_currency(m['spd'])} investidos"
        color = _ACCENT
        icon  = "●"
    elif roas >= 1:
        msg   = f"Equilíbrio frágil: ROAS {roas:.2f}x — margem estreita, atenção ao CPA ({fmt_currency(m['cpa'])})"
        color = _YELLOW
        icon  = "●"
    elif roas > 0:
        msg   = f"Alerta: ROAS {roas:.2f}x — cada R$1,00 retorna apenas R${roas:.2f}. Revisar mix e eficiência."
        color = _RED
        icon  = "●"
    else:
        msg   = "Sem dados de receita no período. Configure os eventos de conversão no GA4."
        color = _MUTED
        icon  = "○"

    ga4c_txt = f"{fmt_number(m['ga4c'])} conversões GA4" if m["ga4c"] > 0 else "sem conversões GA4"

    st.markdown(f"""
    <div style="padding:22px 26px;background:{_CARD};border-left:4px solid {color};
                border-radius:0 10px 10px 0;margin-bottom:20px;">
      <p style="font-size:11px;color:{_MUTED};text-transform:uppercase;
                letter-spacing:.1em;margin-bottom:8px">{icon} Veredicto do período</p>
      <p style="font-size:1.35rem;font-weight:700;color:{_TEXT};line-height:1.5;margin:0">{msg}</p>
      <p style="font-size:11px;color:{_MUTED};margin-top:10px">{ga4c_txt} · Atribuição last-click via GA4</p>
    </div>""", unsafe_allow_html=True)


# ── 2. Três números ───────────────────────────────────────────
def _render_three_numbers(m: dict) -> None:
    rc = _GREEN if m["roas"] >= 1.5 else (_YELLOW if m["roas"] >= 1 else (_RED if m["roas"] > 0 else _MUTED))
    rev_txt = fmt_currency(m["rev"]) if m["rev"] > 0 else "—"

    st.markdown(f"""
    <div style="display:flex;gap:12px;margin-bottom:4px;flex-wrap:wrap;">
      <div style="flex:1;min-width:180px;background:{_CARD};border:1px solid {_BORDER};
                  border-radius:12px;padding:22px 24px;">
        <p style="font-size:10px;color:{_MUTED};text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px">
          Investimento</p>
        <p style="font-size:2rem;font-weight:900;color:{_TEXT};font-variant-numeric:tabular-nums;margin:0">
          {fmt_currency(m['spd'])}</p>
        <p style="font-size:11px;color:{_MUTED};margin-top:6px">Capital alocado no período</p>
      </div>
      <div style="flex:1;min-width:180px;background:{_CARD};
                  border:1px solid {'#3FB95044' if m['rev']>0 else _BORDER};
                  border-radius:12px;padding:22px 24px;">
        <p style="font-size:10px;color:{_MUTED};text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px">
          Receita (GA4)</p>
        <p style="font-size:2rem;font-weight:900;color:{_GREEN if m['rev']>0 else _MUTED};
                  font-variant-numeric:tabular-nums;margin:0">{rev_txt}</p>
        <p style="font-size:11px;color:{_MUTED};margin-top:6px">Last-click · AOV {fmt_currency(m['aov']) if m['aov']>0 else '—'}</p>
      </div>
      <div style="flex:1;min-width:180px;background:{_CARD};border:1px solid {rc}44;
                  border-radius:12px;padding:22px 24px;">
        <p style="font-size:10px;color:{_MUTED};text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px">
          ROAS</p>
        <p style="font-size:2rem;font-weight:900;color:{rc};font-variant-numeric:tabular-nums;margin:0">
          {m['roas']:.2f}x</p>
        <p style="font-size:11px;color:{_MUTED};margin-top:6px">CPA: {fmt_currency(m['cpa']) if m['cpa']>0 else '—'}</p>
      </div>
    </div>""", unsafe_allow_html=True)


# ── 3. Funil ──────────────────────────────────────────────────
def _render_funnel(m: dict) -> None:
    stages = []
    if m["imp"]  > 0: stages.append(("Impressões",    m["imp"],  f"CPM {fmt_currency(m['cpm'])}",  "#4285F4"))
    if m["clk"]  > 0: stages.append(("Cliques",       m["clk"],  f"CPC {fmt_currency(m['cpc'])}",  "#A371F7"))
    if m["sess"] > 0: stages.append(("Sessões GA4",   m["sess"], f"Custo/visita {fmt_currency(m['cpv'])}", "#D29922"))
    if m["ga4c"] > 0: stages.append(("Conversões",    m["ga4c"], f"CPA {fmt_currency(m['cpa'])}",  "#3FB950"))

    if len(stages) < 2:
        st.info("Dados insuficientes para o funil. Verifique se GA4 está conectado.")
        return

    st.markdown("**Do awareness à conversão**")

    maxv = max(s[1] for s in stages)

    # Taxas entre etapas + gargalo (maior queda)
    rate_lbls = ["CTR", "Clique → Sessão", "Sessão → Conversão"]
    rates = [
        (stages[i + 1][1] / stages[i][1] * 100 if stages[i][1] > 0 else 0)
        for i in range(len(stages) - 1)
    ]
    worst = min(range(len(rates)), key=lambda i: rates[i]) if len(rates) > 1 else -1

    html = ['<div style="margin:6px 0 2px;">']
    for i, (name, val, sub, color) in enumerate(stages):
        w = 38 + 62 * (val / maxv)   # afunila mas mantém largura mínima legível
        html.append(
            f'<div style="display:flex;justify-content:center;">'
            f'<div style="width:{w:.1f}%;min-width:260px;'
            f'background:linear-gradient(90deg,{color}1f,{color});'
            f'border:1px solid {color}55;border-radius:12px;padding:13px 20px;margin:5px 0;'
            f'display:flex;align-items:center;justify-content:space-between;gap:14px;'
            f'box-shadow:0 1px 2px rgba(0,0,0,.25);">'
            f'<span style="font-size:11px;font-weight:700;color:#fff;text-transform:uppercase;'
            f'letter-spacing:.05em;white-space:nowrap;">{name}</span>'
            f'<span style="font-size:1.5rem;font-weight:900;color:#fff;'
            f'font-variant-numeric:tabular-nums;line-height:1;">{fmt_number(val)}</span>'
            f'<span style="font-size:11px;color:#ffffffcc;white-space:nowrap;">{sub}</span>'
            f'</div></div>'
        )
        if i < len(stages) - 1:
            r, is_worst = rates[i], (i == worst)
            lbl = rate_lbls[i] if i < len(rate_lbls) else ""
            bg = "#3a1414" if is_worst else "#161b22"
            fg = "#FCA5A5" if is_worst else _MUTED
            tag = f"⚠ gargalo · {lbl}" if is_worst else lbl
            html.append(
                f'<div style="display:flex;justify-content:center;align-items:center;gap:8px;margin:1px 0;">'
                f'<span style="color:{_MUTED};font-size:12px;">▼</span>'
                f'<span style="background:{bg};color:{fg};border:1px solid {fg}33;'
                f'border-radius:20px;padding:2px 12px;font-size:11px;font-weight:700;'
                f'font-variant-numeric:tabular-nums;">{r:.1f}%&nbsp; ·&nbsp; {tag}</span>'
                f'</div>'
            )
    html.append('</div>')
    st.markdown("".join(html), unsafe_allow_html=True)

    # Receita separada (unidade diferente — dinheiro, não pessoas)
    if m["rev"] > 0:
        st.markdown(f"""
        <div style="display:flex;gap:12px;margin-top:12px;">
          <div style="flex:1;background:#0d2137;border:1px solid #3FB95044;border-radius:10px;
                      padding:16px 20px;display:flex;align-items:center;gap:20px;">
            <div>
              <p style="font-size:10px;color:{_MUTED};text-transform:uppercase;letter-spacing:.07em;margin-bottom:4px">
                Receita Gerada</p>
              <p style="font-size:1.6rem;font-weight:900;color:{_GREEN};font-variant-numeric:tabular-nums;margin:0">
                {fmt_currency(m['rev'])}</p>
            </div>
            <div style="width:1px;height:40px;background:{_BORDER}"></div>
            <div>
              <p style="font-size:10px;color:{_MUTED};text-transform:uppercase;letter-spacing:.07em;margin-bottom:4px">ROAS</p>
              <p style="font-size:1.6rem;font-weight:900;color:{_GREEN};margin:0">{m['roas']:.2f}x</p>
            </div>
            <div style="width:1px;height:40px;background:{_BORDER}"></div>
            <div>
              <p style="font-size:10px;color:{_MUTED};text-transform:uppercase;letter-spacing:.07em;margin-bottom:4px">Ticket Médio</p>
              <p style="font-size:1.6rem;font-weight:900;color:{_TEXT};margin:0">{fmt_currency(m['aov'])}</p>
            </div>
          </div>
        </div>""", unsafe_allow_html=True)


# ── 4. Tendência de eficiência ────────────────────────────────
def _render_efficiency_trend(df_daily: pd.DataFrame) -> None:
    if df_daily.empty:
        return

    daily = df_daily.groupby("date", as_index=False).agg(
        spend=("spend", "sum"),
        revenue=("revenue", "sum"),
    ) if "revenue" in df_daily.columns else df_daily.groupby("date", as_index=False).agg(
        spend=("spend", "sum"),
    )

    has_rev = "revenue" in daily.columns and daily["revenue"].gt(0).any()

    if has_rev:
        daily["roas"] = (daily["revenue"] / daily["spend"].where(daily["spend"] > 0)).fillna(0)
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=daily["date"], y=daily["roas"],
            mode="lines+markers",
            name="ROAS diário",
            line=dict(color=_GREEN, width=2.5),
            marker=dict(size=4),
            fill="tozeroy",
            fillcolor="rgba(63,185,80,0.08)",
        ))
        fig.add_hline(y=1, line_dash="dot", line_color=_RED, opacity=0.6,
                      annotation_text="Break-even", annotation_font_size=10,
                      annotation_font_color=_RED)
        yaxis_title = "ROAS"
    else:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=daily["date"], y=daily["spend"],
            name="Investimento",
            marker_color="rgba(88,166,255,0.67)",
        ))
        yaxis_title = "Investimento (R$)"

    fig.update_layout(**_L(
        height=240,
        showlegend=False,
        yaxis_title=yaxis_title,
        margin=dict(t=8, b=16, l=0, r=8),
    ))
    st.markdown("**Eficiência ao longo do tempo**")
    st.plotly_chart(fig, use_container_width=True)


# ── 5. Onde o dinheiro trabalha ───────────────────────────────
def _render_channel_revenue(df_platform: pd.DataFrame) -> None:
    if df_platform.empty:
        return

    has_rev = "revenue" in df_platform.columns and df_platform["revenue"].gt(0).any()
    metric  = "revenue" if has_rev else "spend"
    label   = "Receita (R$)" if has_rev else "Investimento (R$)"

    df_sorted = df_platform.sort_values(metric, ascending=True)

    # Texto da barra: valor + ROAS numa única string (sem anotações separadas)
    if has_rev and "roas" in df_platform.columns:
        bar_text = df_sorted.apply(
            lambda r: f"{fmt_currency(r[metric])}  ·  ROAS {r['roas']:.2f}x", axis=1
        ).tolist()
    else:
        bar_text = df_sorted[metric].apply(fmt_currency).tolist()

    fig = go.Figure(go.Bar(
        x=df_sorted[metric],
        y=df_sorted["platform"],
        orientation="h",
        marker_color=[_COLORS.get(p, _ACCENT) for p in df_sorted["platform"]],
        text=bar_text,
        textposition="inside",
        insidetextanchor="middle",
        textfont=dict(size=13, color="#FFFFFF"),
    ))

    fig.update_layout(**_L(
        height=200,
        showlegend=False,
        xaxis_title=label,
        xaxis=dict(visible=False),
        margin=dict(t=8, b=8, l=0, r=8),
    ))
    st.markdown(f"**{'Receita' if has_rev else 'Investimento'} por canal**")
    st.plotly_chart(fig, use_container_width=True)


# ── 6. Decisões (The Ask) ─────────────────────────────────────
def _render_the_ask(m: dict, df_platform: pd.DataFrame) -> None:
    decisions = []

    # Decisão 1: escalar ou cortar com base no ROAS
    if m["roas"] >= 3:
        potential = m["rev"] * 0.25
        decisions.append({
            "icon": "🚀", "color": _GREEN,
            "title": "Escalar investimento",
            "body":  f"ROAS de {m['roas']:.2f}x confirma eficiência comprovada. Aumentar budget em +25% pode gerar "
                     f"~{fmt_currency(potential)} de receita incremental sem alterar o CAC.",
            "ask":   f"Aprovar aumento de {fmt_currency(m['spd']*0.25)} em verba paga",
        })
    elif m["roas"] >= 1.5:
        decisions.append({
            "icon": "📈", "color": _ACCENT,
            "title": "Otimizar antes de escalar",
            "body":  f"ROAS {m['roas']:.2f}x é positivo mas ainda tem espaço. Reduzir CPA de {fmt_currency(m['cpa'])} "
                     f"em 15% antes de escalar pode elevar ROAS para {m['roas']*1.15:.2f}x.",
            "ask":   "Revisar lances e audiências antes do próximo ciclo de budget",
        })
    elif m["roas"] > 0 and m["roas"] < 1:
        decisions.append({
            "icon": "🛑", "color": _RED,
            "title": "Revisar mix urgente",
            "body":  f"ROAS de {m['roas']:.2f}x significa prejuízo a cada real investido. Congelar campanhas com CPA "
                     f"acima de {fmt_currency(m['cpa']*1.3)} e redirecionar para canais rentáveis.",
            "ask":   f"Cortar {fmt_currency(m['spd']*0.3)} das campanhas menos eficientes imediatamente",
        })

    # Decisão 2: realocar entre canais
    if not df_platform.empty and "roas" in df_platform.columns and len(df_platform) >= 2:
        df_sorted = df_platform.sort_values("roas", ascending=False)
        best  = df_sorted.iloc[0]
        worst = df_sorted.iloc[-1]
        if best["roas"] > 0 and worst["roas"] >= 0 and best["roas"] > worst["roas"] * 1.3:
            move = worst["spend"] * 0.3
            est  = move * best["roas"]
            decisions.append({
                "icon": "🔀", "color": _YELLOW,
                "title": f"Realocar de {worst['platform']} → {best['platform']}",
                "body":  f"{best['platform']} entrega ROAS {best['roas']:.2f}x vs {worst['roas']:.2f}x do {worst['platform']}. "
                         f"Mover {fmt_currency(move)} pode gerar ~{fmt_currency(est)} adicionais.",
                "ask":   f"Realocar {fmt_currency(move)} para {best['platform']} no próximo ciclo",
            })

    # Decisão 3: gargalo do funil
    stages = [("CTR", m["ctr"], 2.0), ("Click→Sessão", m["c2s"], 60.0), ("Conv. Rate", m["cvr"], 2.0)]
    bottlenecks = [(lbl, val, ref) for lbl, val, ref in stages if val > 0 and val < ref * 0.5]
    if bottlenecks:
        lbl, val, ref = bottlenecks[0]
        decisions.append({
            "icon": "⚠️", "color": _YELLOW,
            "title": f"Gargalo crítico: {lbl} abaixo do benchmark",
            "body":  f"{lbl} de {val:.2f}% está menos da metade do benchmark ({ref:.1f}%). "
                     f"Dobrar essa taxa sem mudar spend poderia duplicar as conversões.",
            "ask":   f"Auditar landing page e UX — potencial de +{fmt_number(m['ga4c'])} conversões/período",
        })

    if not decisions:
        decisions.append({
            "icon": "📊", "color": _MUTED,
            "title": "Aguardando dados suficientes",
            "body":  "Conecte GA4 e certifique-se de ter ao menos 14 dias de dados para gerar recomendações.",
            "ask":   "Verificar integração GA4 e UTMs",
        })

    st.markdown("**Decisões recomendadas**")
    cols = st.columns(min(len(decisions), 3))
    for col, d in zip(cols, decisions[:3]):
        col.markdown(f"""
        <div style="background:{_CARD};border:1px solid {d['color']}33;border-radius:12px;
                    padding:18px;height:100%;">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">
            <span style="font-size:18px">{d['icon']}</span>
            <p style="font-size:13px;font-weight:700;color:{_TEXT};margin:0">{d['title']}</p>
          </div>
          <p style="font-size:12px;color:{_MUTED};line-height:1.6;margin-bottom:12px">{d['body']}</p>
          <div style="border-top:1px solid {_BORDER};padding-top:10px">
            <p style="font-size:11px;color:{d['color']};font-weight:700;margin:0">→ {d['ask']}</p>
          </div>
        </div>""", unsafe_allow_html=True)


# ── Entry point ───────────────────────────────────────────────
def render(
    df_merged:   pd.DataFrame,
    ga4_display: pd.DataFrame,
    df_daily:    pd.DataFrame,
    df_platform: pd.DataFrame,
) -> None:
    if df_merged.empty:
        st.info("Sem dados de mídia para o período. Atualize os dados na barra lateral.")
        return

    m = _pull_metrics(df_merged, ga4_display)

    _render_verdict(m)
    _render_three_numbers(m)
    st.divider()
    _render_funnel(m)
    st.divider()
    col_l, col_r = st.columns([3, 2])
    with col_l:
        _render_efficiency_trend(df_daily)
    with col_r:
        _render_channel_revenue(df_platform)
    st.divider()
    _render_the_ask(m, df_platform)
    st.caption(
        f"Atribuição: last-click via GA4 · "
        f"Invest. {fmt_currency(m['spd'])} · "
        f"Receita {fmt_currency(m['rev'])} · "
        f"ROAS {m['roas']:.2f}x"
    )
