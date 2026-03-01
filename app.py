import os
import json
import requests
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import altair as alt
from datetime import datetime
from backend.summary_report import generate_summary_report
from auth import Authenticator

# Configurar página
st.set_page_config(page_title="SportsBankZU Pro Streamlit", layout="wide")
st.markdown(
  """
  <style>
  @media (max-width: 768px) {
    div[data-testid="stHorizontalBlock"] {
      flex-wrap: wrap;
    }
    div[data-testid="column"] {
      min-width: 100% !important;
      flex: 1 1 100% !important;
    }
  }
  </style>
  """,
  unsafe_allow_html=True,
)

# ============================================
# SISTEMA DE AUTENTICAÇÃO
# ============================================
authenticator = Authenticator('config.yaml')

if not authenticator.login():
    st.stop()  # Para a execução se não estiver autenticado

authenticator.logout()  # Adiciona botão de logout na sidebar

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
    r = requests.post(
      f"{BACKEND_URL}/ai/analyze-context",
      json={"home_team": home_team, "away_team": away_team, "news_summary": news_summary or ""},
      timeout=30,
    )
    return r.json().get("analysis")
  except:
    return None
def ai_generate_report(home_team: str, away_team: str, stats: dict, market: str, classification: str, probability: float):
  try:
    r = requests.post(
      f"{BACKEND_URL}/ai/generate-report",
      json={"home_team": home_team, "away_team": away_team, "stats": stats, "market": market, "classification": classification, "probability": probability},
      timeout=30,
    )
    return r.json().get("report")
  except:
    return None

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
              background-color: #0066cc;
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
          onmouseover="this.style.backgroundColor='#0052a3'; this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 8px rgba(0,0,0,0.2)';"
          onmouseout="this.style.backgroundColor='#0066cc'; this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 4px rgba(0,0,0,0.1)';"
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
                  .catch(err => {
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
  html_code = (
    html_template
      .replace("__BUTTON_ID__", button_id)
      .replace("__TEXTO__", texto_escapado)
  )
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

st.title("SportsBankZU Pro - Streamlit")
st.caption(f"Backend: {BACKEND_URL}")
health = get_health()
if health:
  st.success("Backend conectado")
else:
  st.warning("Backend indisponível. Verifique BACKEND_URL nos Secrets.")
st.caption(f"Backend: {BACKEND_URL}")

col_a, col_b, col_c = st.columns([2, 2, 1])

discover = get_discover()
# Se o backend retornar ligas, usamos elas. Se não, usamos uma lista fixa estendida com as 22 ligas
all_possible_leagues = [
    "premier-league", "championship", "league-one", "league-two", # Inglaterra
    "la-liga", "segunda-division", # Espanha
    "serie-a", "serie-b", # Itália
    "bundesliga", "2-bundesliga", # Alemanha
    "ligue-1", "ligue-2", # França
    "eredivisie", # Holanda
    "primeira-liga", # Portugal
    "super-lig", # Turquia
    "pro-league", # Bélgica
    "premiership", # Escócia
    "brasileirao-serie-a", "brasileirao-serie-b", # Brasil
    # Novas ligas adicionadas
    "primera-division", # Argentina
    "a-league", # Austrália
    "austrian-bundesliga", # Áustria
    "superliga", # Dinamarca
    "professional-league", # Arábia Saudita
    "super-league" # Suíça
]

available_leagues = [d["league"] for d in discover.get("data_dirs", [])]
if not available_leagues:
    available_leagues = all_possible_leagues

# Ordena alfabeticamente para facilitar a busca
available_leagues = sorted(list(set(available_leagues)))

default_leagues = ["premier-league"] if "premier-league" in available_leagues else available_leagues[:1]

with col_a:
  leagues = st.multiselect("Ligas", options=available_leagues, default=default_leagues)
with col_b:
  date_filter = st.radio("Data", options=["today","tomorrow","week"], index=2, horizontal=True)
with col_c:
  fetch_btn = st.button("Buscar Jogos")

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
  with st.spinner("Gerando quadro-resumo personalizado..."):
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

st.subheader("Jogos")
if matches:
  st.subheader("Quadro Resumo de Jogos")
  summary_report = generate_summary_report(matches)
  st.dataframe(summary_report, hide_index=True, use_container_width=True)

  last_update = get_last_update(matches)
  if last_update:
    st.caption(f"Última atualização (fonte): {last_update} UTC")
  else:
    st.caption("Última atualização: não informada pela fonte.")
  data_source = matches[0].get("dataSource") if matches else None
  if data_source:
    st.caption(f"Origem dos dados: {data_source}")
  # Regime/volatilidade por liga (se disponível)
  regimes = {m.get("stats", {}).get("leagueRegime") for m in matches if m.get("stats", {}).get("leagueRegime")}
  vols = {m.get("stats", {}).get("leagueVolatility") for m in matches if m.get("stats", {}).get("leagueVolatility")}
  if regimes or vols:
    st.caption(f"Regime da Liga: {', '.join(sorted(regimes)) or '-'} | Volatilidade: {', '.join(sorted(vols)) or '-'}")
  df = pd.DataFrame([format_match_row(m) for m in matches])
  st.dataframe(df, use_container_width=True, height=400)

  st.subheader("Gráfico de Probabilidades")
  chart_rows = []
  for m in matches:
    league_name = m.get("leagueName") or m.get("league") or m.get("leagueId") or "-"
    game = f"{league_name} — {m.get('homeTeam')} vs {m.get('awayTeam')}"
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
        chart_rows.append({
          "Liga": league_name,
          "Jogo": game,
          "Métrica": label,
          "Prob%": float(val),
          "λH": stats.get("lambdaHome"),
          "λA": stats.get("lambdaAway"),
          "λT": stats.get("lambdaTotal"),
        })
  if chart_rows:
    cdf = pd.DataFrame(chart_rows)
    # Lista única de jogos para criar o seletor
    jogos_unicos = sorted(list(set(cdf["Jogo"])))
    
    st.markdown("### Visualização Gráfica")
    jogo_selecionado = st.selectbox(
        "Selecione o jogo para visualizar probabilidades:",
        options=jogos_unicos,
        key="chart_game_selector"
    )
    
    # Filtra o dataframe para mostrar apenas o jogo selecionado
    cdf_filtrado = cdf[cdf["Jogo"] == jogo_selecionado]
    
    chart = alt.Chart(cdf_filtrado).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
      x=alt.X("Métrica", axis=alt.Axis(labelAngle=0)),
      y=alt.Y("Prob%", scale=alt.Scale(domain=[0, 100])),
      color=alt.Color("Métrica", legend=None),
      tooltip=["Liga", "Jogo", "Métrica", "Prob%", "λH", "λA", "λT"]
    ).properties(height=300)
    
    st.altair_chart(chart, use_container_width=True)
else:
  err = st.session_state.get("last_error")
  if err:
    st.error(f"Falha ao buscar jogos: {err}")
  st.info("Nenhum jogo encontrado. Ajuste a liga/data e tente novamente.")

st.subheader("Análise de Picks")
selected_games = st.multiselect("Selecionar jogos para análise", options=[f"{m.get('homeTeam')} vs {m.get('awayTeam')}" for m in matches])
if st.button("Analisar Selecionados") and selected_games:
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
st.subheader("Análise de Contexto (AI)")
ai_col1, ai_col2 = st.columns([2, 1])
with ai_col1:
  if matches:
    jogo_ai = st.selectbox("Jogo", options=[f"{m.get('homeTeam')} vs {m.get('awayTeam')}" for m in matches])
  else:
    jogo_ai = None
  news_summary = st.text_area("Resumo de notícias", placeholder="Lesões, pressão, contexto tático", height=100)
  market_choice = st.selectbox("Mercado para relatório", options=["Over 0.5","Over 1.5","Over 2.5","Over 3.5","BTTS"], index=2)
with ai_col2:
  run_ai = st.button("Analisar Contexto", use_container_width=True)
if run_ai and jogo_ai:
  for m in matches:
    if f"{m.get('homeTeam')} vs {m.get('awayTeam')}" == jogo_ai:
      analysis = ai_analyze_context(m.get('homeTeam'), m.get('awayTeam'), news_summary)
      if analysis:
        st.json(analysis, expanded=True)
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
        report = ai_generate_report(m.get('homeTeam'), m.get('awayTeam'), stats, market, classification, prob)
        if report:
          st.markdown("---")
          st.subheader("Relatório do Mercado (AI)")
          st.write(report)
          st.download_button(
            "📥 Baixar relatório (TXT)",
            data=report,
            file_name="report.txt",
            mime="text/plain",
            use_container_width=True,
          )
      else:
        st.info("Sem análise retornada")
      break