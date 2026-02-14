import { google } from '@ai-sdk/google';
import { generateText } from 'ai';

export async function GET() {
  try {
    // Simulando dados que seu sistema enviaria (xG, Histórico, etc)
    const dadosDoJogo = `
      Jogo: Flamengo x Palmeiras
      Contexto: Brasileirão Série A, Rodada 30.
      
      Métricas Recentes (5 jogos):
      - Flamengo (Casa): xG Médio 2.1, Gols Marcados 1.2 (Sub-performance ofensiva). Posse 62%.
      - Palmeiras (Fora): xG Concedido 0.8, Clean Sheets 3/5. Joga em contra-ataque.
      
      Histórico: Nos últimos 3 confrontos diretos, houve menos de 2.5 gols.
    `;

    const { text } = await generateText({
      // Usando o modelo mais potente da sua lista para raciocínio complexo
      model: google('gemini-3-pro-preview'), 
      
      // Prompt focado em análise tática e de valor
      prompt: `Atue como um analista de performance sênior. Com base APENAS nestes dados brutos, gere um mini-relatório pré-jogo:
      ${dadosDoJogo}
      
      Destaque:
      1. O conflito tático principal (ex: Posse vs Contra-ataque).
      2. Uma previsão baseada na métrica de xG vs Gols reais.`,
    });

    return Response.json({ 
      status: 'Análise Realizada com Gemini 3 Pro', 
      resultado: text 
    });

  } catch (error: any) {
    console.error("Erro na análise:", error);
    return Response.json({ 
      status: 'Erro', 
      erro: error.message 
    }, { status: 500 });
  }
}