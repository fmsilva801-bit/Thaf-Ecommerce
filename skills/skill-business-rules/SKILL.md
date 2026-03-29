# skill-business-rules

Objetivo: garantir integridade de regras operacionais e integrações entre módulos.

## Regras núcleo
- Produto não entra no estoque ao cadastrar.
- Não permitir estoque negativo.
- Não permitir venda sem estoque.
- Compra de mercadoria impacta estoque + financeiro.
- Compra operacional impacta apenas financeiro.
- Exclusão com histórico deve virar inativação quando aplicável.

## Validações obrigatórias
1. SKU único.
2. Código de barras único.
3. Campos obrigatórios com erro claro.
4. Permissões por módulo respeitadas no backend.

## Verificações de integração
- Vendas: atualiza estoque, financeiro, dashboard.
- Compras: atualiza estoque/financeiro conforme tipo.
- Edição/exclusão: reverte e recalcula impactos corretamente.
