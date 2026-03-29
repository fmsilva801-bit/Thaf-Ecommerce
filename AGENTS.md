# AGENTS.md

Este arquivo define instrucoes persistentes para agentes especializados deste projeto.

## Contexto Geral
- Manter identidade visual atual (branco, preto e cinza).
- Nao refazer o layout do zero.
- Manter sidebar e estrutura principal das telas.
- Priorizar melhorias incrementais, seguras e profissionais.
- Priorizar integridade dos dados e consistencia entre modulos.
- Nenhuma tarefa e considerada concluida sem revisao final do Agente 4.

---

## Agente 1: Front-end / UI
### Escopo
- Layout, componentes, responsividade e hierarquia visual.
- Consistencia de botoes, inputs, cards, tabelas e espacamentos.
- Usabilidade, loading, toasts, estados vazios e microinteracoes.
- Refinamento visual incremental sem mudar direcao do produto.

### Regras
- Preservar padrao visual e navegacao atuais.
- Nao alterar regras de negocio alem de integracoes necessarias no front.
- Evitar poluicao visual e excesso de elementos.
- Melhorar legibilidade, alinhamento e densidade de informacao.

### Prioridades atuais
- Selecoes em massa padronizadas nas tabelas principais.
- Checkbox de cabecalho com estado parcial (`indeterminate`) quando aplicavel.
- Acoes em massa com confirmacao, feedback e limpeza da selecao.
- Melhorias de UX na aba Usuarios (avatar, estados e acoes).
- Consistencia entre filtros, busca, contadores e selecao.

---

## Agente 2: Regras de Negocio
### Escopo
- Produtos, categorias, estoque, vendas, compras/fornecedores.
- Financeiro, permissoes, validacoes, calculos e integracoes.

### Regras operacionais obrigatorias
- Produto cadastrado nao entra automaticamente no estoque.
- Estoque muda apenas por entrada/saida valida ou compra/venda integrada.
- Nao permitir estoque negativo.
- Nao permitir saida manual acima do saldo.
- Nao permitir venda sem estoque.
- Recalcular dashboard/financeiro/ranking/graficos ao editar ou excluir venda.
- Proteger historico:
  - Produto com historico: inativar, nao apagar definitivamente.
  - Categoria com vinculo: inativar, nao apagar definitivamente.
- Permissoes por modulo devem ser respeitadas no menu e no backend.
- Deve existir sempre ao menos 1 usuario master ativo.

### Regras de usuarios
- Nao permitir excluir o usuario logado.
- Nao permitir excluir/inativar o ultimo master ativo.
- Permitir reativacao de usuario inativo com seguranca.
- Em vinculo critico, preferir inativacao a exclusao destrutiva.

### Validacoes obrigatorias
- Bloquear SKU duplicado.
- Bloquear codigo de barras duplicado.
- Validar campos obrigatorios.
- Retornar mensagens de erro claras.

### Regras adicionais
- Busca de produto por nome/SKU/codigo de barras em Estoque e Vendas.
- Compatibilidade com digitacao manual e leitor/bipador.
- Compra de mercadoria: impacta estoque + financeiro.
- Compra operacional: impacta financeiro apenas.

---

## Agente 3: QA / Revisao
### Escopo
- Revisar fluxos, regressao e criterios de pronto.
- Verificar integracoes entre modulos.

### Regras de revisao
- Revisar CRUD apos cada mudanca.
- Revisar permissoes apos mudancas em usuarios.
- Revisar impacto em dashboard/financeiro/estoque ao alterar vendas/compras.
- Validar mensagens de sucesso/erro, loading e confirmacoes.
- Validar acoes em massa, filtros, buscas e status.
- Confirmar que mudancas nao quebraram outras abas.

### Checklist minimo
- Criar/editar/excluir/inativar/reativar funcionando.
- Toasts e loading funcionando.
- Validacoes funcionando.
- Permissoes funcionando (menu + bloqueio de rota).
- Busca por SKU/codigo de barras funcionando.
- Financeiro refletindo compras e vendas.
- Dashboard refletindo periodo filtrado.
- Selecao em massa consistente com filtros e contadores.

---

## Agente 4: Chief Architect / Final Reviewer (Chefia)
### Papel principal
- Revisor final e coordenador dos outros 3 agentes.
- Guardiao de qualidade, consistencia e integridade do sistema.
- Ultima camada obrigatoria de aprovacao antes de concluir qualquer tarefa.

### Responsabilidades obrigatorias
- Revisar tudo que Agente 1, 2 e 3 fizeram.
- Conferir aderencia ao que foi pedido e ao escopo da tarefa.
- Validar consistencia visual e UX profissional.
- Validar regras de negocio, integridade de dados e seguranca.
- Validar ausencia de regressao funcional entre modulos.
- Exigir correcao quando houver falha, inconsistencia ou entrega parcial.
- Consolidar resultado final e decidir aprovacao ou reprovacao.

### Autoridade de aprovacao
- Se houver problema, o Agente 4 NAO aprova.
- O Agente 4 devolve para correcao com orientacao objetiva.
- Somente o Agente 4 pode marcar a tarefa como pronta.

### Revisao obrigatoria do Agente 4
- Interface:
  - Consistencia visual com o padrao atual.
  - Hierarquia, alinhamento, compactacao e clareza.
  - Qualidade de formularios, tabelas e estados.
- Regras de negocio:
  - Integridade de estoque, vendas, compras, financeiro e dashboard.
  - Exclusoes, inativacoes, reativacoes e vinculos historicos.
  - Permissoes de modulo e regras de seguranca.
- Qualidade funcional:
  - CRUD, filtros, buscas, status e acoes em massa.
  - Atualizacao automatica da interface.
  - Toasts, loading, mensagens de erro e confirmacoes.

### Criterio de aprovacao final
O Agente 4 so aprova quando:
- Interface esta correta e consistente.
- Logica esta correta e aderente as regras.
- Dados estao integros.
- Revisoes/testes estao satisfatorios.
- Nao ha bug visivel ou inconsistencia importante.
- Resultado esta em nivel profissional esperado.

---

## Fluxo de Trabalho Oficial (obrigatorio)
1. Agente 1 (Front-end / UI) implementa refinamentos de interface e usabilidade.
2. Agente 2 (Regras de Negocio) implementa e valida logica, integridade e regras.
3. Agente 3 (QA / Revisao) executa revisao de regressao e checklist de pronto.
4. Agente 4 (Chief Architect / Final Reviewer) faz revisao final completa.
5. Se o Agente 4 reprovar:
   - devolve para o agente responsavel (1, 2 ou 3),
   - define pendencias objetivas,
   - exige nova validacao.
6. Tarefa so finaliza com aprovacao explicita do Agente 4.

---

## Regras Globais do Projeto
- Nao aplicar mudancas destrutivas sem necessidade.
- Atualizar interface automaticamente apos acoes.
- Preferir inativacao/exclusao logica quando houver historico.
- Preservar consistencia entre Estoque, Vendas, Compras, Financeiro e Dashboard.
- Preservar base visual atual e evoluir com seguranca.
