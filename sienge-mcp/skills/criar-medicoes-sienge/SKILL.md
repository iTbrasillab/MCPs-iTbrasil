---
name: criar-medicoes-sienge
description: Operar criação de medições, cobranças, medições mensais ou medições de contratos no Sienge via MCP. Use quando a usuária pedir para criar, simular ou reportar medições/cobranças de contratos Sienge em linguagem natural.
---

# Criar medições Sienge

## Fluxo

Ao receber um pedido de criação de medições, cobranças, medições mensais ou medições de contratos no Sienge:

1. Extrair do prompt:
   - número do contrato
   - valor
   - obra ou `building_id`
   - quantidade de itens, se houver
   - data de medição
   - data de vencimento ou dia de vencimento
2. Se a data de medição não for informada, usar a data atual.
3. Se o vencimento vier como "dia 25", calcular o dia 25 do mesmo mês da medição e enviar `dia_vencimento: 25`.
4. Chamar a tool MCP `criar_medicoes_contratos_sienge`.
5. Nunca pedir caminho de script local.
6. Nunca pedir para a usuaria executar `pip install` ou `python` manualmente.
7. Ao final, responder com uma tabela:

```text
contrato | valor | status | mensagem
```

## Entrada da tool

Use este formato:

```json
{
  "contratos": [
    {
      "numero_contrato": "CT/EXEMPLO-001",
      "valor": 1234.56,
      "obra": "Obra Exemplo Alpha"
    },
    {
      "numero_contrato": "CT/EXEMPLO-004",
      "valor": 4568.00,
      "building_id": 101,
      "quantidade_itens": 2
    }
  ],
  "data_medicao": "2026-06-26",
  "dia_vencimento": 25,
  "dry_run": true
}
```

Para operações reais, manter `dry_run: true` na primeira rodada quando a usuária pedir apenas para criar ou quando houver qualquer ambiguidade. Executar `dry_run: false` quando a usuária confirmar o envio ao Sienge.

## Resposta

Para cada item retornado pela tool, mapear:

- `contrato`: contrato
- `payload_enviado.amount`: valor
- `status`: status
- `mensagem`: mensagem

Se algum contrato retornar `422`, orientar: "Existe medição anterior pendente de autorização no Sienge. Autorize antes da próxima rodada."

Se algum contrato retornar `403`, orientar: "As permissões da API foram alteradas. Verificar com o gerenciador do Sienge."

## Consulta de contratos

Quando a usuária pedir para listar, consultar, procurar ou validar contratos no Sienge, chamar a tool `listar_contratos_sienge`.

Se a usuária não informar datas, não pedir datas. Usar os defaults da tool, que calculam automaticamente o período dos últimos 365 dias até a data atual.

Para pedidos como "liste contratos ativos", enviar `somente_ativos: true`.

Responder em tabela curta com:

```text
contrato | fornecedor | status | obra | valor
```
