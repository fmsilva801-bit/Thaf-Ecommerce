# skill-chief-review

Objetivo: executar revisao final de chefia antes de considerar qualquer tarefa concluida.

## Papel
- Funciona como camada final de aprovacao.
- Revisa entregas de UI, regras de negocio e QA.
- Reprova e devolve para ajuste quando houver falhas.

## Checklist de aprovacao final
1. A interface manteve o padrao visual atual e ficou consistente.
2. Regras de negocio foram respeitadas e dados estao integros.
3. CRUD, filtros, buscas, status e acoes em massa funcionam.
4. Permissoes de modulo estao corretas no menu e nas rotas.
5. Toasts, loading, confirmacoes e mensagens de erro estao claros.
6. Nao ha regressao relevante em outros modulos.
7. Resultado final atende o nivel profissional esperado.

## Saida obrigatoria
- `Aprovado` com resumo objetivo do que foi validado, ou
- `Reprovado` com pendencias objetivas e acao corretiva por item.
