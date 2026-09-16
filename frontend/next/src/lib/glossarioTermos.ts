/** #257 — os dez termos do glossário (spec §5), com exemplo numérico real
 * (mesmos números do card de exemplo da spec §4.1: Toronto × Nashville SC). */
export interface TermoGlossario { id: string; titulo: string; explicacao: string; exemplo: string }

export const TERMOS: TermoGlossario[] = [
  { id: "chance", titulo: "Chance", explicacao: "a frequência que o modelo espera para esse resultado, em cada 100 jogos parecidos.", exemplo: "58 em cada 100 jogos assim terminam com mais de 6,5 escanteios." },
  { id: "minimo", titulo: "Mínimo", explicacao: "a odd abaixo da qual apostar deixa de valer a pena, dada a chance calculada.", exemplo: "com chance de 58%, vale a partir de 1,67." },
  { id: "paga", titulo: "Paga", explicacao: "a odd que a casa de apostas está oferecendo agora para esse mercado.", exemplo: "mercado paga 1,75." },
  { id: "edge", titulo: "Edge", explicacao: "a diferença entre a chance calculada e a chance implícita na odd da casa — quanto maior, mais a odd está \"errada\" a favor de quem aposta.", exemplo: "chance 58% − chance implícita em 1,75 (57%) = edge de 0,01 (1pp)." },
  { id: "stake", titulo: "Stake", explicacao: "quanto apostar nesse pick, calculado como uma fração da sua banca pelo critério de Kelly, reduzido a um quarto por segurança.", exemplo: "numa banca de R$ 1.000, um pick com edge de 8pp sugere R$ 25." },
  { id: "jogos-medidos", titulo: "Jogos medidos", explicacao: "quantos jogos dessa liga entraram na conta de acerto que o painel mostra — quanto menor, menos confiável é a média.", exemplo: "MLS: 40 jogos medidos." },
  { id: "calibracao", titulo: "Calibração", explicacao: "o quanto as chances que o painel diz batem com o que de fato acontece, olhando muitos picks juntos.", exemplo: "quando o painel disse 60, aconteceu 57 em cada 100." },
  { id: "brier", titulo: "Brier", explicacao: "uma nota de erro da previsão: quanto menor, melhor calibrado está o modelo. Zero é perfeito, 0,25 é o mesmo que \"não sei\".", exemplo: "Brier de 0,2529 nos últimos 30 dias." },
  { id: "direcao", titulo: "Direção", explicacao: "quando o modelo aponta um lado mas não há preço bom o bastante para recomendar apostar.", exemplo: "Direção: mais de 2,5 gols, 57 em cada 100 — sem preço que valha hoje." },
  { id: "corredor", titulo: "Corredor", explicacao: "mercados que se sobrepõem (ex.: mais de 2,5 gols e ambos marcam) não competem pelo talão ao mesmo tempo, para não recomendar duas apostas que dependem do mesmo resultado.", exemplo: "Over 1,5, Over 2,5 e Over 3,5 gols são o mesmo corredor: só um deles vira talão por jogo." },
];
