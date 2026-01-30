# Plano de Integração Finalizado: FootyStats API

Após a análise detalhada dos leiautes dos arquivos CSV e da documentação da API FootyStats, elaborei o plano de execução final. A integração usará os dados em tempo real da API, mantendo a compatibilidade com a estrutura de dados profunda (mais de 400 colunas) que o sistema já suporta.

## 1. Mapeamento de Dados (Data Mapping)
- **Normalização**: Criar um tradutor que converte os campos da API FootyStats para o formato dos nossos arquivos CSV (ex: `team_a_xg` da API para a coluna `home_team_xg` do nosso processador).
- **Consistência**: Garantir que as métricas de "Pre-Match Potential" (BTTS, Over 2.5, Corners) sejam extraídas da API para alimentar o Mistral Auditor.

## 2. Desenvolvimento do Core (Backend)
- **Cliente `footstats_client.py`**: 
    - Implementar métodos para buscar partidas (`league-matches`), tabelas (`league-tables`) e detalhes de jogos individuais (`match`).
    - Adicionar suporte a **Lineups (Escalações)** e **Trends (Tendências)**, conforme identificado nos arquivos de detalhes de partida.
- **Sistema de Fallback**: O backend tentará a API primeiro; se falhar, lerá os arquivos CSV da pasta `C:\Users\wxamb\futebol\data` como backup.

## 3. Mapeamento das 22 Ligas
- **Configuração de IDs**: Mapear as 22 ligas solicitadas (Brasil Série A/B, Premier League, etc.) com seus respectivos `country_id` e `season_id` da FootyStats.
- **Filtro Geográfico**: Implementar a lógica de "País - Liga" no seletor para evitar ambiguidades.

## 4. Atualização da Interface (Frontend)
- **Seletor de Ligas**: Atualizar o arquivo [leagues.ts](file:///c:/painel_apostas/sportsbank-pro/frontend/next/src/lib/leagues.ts) com as 22 novas opções.
- **Tooltips Ocre**: Implementar os tooltips informativos com a cor ocre saturada conforme solicitado, explicando a origem dos dados (API vs Histórico).

## 5. Deploy e Sincronização
- **AWS Lambda**: Atualizar a função Lambda via S3 com as novas bibliotecas e configurações de ambiente.
- **Banco de Dados**: Sincronizar os metadados das ligas para que o dashboard mostre os logos e nomes corretos.

**Posso iniciar a execução seguindo este fluxo?**
