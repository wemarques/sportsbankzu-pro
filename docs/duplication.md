# Relatório de Duplicação

Comparação: app.py (raiz) vs streamlit/app.py

Observações:
- Ambos implementam UI em Streamlit consumindo BACKEND_URL
- Estruturas semelhantes de fetch (fixtures, decision/pre), layout e geração de quadro-resumo
- Diferenças pontuais em helpers e apresentação (componentes HTML, métricas)

Conclusão:
- Duplicação alta entre os dois arquivos (interface e chamadas de API similares)
- Recomenda-se manter um único ponto de entrada Streamlit e remover o duplicado após consolidação
