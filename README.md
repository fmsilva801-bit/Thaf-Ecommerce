# Plataforma de Gestão para E-commerce

MVP funcional com:
- Login por usuário (master/admin/member)
- Cadastro de produtos com custo base + custos adicionais fixos e percentuais
- Cálculo de custo total, lucro estimado e preço sugerido por margem desejada
- Controle de estoque (entrada e saída)
- Registro de vendas com baixa automática de estoque e entrada financeira
- Financeiro (ganhos e gastos)
- Dashboard com KPIs, gráfico mensal e ranking de produtos
- Interface preta, branca e tons de cinza

## Como rodar

1. No terminal, dentro da pasta do projeto:

```powershell
python app.py
```

2. Acesse no navegador:

[http://127.0.0.1:8000](http://127.0.0.1:8000)

## Usuário inicial

- Email: `master@admin.local`
- Senha: `admin123`

Recomendação: após o primeiro acesso, crie novos usuários para operação diária.

## Estrutura

- `app.py`: servidor HTTP + API + banco SQLite
- `data/ecommerce.db`: banco criado automaticamente
- `static/index.html`: interface
- `static/styles.css`: estilo visual
- `static/app.js`: lógica frontend
