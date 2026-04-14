/**
 * Glossary data for SportsBankZU Pro (#080).
 */

export interface GlossaryEntry {
  term: string;
  category: "classificacao" | "metrica" | "mercado" | "modelo";
  definition: string;
  example?: string;
}

export const GLOSSARY: GlossaryEntry[] = [
  // ── Classifications ──
  {
    term: "ALTA CONFIANCA",
    category: "classificacao",
    definition:
      "Classificacao maxima — probabilidade alta, EV positivo, dados confiaveis e edge suficiente. Todos os criterios do modelo foram atingidos.",
    example: "Over 2.5 gols com prob 72%, EV +8.3%, edge 6.1%",
  },
  {
    term: "VALOR DETECTADO",
    category: "classificacao",
    definition:
      "O modelo encontrou valor matematico (EV+), mas nem todos os criterios de alta confianca foram atingidos. Elegivel para combinadas e duplas.",
    example: "BTTS Sim com prob 58%, EV +4.2%",
  },
  {
    term: "VIÁVEL",
    category: "classificacao",
    definition:
      "Mercado com chance real de acerto neste jogo especifico, mas sem valor matematico (EV+) para aposta sistematica. Viavel como pick pontual.",
  },
  {
    term: "BLOQUEADO",
    category: "classificacao",
    definition:
      "Mercado bloqueado pelo sistema por risco alto, dados insuficientes, EV muito negativo ou regime restritivo da liga.",
  },

  // ── Metrics ──
  {
    term: "Brier Score",
    category: "metrica",
    definition:
      "Mede a precisao das probabilidades previstas. Varia de 0 (perfeito) a 1 (pior possivel). Quanto menor, melhor a calibracao do modelo.",
    example: "Brier 0.18 = boa calibracao; Brier 0.30 = precisa ajuste",
  },
  {
    term: "Log-Loss",
    category: "metrica",
    definition:
      "Penaliza previsoes confiantes que erram. Modelo que diz 95% e erra e penalizado muito mais do que um que diz 55% e erra.",
  },
  {
    term: "Sharpe Ratio",
    category: "metrica",
    definition:
      "Retorno medio dividido pela volatilidade. Mede eficiencia do retorno ajustado ao risco. Acima de 1.0 e considerado bom.",
  },
  {
    term: "EV (Expected Value)",
    category: "metrica",
    definition:
      "Valor esperado do retorno por unidade apostada. EV positivo indica vantagem matematica a longo prazo.",
    example: "EV +5.2% = para cada R$100 apostados, espera-se ganhar R$5,20",
  },
  {
    term: "ECE (Expected Calibration Error)",
    category: "metrica",
    definition:
      "Erro medio de calibracao — quao distante as probabilidades previstas estao da frequencia real observada.",
  },

  // ── Markets ──
  {
    term: "1X2",
    category: "mercado",
    definition: "Resultado final: 1 = vitoria mandante, X = empate, 2 = vitoria visitante.",
  },
  {
    term: "Over/Under",
    category: "mercado",
    definition:
      "Mais ou menos gols que a linha. Ex: Over 2.5 = 3 ou mais gols na partida.",
    example: "Under 2.5 gols — a partida precisa ter 0, 1 ou 2 gols",
  },
  {
    term: "BTTS",
    category: "mercado",
    definition:
      "Both Teams To Score — ambas as equipes marcam pelo menos um gol na partida.",
  },
  {
    term: "Dupla Chance",
    category: "mercado",
    definition:
      "Cobre dois resultados: 1X (casa ou empate), 12 (casa ou fora), X2 (empate ou fora).",
  },
  {
    term: "Escanteios",
    category: "mercado",
    definition:
      "Total de escanteios na partida. Linhas de 4.5 a 12.5. Motor v2 bidirecional com calibracao per-league.",
  },

  // ── Model ──
  {
    term: "Dixon-Coles",
    category: "modelo",
    definition:
      "Extensao do modelo Poisson que adiciona correlacao entre gols dos dois times via parametro rho (rho). Corrige o fato de que placares baixos (0-0, 1-0, 0-1, 1-1) tem frequencia diferente do Poisson puro.",
  },
  {
    term: "Lambda (L)",
    category: "modelo",
    definition:
      "Media de gols esperados por time. Base do calculo Poisson. Combina dados da temporada, jogos recentes e xG com pesos calibrados.",
  },
  {
    term: "Rho (r)",
    category: "modelo",
    definition:
      "Parametro de correlacao Dixon-Coles. Calibrado per-league. Ajusta probabilidade de placares baixos para refletir a realidade.",
  },
  {
    term: "Deflacao",
    category: "modelo",
    definition:
      "Fator multiplicador (0.80-1.50) aplicado aos lambdas para corrigir vieses sistematicos. Calibrado automaticamente per-league via Brier score.",
  },
];

export const GLOSSARY_CATEGORIES = {
  todos: "Todos",
  classificacao: "Classificacoes",
  metrica: "Metricas",
  mercado: "Mercados",
  modelo: "Modelo",
} as const;
