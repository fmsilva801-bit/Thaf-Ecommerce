# skill-qa-checklist

Objetivo: executar revisão funcional de ponta a ponta após mudanças.

## Passo a passo
1. Validar login e permissões por módulo.
2. Validar CRUD principal: produtos, categorias, vendas, compras, financeiro, usuários.
3. Validar buscas (nome/SKU/código de barras) em estoque e vendas.
4. Validar regras de estoque e vendas (sem saldo negativo).
5. Validar reflexos no financeiro e dashboard.
6. Validar mensagens de sucesso/erro, loading e confirmações.

## Critérios de pronto
- Fluxos críticos funcionando sem regressão.
- Erros claros para usuário.
- Dados consistentes entre módulos.
- Sem quebra de layout principal.
