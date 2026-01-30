import os
import json
import sys
import subprocess
from pathlib import Path
import requests
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import altair as alt
from datetime import datetime

project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
  sys.path.insert(0, str(project_root))

from backend.summary_report import generate_summary_report, _normalize_prob

st.set_page_config(
  page_title="SportsBank Pro Streamlit",
  page_icon="⚽",
  layout="wide",
  initial_sidebar_state="expanded"
)

def load_custom_css():
  css_file = Path(__file__).parent / "custom_theme.css"
  if css_file.exists():
    css_content = css_file.read_text(encoding="utf-8")
    st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
  else:
    st.markdown("""
    <style>
    input, select, textarea { font-size: 16px !important; }
    @media (max-width: 1024px) {
      div[data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; gap: 12px !important; }
      div[data-testid="stHorizontalBlock"] > div[data-testid="column"] { min-width: 48% !important; flex: 1 1 48% !important; }
    }
    @media (max-width: 768px) {
      div[data-testid="stHorizontalBlock"] { flex-direction: column !important; }
      div[data-testid="column"] { min-width: 100% !important; flex: 1 1 100% !important; width: 100% !important; }
      .stButton > button, .stDownloadButton > button { width: 100% !important; }
      .stDataFrame { overflow-x: auto !important; -webkit-overflow-scrolling: touch !important; }
      pre, code { white-space: pre-wrap !important; word-wrap: break-word !important; max-width: 100% !important; }
    }
    </style>
    """, unsafe_allow_html=True)

load_custom_css()

# ============================================
# SISTEMA DE AUTENTICAÇÃO
# ============================================
def setup_auth():
  try:
    from auth import Authenticator
    authenticator = Authenticator("config.yaml")
    if not authenticator.login():
      st.stop()
    authenticator.logout()
    return True
  except FileNotFoundError as e:
    st.warning(f"⚠️ Autenticação não configurada: {e}")
    st.info("💡 Configure config.yaml ou Secrets no Streamlit para habilitar.")
  except Exception as e:
    st.warning(f"⚠️ Falha na autenticação: {e}")
  return False

setup_auth()


_general = st.secrets.get("general") or {}
BACKEND_URL = (
  st.secrets.get("BACKEND_URL")
  or _general.get("BACKEND_URL")
  or os.getenv("BACKEND_URL")
  or "http://localhost:5001"
)
def get_health():
  try:
    r = requests.get(f"{BACKEND_URL}/health", timeout=5)
    return r.json()
  except:
    return None

def get_discover():
  try:
    r = requests.get(f"{BACKEND_URL}/discover", timeout=10)
    return r.json()
  except:
    return {"data_dirs": []}

def fetch_fixtures(leagues: list[str], date: str):
  try:
    params = {"leagues": ",".join(leagues), "date": date}
    r = requests.get(f"{BACKEND_URL}/fixtures", params=params, timeout=20)
    r.raise_for_status()
    st.session_state["last_error"] = None
    return r.json().get("matches", [])
  except Exception as e:
    st.session_state["last_error"] = str(e)
    return []

def decision_pre(payload: dict):
  try:
    r = requests.post(f"{BACKEND_URL}/decision/pre", json=payload, timeout=20)
    return r.json().get("picks", [])
  except:
    return []
def ai_analyze_context(home_team: str, away_team: str, news_summary: str | None):
  try:
    r = requests.post(f"{BACKEND_URL}/ai/analyze-context", json={"home_team": home_team, "away_team": away_team, "news_summary": news_summary or ""}, timeout=30)
    return r.json().get("analysis")
  except:
    return None
def ai_generate_report(home, away, stats, market, classification, prob):
    try:
        payload = {
            "home_team": home,
            "away_team": away,
            "stats": stats,
            "market": market,
            "classification": classification,
            "probability": prob
        }
        response = requests.post(f"{BACKEND_URL}/ai/generate-report", json=payload, timeout=60)
        if response.status_code == 200:
            return response.json().get("report")
    except Exception:
        pass
    return None

def ai_audit_match(match_data: dict):
    """Chama o endpoint de auditoria de cálculos do backend."""
    try:
        response = requests.post(f"{BACKEND_URL}/ai/audit-match", json=match_data, timeout=60)
        if response.status_code == 200:
            return response.json().get("audit")
    except Exception as e:
        st.error(f"Erro na auditoria: {e}")
    return None


# ===== FUNÇÃO PARA RENDERIZAR ANÁLISE AI (7 SEÇÕES) =====
def render_ai_analysis(analysis_data, report_text=None, match_data=None):
    """
    Renderiza análise Mistral AI em 7 seções modulares:
    1. Recomendação Principal (métricas)
    2. Comparação de Times (tabela)
    3. Histórico Direto H2H (gráfico)
    4. Análise Tática (colunas)
    5. Análise de Risco/Cenários (cards)
    6. Fatores de Risco (prós/contras)
    7. Recomendação Final (ação)
    """
    st.markdown(
        """
        <div class="ai-analysis-section">
            <h2>🤖 Análise Inteligente - Mistral AI <span class="ai-badge">Powered by Mistral</span></h2>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if analysis_data:
        # === SEÇÃO 1: RECOMENDAÇÃO PRINCIPAL ===
        with st.container(border=True):
            st.markdown("#### 🎯 Recomendação Principal")
            conf = analysis_data.get("confidence_adjustment", {})
            pressure = analysis_data.get("pressure_level", {})
            recommendation = conf.get("recommendation", "Aguardar")
            impact = conf.get("impact_percentage", 0)
            confidence = analysis_data.get("confidence", analysis_data.get("overall_confidence", 0))
            edge = analysis_data.get("edge", 0)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Prognóstico", recommendation)
            c2.metric("Confiança", f"{confidence}%" if confidence else "N/A")
            c3.metric("Edge", f"{edge}%" if edge else f"{impact}%")
            classification = "SAFE" if (confidence and float(str(confidence).replace('%','')) >= 60) else "NEUTRO"
            c4.metric("Classificação", classification,
                      delta="Alta" if classification == "SAFE" else "Moderada",
                      delta_color="normal" if classification == "SAFE" else "off")

        # === SEÇÃO 2: COMPARAÇÃO DE TIMES ===
        teams_data = analysis_data.get("team_comparison") or analysis_data.get("teams")
        if teams_data:
            with st.container(border=True):
                st.markdown("#### ⚔️ Comparação de Times")
                if isinstance(teams_data, dict):
                    home_data = teams_data.get("home", {})
                    away_data = teams_data.get("away", {})
                    comp_rows = []
                    all_keys = set(list(home_data.keys()) + list(away_data.keys()))
                    for k in sorted(all_keys):
                        comp_rows.append({
                            "Métrica": k.replace("_", " ").title(),
                            "Casa": str(home_data.get(k, "—")),
                            "Fora": str(away_data.get(k, "—")),
                        })
                    if comp_rows:
                        st.dataframe(pd.DataFrame(comp_rows), use_container_width=True, hide_index=True)
                elif isinstance(teams_data, list):
                    st.dataframe(pd.DataFrame(teams_data), use_container_width=True, hide_index=True)

        # === SEÇÃO 3: HISTÓRICO DIRETO (H2H) ===
        h2h = analysis_data.get("h2h") or analysis_data.get("head_to_head") or analysis_data.get("historical")
        if h2h:
            with st.container(border=True):
                st.markdown("#### 📊 Histórico Direto (H2H)")
                if isinstance(h2h, dict):
                    h2h_metrics = []
                    for k, v in h2h.items():
                        h2h_metrics.append({"Indicador": k.replace("_", " ").title(), "Valor": str(v)})
                    if h2h_metrics:
                        st.dataframe(pd.DataFrame(h2h_metrics), use_container_width=True, hide_index=True)
                    # Gráfico de barras H2H se houver dados numéricos
                    numeric_h2h = {k: v for k, v in h2h.items() if isinstance(v, (int, float))}
                    if numeric_h2h:
                        h2h_df = pd.DataFrame([{"Métrica": k.replace("_"," ").title(), "Valor": v} for k, v in numeric_h2h.items()])
                        h2h_chart = alt.Chart(h2h_df).mark_bar(color="#8b5cf6").encode(
                            x=alt.X("Métrica:N", sort=None),
                            y="Valor:Q",
                            tooltip=["Métrica", "Valor"]
                        ).properties(height=200)
                        st.altair_chart(h2h_chart, use_container_width=True)
                elif isinstance(h2h, list):
                    for item in h2h[:5]:
                        st.markdown(f"- {item}" if isinstance(item, str) else f"- {json.dumps(item, ensure_ascii=False)}")

        # === SEÇÃO 4: ANÁLISE TÁTICA ===
        tactical = analysis_data.get("tactical_analysis") or analysis_data.get("tactics")
        if tactical:
            with st.container(border=True):
                st.markdown("#### 🧠 Análise Tática")
                if isinstance(tactical, dict):
                    tc1, tc2 = st.columns(2)
                    home_tactic = tactical.get("home") or tactical.get("home_team", {})
                    away_tactic = tactical.get("away") or tactical.get("away_team", {})
                    with tc1:
                        st.markdown("**Casa**")
                        if isinstance(home_tactic, dict):
                            for k, v in home_tactic.items():
                                st.markdown(f"- **{k.replace('_',' ').title()}**: {v}")
                        elif isinstance(home_tactic, str):
                            st.markdown(home_tactic)
                    with tc2:
                        st.markdown("**Fora**")
                        if isinstance(away_tactic, dict):
                            for k, v in away_tactic.items():
                                st.markdown(f"- **{k.replace('_',' ').title()}**: {v}")
                        elif isinstance(away_tactic, str):
                            st.markdown(away_tactic)
                elif isinstance(tactical, str):
                    st.markdown(tactical)

        # === SEÇÃO 5: CENÁRIOS DE RISCO ===
        scenarios = analysis_data.get("scenarios") or analysis_data.get("risk_scenarios")
        if scenarios:
            with st.container(border=True):
                st.markdown("#### 🎲 Cenários")
                if isinstance(scenarios, dict):
                    sc1, sc2, sc3 = st.columns(3)
                    for col, (label, icon) in zip(
                        [sc1, sc2, sc3],
                        [("optimistic", "🟢"), ("base", "🟡"), ("pessimistic", "🔴")]
                    ):
                        sc = scenarios.get(label, {})
                        if sc:
                            with col:
                                st.markdown(f"**{icon} {label.title()}**")
                                if isinstance(sc, dict):
                                    for k, v in sc.items():
                                        st.markdown(f"- {k.replace('_',' ').title()}: {v}")
                                else:
                                    st.markdown(str(sc))
                elif isinstance(scenarios, list):
                    for sc in scenarios:
                        st.markdown(f"- {sc}" if isinstance(sc, str) else f"- {json.dumps(sc, ensure_ascii=False)}")

        # === SEÇÃO 6: FATORES DE RISCO ===
        factors = analysis_data.get("risk_factors") or analysis_data.get("factors")
        if factors:
            with st.container(border=True):
                st.markdown("#### ⚠️ Fatores de Risco")
                if isinstance(factors, dict):
                    pros = factors.get("pros") or factors.get("positive") or factors.get("favorable", [])
                    cons = factors.get("cons") or factors.get("negative") or factors.get("unfavorable", [])
                    fc1, fc2 = st.columns(2)
                    with fc1:
                        st.markdown("**Favoráveis**")
                        for p in (pros if isinstance(pros, list) else [pros]):
                            st.markdown(f"✅ {p}")
                    with fc2:
                        st.markdown("**Desfavoráveis**")
                        for c in (cons if isinstance(cons, list) else [cons]):
                            st.markdown(f"⚠️ {c}")
                elif isinstance(factors, list):
                    for f_item in factors:
                        st.markdown(f"- {f_item}" if isinstance(f_item, str) else f"- {json.dumps(f_item, ensure_ascii=False)}")

        # === SEÇÃO 7: RECOMENDAÇÃO FINAL ===
        with st.container(border=True):
            st.markdown("#### 📋 Recomendação Final")
            final_rec = analysis_data.get("final_recommendation") or analysis_data.get("summary") or analysis_data.get("conclusion")
            if final_rec:
                if isinstance(final_rec, dict):
                    for k, v in final_rec.items():
                        st.markdown(f"**{k.replace('_',' ').title()}**: {v}")
                else:
                    st.markdown(str(final_rec))
            else:
                st.markdown(f"**Recomendação**: {recommendation}")
                st.markdown(f"**Pressão Casa**: {pressure.get('home', 'N/A')} | **Pressão Fora**: {pressure.get('away', 'N/A')}")
                st.markdown(f"**Ajuste de Confiança**: {impact}%")

        # Dados brutos (colapsado)
        with st.expander("🔧 Dados brutos da análise (JSON)", expanded=False):
            st.json(analysis_data)

    if report_text:
        with st.container(border=True):
            st.markdown("### 📝 Relatório Detalhado")
            st.markdown(
                f'<div class="ai-analysis-content">{report_text}</div>',
                unsafe_allow_html=True,
            )

def criar_botao_copiar(texto: str, button_id: str = "copy-btn"):
  """
  Cria botao de copiar que funciona em desktop e mobile.
  """
  texto_escapado = (
    texto.replace("\\", "\\\\")
      .replace("'", "\\'")
      .replace("\n", "\\n")
  )
  html_template = """
  <div style="margin: 10px 0;">
      <button
          id="__BUTTON_ID__"
          onclick="copyToClipboard()"
          style="
              background-color: #22c55e;
              color: white;
              border: none;
              padding: 12px 24px;
              border-radius: 5px;
              cursor: pointer;
              font-size: 16px;
              font-weight: bold;
              width: 100%%;
              transition: all 0.3s;
              box-shadow: 0 2px 4px rgba(0,0,0,0.1);
          "
          onmouseover="this.style.backgroundColor='#16a34a'; this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 8px rgba(0,0,0,0.2)';"
          onmouseout="this.style.backgroundColor='#22c55e'; this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 4px rgba(0,0,0,0.1)';"
      >
          📋 Copiar
      </button>
      <div id="feedback-__BUTTON_ID__" style="
          margin-top: 10px;
          padding: 10px;
          border-radius: 5px;
          display: none;
          text-align: center;
          font-weight: bold;
          animation: fadeIn 0.3s;
      "></div>
  </div>
  <style>
      @keyframes fadeIn {
          from { opacity: 0; transform: translateY(-10px); }
          to { opacity: 1; transform: translateY(0); }
      }
  </style>
  <script>
      const textoParaCopiar = '__TEXTO__';
      function copyToClipboard() {
          if (navigator.clipboard && navigator.clipboard.writeText) {
              navigator.clipboard.writeText(textoParaCopiar)
                  .then(() => {
                      mostrarFeedback('✅ Copiado com sucesso!', 'success');
                  })
                  .catch(() => {
                      tentarMetodoAntigo();
                  });
          } else {
              tentarMetodoAntigo();
          }
      }
      function tentarMetodoAntigo() {
          const textarea = document.createElement('textarea');
          textarea.value = textoParaCopiar;
          textarea.style.position = 'fixed';
          textarea.style.left = '-9999px';
          textarea.style.top = '0';
          document.body.appendChild(textarea);
          if (navigator.userAgent.match(/ipad|ipod|iphone/i)) {
              const range = document.createRange();
              range.selectNodeContents(textarea);
              const selection = window.getSelection();
              selection.removeAllRanges();
              selection.addRange(range);
              textarea.setSelectionRange(0, 999999);
          } else {
              textarea.select();
          }
          try {
              const successful = document.execCommand('copy');
              if (successful) {
                  mostrarFeedback('✅ Copiado com sucesso!', 'success');
              } else {
                  mostrarFeedback('❌ Erro ao copiar. Tente baixar o arquivo.', 'error');
              }
          } catch (err) {
              mostrarFeedback('❌ Erro ao copiar. Tente baixar o arquivo.', 'error');
          }
          document.body.removeChild(textarea);
      }
      function mostrarFeedback(mensagem, tipo) {
          const feedback = document.getElementById('feedback-__BUTTON_ID__');
          feedback.textContent = mensagem;
          feedback.style.display = 'block';
          feedback.style.backgroundColor = tipo === 'success' ? '#d4edda' : '#f8d7da';
          feedback.style.color = tipo === 'success' ? '#155724' : '#721c24';
          feedback.style.border = tipo === 'success' ? '1px solid #c3e6cb' : '1px solid #f5c6cb';
          setTimeout(() => {
              feedback.style.display = 'none';
          }, 3000);
      }
  </script>
  """
  html_code = html_template.replace('__BUTTON_ID__', button_id).replace('__TEXTO__', texto_escapado)
  components.html(html_code, height=120)

def get_last_update(matches: list[dict]) -> str | None:
  for m in matches:
    val = m.get("lastUpdated") or m.get("last_updated") or m.get("updatedAt")
    if val:
      return str(val)
  return None

def format_match_row(m: dict):
  return {
    "Liga": m.get("leagueName"),
    "Jogo": f"{m.get('homeTeam')} vs {m.get('awayTeam')}",
    "Data": m.get("datetime"),
    "Odds Home": m.get("odds", {}).get("home"),
    "Odds Draw": m.get("odds", {}).get("draw"),
    "Odds Away": m.get("odds", {}).get("away"),
    "BTTS%": m.get("stats", {}).get("bttsProb"),
    "Over0.5%": m.get("stats", {}).get("over05Prob"),
    "Over1.5%": m.get("stats", {}).get("over15Prob"),
    "Over2.5%": m.get("stats", {}).get("over25Prob"),
    "Over3.5%": m.get("stats", {}).get("over35Prob"),
    "λH": m.get("stats", {}).get("lambdaHome"),
    "λA": m.get("stats", {}).get("lambdaAway"),
    "λT": m.get("stats", {}).get("lambdaTotal"),
    "Posse": f"{m.get('stats', {}).get('homePossession') or '-'} / {m.get('stats', {}).get('awayPossession') or '-'}",
    "Escanteios/Partida": f"{m.get('stats', {}).get('homeCornersPerMatch') or '-'} / {m.get('stats', {}).get('awayCornersPerMatch') or '-'}",
    "Cartões/Partida": f"{m.get('stats', {}).get('homeCardsPerMatch') or '-'} / {m.get('stats', {}).get('awayCardsPerMatch') or '-'}",
  }


st.title("⚽ SportsBank Pro - Streamlit")
st.caption(f"Backend: {BACKEND_URL}")

def get_git_info():
  try:
    commit_hash = subprocess.check_output(
      ["git", "rev-parse", "--short", "HEAD"],
      stderr=subprocess.DEVNULL,
    ).decode("ascii").strip()
    branch = subprocess.check_output(
      ["git", "rev-parse", "--abbrev-ref", "HEAD"],
      stderr=subprocess.DEVNULL,
    ).decode("ascii").strip()
    return f"{branch}@{commit_hash}"
  except Exception:
    return os.getenv("GIT_COMMIT_SHA", "dev")

st.caption(f"Versão: {get_git_info()} | Atualizado: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

health = get_health()
if health:
  col_status1, col_status2, col_theme = st.columns([3, 1, 1])
  with col_status1:
    st.success("✅ Backend conectado")
  with col_status2:
    if st.button("🔄 Recarregar", key="reload_health"):
      st.rerun()
  with col_theme:
    theme = st.selectbox("Tema", options=["Dark","Light"], index=0)
    if theme == "Light":
      st.markdown("""
        <style>
        :root {
          --bg-dark: #F5F5F0 !important;
          --bg-dark-secondary: #FAFAF5 !important;
          --bg-dark-tertiary: #EEEEE8 !important;
          --border-dark: #C8C8BE !important;
          --text-dark-primary: #1a1a1a !important;
          --text-dark-secondary: #2d3748 !important;
          --text-dark-tertiary: #4a5568 !important;
        }
        .stApp { background-color: var(--bg-dark-secondary) !important; }
        h1, h2, h3 { color: var(--text-dark-primary) !important; }
        p, label, .stMarkdown, .stMarkdown p, .stMarkdown div, .stCaption,
        .stText, [data-testid='stMetricValue'], [data-testid='stCaption'],
        .element-container p, .element-container .stMarkdown {
          color: var(--text-dark-secondary) !important;
        }
        .stMetric label { color: var(--text-dark-tertiary) !important; }
        .stDataFrame table { background-color: var(--bg-dark-secondary) !important; }
        .stDataFrame thead tr th { background-color: var(--bg-dark-tertiary) !important; color: var(--text-dark-primary) !important; }
        .stDataFrame tbody tr td { color: var(--text-dark-secondary) !important; }
        .streamlit-expanderHeader, .streamlit-expanderContent { background-color: var(--bg-dark-secondary) !important; color: var(--text-dark-primary) !important; }
        .stSelectbox > div > div, .stMultiSelect > div > div, .stTextInput > div > div > input,
        .stTextArea > div > div > textarea, .stDateInput > div > div > input {
          background-color: #ffffff !important; color: var(--text-dark-primary) !important;
          border-color: var(--border-dark) !important;
        }
        .stCheckbox label, .stRadio label { color: var(--text-dark-secondary) !important; }
        .stMetric { background-color: var(--bg-dark-secondary) !important; border-color: var(--border-dark) !important; }
        .stCode, pre, code { background-color: var(--bg-dark-tertiary) !important; color: var(--text-dark-primary) !important; }
        </style>
      """, unsafe_allow_html=True)
else:
  st.error("❌ Backend indisponível")
  with st.expander("🔧 Diagnóstico e Soluções", expanded=True):
    st.markdown(f"""
    **URL do Backend:** `{BACKEND_URL}`

    **Possíveis causas:**
    - Backend não está em execução
    - URL configurada incorretamente
    - Problemas de rede ou firewall
    - Backend em manutenção

    **Soluções:**
    1. Teste `{BACKEND_URL}/health`
    2. Verifique `.streamlit/secrets.toml`
    3. Confira logs do backend

    **Admin:** BACKEND_URL env configurado: `{bool(os.getenv('BACKEND_URL'))}`
    """)
    col_diag1, col_diag2 = st.columns(2)
    with col_diag1:
      if st.button("🔄 Tentar Reconectar", key="reconnect"):
        with st.spinner("Tentando reconectar..."):
          import time
          time.sleep(1)
          st.rerun()
    with col_diag2:
      if st.button("📋 Copiar URL do Backend", key="copy_backend_url"):
        st.code(BACKEND_URL)
  st.warning("⚠️ A aplicação continuará funcionando em modo limitado.")

col_a, col_b, col_c = st.columns([2, 2, 1])

discover = get_discover()
available_leagues = [d["league"] for d in discover.get("data_dirs", [])] or [
  "premier-league","la-liga","serie-a","bundesliga","ligue-1","brasileirao-serie-a"
]
default_leagues = ["premier-league"] if "premier-league" in available_leagues else available_leagues[:2]

with col_a:
  leagues = st.multiselect("Ligas", options=available_leagues, default=default_leagues)
with col_b:
  date_filter = st.radio("Data", options=["today","tomorrow","week"], index=2, horizontal=True)
with col_c:
  fetch_btn = st.button("🔍 Buscar Jogos", use_container_width=True)

if "auto_loaded" not in st.session_state:
  st.session_state["auto_loaded"] = False
if "last_query" not in st.session_state:
  st.session_state["last_query"] = ([], None)
if "last_matches" not in st.session_state:
  st.session_state["last_matches"] = []
current_query = (list(leagues), date_filter)
should_fetch = fetch_btn or not st.session_state["auto_loaded"] or st.session_state["last_query"] != current_query
if should_fetch and leagues:
  st.session_state["last_matches"] = fetch_fixtures(leagues, date_filter)
  st.session_state["auto_loaded"] = True
  st.session_state["last_query"] = current_query
matches = st.session_state["last_matches"]

st.markdown("---")
st.subheader("📊 Quadro-Resumo Profissional")

col1, col2 = st.columns([4, 1])
with col1:
  st.caption("Prognósticos formatados para compartilhamento e análise rápida")
with col2:
  gerar_btn = st.button("🔄 Gerar Quadro", use_container_width=True, key="gerar_quadro")

st.markdown("**Selecione o que deseja visualizar:**")
formato = st.selectbox("Formato", options=["Detalhado", "WhatsApp"], index=0)
col_a, col_b, col_c, col_d = st.columns(4)
with col_a:
  incluir_simples = st.checkbox(
    "🎯 Jogos Simples",
    value=True,
    help="Prognósticos individuais para cada jogo",
    key="check_simples",
  )
with col_b:
  incluir_duplas = st.checkbox(
    "🔗 Duplas SAFE",
    value=True,
    help="Combinações de 2 jogos com alta confiança",
    key="check_duplas",
  )
with col_c:
  incluir_triplas = st.checkbox(
    "🎲 Triplas SAFE",
    value=False,
    help="Combinações de 3 jogos (maior risco)",
    key="check_triplas",
  )
with col_d:
  incluir_governanca = st.checkbox(
    "📋 Governança",
    value=True,
    help="Regras e alertas do sistema",
    key="check_governanca",
  )

if "quadro_resumo_texto" not in st.session_state:
  st.session_state["quadro_resumo_texto"] = None
if "quadro_resumo_meta" not in st.session_state:
  st.session_state["quadro_resumo_meta"] = {}

if gerar_btn and leagues:
  with st.spinner("⚙️ Gerando quadro-resumo personalizado..."):
    try:
      response = requests.get(
        f"{BACKEND_URL}/quadro-resumo",
        params={
          "league": leagues[0],
          "date": date_filter,
          "incluir_simples": incluir_simples,
          "incluir_duplas": incluir_duplas,
          "incluir_triplas": incluir_triplas,
          "incluir_governanca": incluir_governanca,
          "formato": "whatsapp" if formato == "WhatsApp" else "detalhado",
        },
        timeout=30,
      )
      response.raise_for_status()
      data = response.json()
      st.session_state["quadro_resumo_texto"] = data.get("quadro_texto")
      st.session_state["quadro_resumo_meta"] = data
    except requests.exceptions.Timeout:
      st.error("❌ Timeout: O backend demorou muito para responder.")
      st.info("💡 Tente novamente ou selecione menos jogos.")
    except requests.exceptions.RequestException as e:
      st.error(f"❌ Erro ao gerar quadro-resumo: {str(e)}")
      st.info("💡 Verifique se o backend está rodando e se há jogos disponíveis.")
    except Exception as e:
      st.error(f"❌ Erro inesperado: {str(e)}")
elif gerar_btn and not leagues:
  st.warning("⚠️ Selecione pelo menos uma liga antes de gerar o quadro-resumo!")

quadro_texto = st.session_state.get("quadro_resumo_texto")
if quadro_texto:
  st.code(quadro_texto, language="text")

  col1, col2 = st.columns(2)
  with col1:
    criar_botao_copiar(quadro_texto, button_id="copy-quadro-resumo")
  with col2:
    meta = st.session_state.get("quadro_resumo_meta", {})
    st.download_button(
      "📥 Baixar",
      data=quadro_texto,
      file_name=f"quadro_{leagues[0]}_{date_filter}_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
      mime="text/plain",
      use_container_width=True,
      key="download_quadro",
    )

  st.markdown("---")
  meta = st.session_state.get("quadro_resumo_meta", {})
  cols = st.columns(4)
  if incluir_simples and meta.get("jogos_count", 0) > 0:
    cols[0].metric("🎯 Jogos", meta.get("jogos_count"))
  if incluir_duplas and meta.get("duplas_count", 0) > 0:
    cols[1].metric("🔗 Duplas", meta.get("duplas_count"))
  if incluir_triplas and meta.get("triplas_count", 0) > 0:
    cols[2].metric("🎲 Triplas", meta.get("triplas_count"))
  cols[3].metric("⚙️ Regime", meta.get("regime", "N/A"))
  st.caption(f"Volatilidade: {meta.get('volatilidade', 'N/A')}")

st.subheader("⚽ Jogos")
if matches:

  # --- Barra de status da liga ---
  regimes = {m.get("stats", {}).get("leagueRegime") for m in matches if m.get("stats", {}).get("leagueRegime")}
  vols = {m.get("stats", {}).get("leagueVolatility") for m in matches if m.get("stats", {}).get("leagueVolatility")}
  last_update = get_last_update(matches)
  data_source = matches[0].get("dataSource") if matches else None

  regime_str = ', '.join(sorted(regimes)) if regimes else 'N/A'
  vol_str = ', '.join(sorted(vols)) if vols else 'N/A'
  update_str = f"{last_update} UTC" if last_update else "não informada"
  source_str = data_source if data_source else "API"

  st.markdown(f"""
  <div class="quadro-status-bar">
    <div class="quadro-status-item">
      <div class="quadro-status-label">Jogos</div>
      <div class="quadro-status-value">{len(matches)}</div>
    </div>
    <div class="quadro-status-item">
      <div class="quadro-status-label">Regime</div>
      <div class="quadro-status-value">{regime_str}</div>
    </div>
    <div class="quadro-status-item">
      <div class="quadro-status-label">Volatilidade</div>
      <div class="quadro-status-value">{vol_str}</div>
    </div>
    <div class="quadro-status-item">
      <div class="quadro-status-label">Atualização</div>
      <div class="quadro-status-value">{update_str}</div>
    </div>
    <div class="quadro-status-item">
      <div class="quadro-status-label">Fonte</div>
      <div class="quadro-status-value">{source_str}</div>
    </div>
  </div>
  """, unsafe_allow_html=True)

  # --- Tabela unificada (colunas essenciais) ---
  def build_unified_row(m: dict):
    stats = m.get("stats", {})
    odds = m.get("odds", {})
    # Mercados sugeridos (lógica do summary_report inline)
    markets = []
    p25 = _normalize_prob(stats.get("over25Prob"))
    p_btts = _normalize_prob(stats.get("bttsProb"))
    if p25 and p25 > 0.6:
      markets.append(f"Over 2.5 ({p25*100:.0f}%)")
    if p_btts and p_btts > 0.55:
      markets.append(f"BTTS ({p_btts*100:.0f}%)")
    if not markets:
      markets = ["—"]
    # EV
    ev = m.get("ev")
    if ev is None and p25:
      odd_o25 = odds.get("over25")
      if odd_o25:
        try:
          ev = (p25 * float(odd_o25)) - 1
        except Exception:
          ev = None
    return {
      "Jogo": f"{m.get('homeTeam')} vs {m.get('awayTeam')}",
      "Liga": m.get("leagueName", ""),
      "Data": m.get("datetime", ""),
      "1": odds.get("home", "—"),
      "X": odds.get("draw", "—"),
      "2": odds.get("away", "—"),
      "BTTS%": stats.get("bttsProb", "—"),
      "O2.5%": stats.get("over25Prob", "—"),
      "λH": stats.get("lambdaHome", "—"),
      "λA": stats.get("lambdaAway", "—"),
      "Mercados": " | ".join(markets),
      "Status": m.get("pick_type", "NO_BET"),
      "EV": f"{ev:.2f}" if ev is not None else "—",
    }

  df_unified = pd.DataFrame([build_unified_row(m) for m in matches])
  st.dataframe(df_unified, use_container_width=True, hide_index=True, height=min(400, 56 + len(matches) * 35))

  # --- Tabela completa (expandível) ---
  with st.expander("📋 Ver tabela completa com todas as estatísticas", expanded=False):
    df_full = pd.DataFrame([format_match_row(m) for m in matches])
    st.dataframe(df_full, use_container_width=True, height=400)

  st.subheader("📈 Gráfico de Probabilidades")
  chart_rows = []
  game_names = []
  for m in matches:
    game = f"{m.get('homeTeam')} vs {m.get('awayTeam')}"
    game_names.append(game)
    stats = m.get("stats", {})
    for key,label in [
      ("over05Prob","Over 0.5"),
      ("over15Prob","Over 1.5"),
      ("over25Prob","Over 2.5"),
      ("over35Prob","Over 3.5"),
      ("bttsProb","BTTS"),
    ]:
      val = stats.get(key)
      if val is not None:
        chart_rows.append({"Jogo": game, "Métrica": label, "Prob%": float(val), "λH": stats.get("lambdaHome"), "λA": stats.get("lambdaAway"), "λT": stats.get("lambdaTotal")})
  if chart_rows:
    cdf = pd.DataFrame(chart_rows)
    # Seletor de jogo para evitar gráfico muito largo
    selected_chart_game = st.selectbox(
      "Selecionar jogo para visualizar",
      options=game_names,
      key="chart_game_selector"
    )
    cdf_filtered = cdf[cdf["Jogo"] == selected_chart_game]
    chart = alt.Chart(cdf_filtered).mark_bar(
      cornerRadiusTopLeft=4,
      cornerRadiusTopRight=4,
    ).encode(
      x=alt.X("Métrica:N", sort=None, axis=alt.Axis(labelAngle=0)),
      y=alt.Y("Prob%:Q", title="Probabilidade %"),
      color=alt.Color("Métrica:N", legend=None),
      tooltip=["Jogo","Métrica","Prob%","λH","λA","λT"]
    ).properties(height=300, title=selected_chart_game)
    st.altair_chart(chart, use_container_width=True)
else:
  err = st.session_state.get("last_error")
  if err:
    st.error(f"Falha ao buscar jogos: {err}")
  st.info("Nenhum jogo encontrado. Ajuste a liga/data e tente novamente.")

st.subheader("🎯 Análise de Picks")
selected_games = st.multiselect("Selecionar jogos para análise", options=[f"{m.get('homeTeam')} vs {m.get('awayTeam')}" for m in matches])
if st.button("🔍 Analisar Selecionados") and selected_games:
  sel = []
  for m in matches:
    key = f"{m.get('homeTeam')} vs {m.get('awayTeam')}"
    if key in selected_games:
      sel.append({
        "id": m.get("id"),
        "leagueId": m.get("leagueId"),
        "homeTeam": m.get("homeTeam"),
        "awayTeam": m.get("awayTeam"),
        "odds": m.get("odds"),
        "stats": m.get("stats"),
        "datetime": m.get("datetime"),
      })
  picks = decision_pre({"matches": sel})
  if picks:
    pdf = pd.DataFrame(picks)
    if "prob" in pdf.columns:
      def format_prob(v):
        try:
          fv = float(v)
        except Exception:
          return v
        if fv <= 1:
          return f"{fv * 100:.1f}%"
        return f"{fv:.1f}%"
      pdf["prob"] = pdf["prob"].apply(format_prob)
    st.dataframe(pdf, use_container_width=True)
  else:
    st.info("Sem picks retornados")
# ===== ANÁLISE DE CONTEXTO (MISTRAL AI) =====
st.markdown("---")
st.markdown(
  """
  <div class="ai-analysis-section">
    <div class="ai-analysis-header">
      <h2>🤖 Análise de Contexto com IA <span class="ai-badge">Powered by Mistral</span></h2>
    </div>
  </div>
  """,
  unsafe_allow_html=True,
)

ai_col1, ai_col2 = st.columns([2, 1])
with ai_col1:
  if matches:
    jogo_ai = st.selectbox("Jogo", options=[f"{m.get('homeTeam')} vs {m.get('awayTeam')}" for m in matches])
  else:
    jogo_ai = None
  news_summary = st.text_area("Resumo de notícias", placeholder="Lesões, pressão, contexto tático", height=100)
  market_choice = st.selectbox("Mercado para relatório", options=["Over 0.5","Over 1.5","Over 2.5","Over 3.5","BTTS"], index=2)
with ai_col2:
  run_ai = st.button("🚀 Analisar Contexto", use_container_width=True)

if run_ai and jogo_ai:
  for m in matches:
    if f"{m.get('homeTeam')} vs {m.get('awayTeam')}" == jogo_ai:
      with st.spinner("🤖 Mistral AI está analisando..."):
        analysis = ai_analyze_context(m.get('homeTeam'), m.get('awayTeam'), news_summary)

      if analysis:
        render_ai_analysis(analysis)
        st.download_button(
          "📥 Baixar análise (JSON)",
          data=json.dumps(analysis, ensure_ascii=False, indent=2),
          file_name="analysis.json",
          mime="application/json",
          use_container_width=True,
        )

        stats = m.get("stats") or {}
        market = market_choice
        prob_map = {
          "Over 0.5": stats.get("over05Prob") or 0,
          "Over 1.5": stats.get("over15Prob") or 0,
          "Over 2.5": stats.get("over25Prob") or 0,
          "Over 3.5": stats.get("over35Prob") or 0,
          "BTTS": stats.get("bttsProb") or 0,
        }
        prob = float((prob_map.get(market) or 0) * 100)
        classification = "SAFE" if prob >= 60 else "NEUTRO"

        with st.spinner("📝 Gerando relatório detalhado..."):
          report = ai_generate_report(m.get('homeTeam'), m.get('awayTeam'), stats, market, classification, prob)

        if report:
          st.markdown("---")
          st.subheader("📝 Relatório do Mercado (Mistral AI)")
          render_ai_analysis(None, report)
          st.download_button(
            "📥 Baixar relatório (TXT)",
            data=report,
            file_name="report.txt",
            mime="text/plain",
            use_container_width=True,
            key="download_report",
          )
          
        # ===== NOVA SEÇÃO: AUDITORIA DE CÁLCULOS =====
        st.markdown("---")
        st.subheader("🔍 Auditoria de Cálculos (Auditor)")
        if st.button("⚖️ Auditar Cálculos Estatísticos", use_container_width=True, key="btn_audit"):
            with st.spinner("⚖️ Mistral Auditor está validando os números..."):
                audit_data = {
                    "id": m.get("id"),
                    "homeTeam": m.get("homeTeam"),
                    "awayTeam": m.get("awayTeam"),
                    "stats": m.get("stats"),
                    "odds": m.get("odds")
                }
                audit_result = ai_audit_match(audit_data)
                if audit_result:
                    st.success(f"Auditoria concluída com {audit_result.get('audit_confidence', 0)}% de confiança")
                    
                    col_aud1, col_aud2, col_aud3 = st.columns(3)
                    v = audit_result.get("validation", {})
                    
                    def get_status_color(status):
                        if status == "OK": return "✅"
                        if status == "WARNING": return "⚠️"
                        return "❌"
                        
                    with col_aud1:
                        st.metric("Probabilidades", v.get("probabilities", {}).get("status", "N/A"), help=v.get("probabilities", {}).get("notes"))
                    with col_aud2:
                        st.metric("Lambdas", v.get("lambdas", {}).get("status", "N/A"), help=v.get("lambdas", {}).get("notes"))
                    with col_aud3:
                        st.metric("Expected Value", v.get("ev", {}).get("status", "N/A"), help=v.get("ev", {}).get("notes"))
                        
                    with st.expander("Ver detalhes da auditoria"):
                        st.json(audit_result)
      else:
        st.info("ℹ️ Sem análise retornada. Verifique se o backend está configurado corretamente.")
      break
