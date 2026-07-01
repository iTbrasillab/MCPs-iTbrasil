# Sienge MCP

Servidor MCP em Python para operar integrações com o Sienge usando FastMCP.

Esta primeira versão entrega a tool `criar_medicoes_contratos_sienge`, que cria ou simula payloads de medições mensais de contratos. O endpoint de criação ainda fica configurável por `SIENGE_MEDICOES_ENDPOINT_PATH`, para ser ajustado quando o endpoint oficial for confirmado.

## Requisitos

- Python 3.10 ou superior
- FastMCP
- httpx
- Pydantic

## Instalação

Dentro desta pasta:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Para executar localmente:

```bash
sienge-mcp
```

## Configuração

Copie `.env.example` para `.env` no ambiente que executa o MCP e preencha:

```bash
SIENGE_API_KEY=
SIENGE_USERNAME=
SIENGE_PASSWORD=
SIENGE_SUBDOMAIN=sua-empresa
SIENGE_BASE_URL=https://api.sienge.com.br/{subdomain}/public/api/v1
SIENGE_MEDICOES_ENDPOINT_PATH=/contracts/measurements
SIENGE_AUTH_TEST_ENDPOINT_PATH=/companies
SIENGE_REQUEST_TIMEOUT=30
```

Use `SIENGE_USERNAME` e `SIENGE_PASSWORD` para Basic Authorization, conforme a documentação oficial do Sienge. `SIENGE_API_KEY` também é aceito pelo pacote caso seu ambiente use bearer token. Os valores não são registrados em logs.

## Teste de autenticação

Não cole credenciais em chats ou logs. Crie um arquivo local `.env.local`, que é ignorado pelo Git:

```bash
SIENGE_USERNAME=usuario-api
SIENGE_PASSWORD=senha
SIENGE_SUBDOMAIN=minhaempresa
SIENGE_AUTH_TEST_ENDPOINT_PATH=/companies
```

Execute:

```bash
sienge-mcp-auth-check --env-file .env.local
```

O comando imprime apenas `status`, `http_status`, `mensagem`, `base_url`, `endpoint_path`, método de autenticação e resposta do Sienge. Ele não imprime usuário, senha, API key ou header `Authorization`.

Interpretação principal:

- `200-299`: autenticação validada
- `401`: falha de autenticação
- `403`: credencial existe, mas a permissão/API precisa ser verificada com o gerenciador
- `404`: endpoint de teste incorreto; ajuste `SIENGE_AUTH_TEST_ENDPOINT_PATH` para um GET read-only disponível no seu pacote Sienge

## Claude Desktop

Depois de instalar o pacote no mesmo ambiente em que o Claude Desktop executa MCP servers:

```json
{
  "mcpServers": {
    "sienge": {
      "command": "sienge-mcp",
      "args": [],
      "env": {
        "SIENGE_API_KEY": "preencher-no-ambiente-seguro",
        "SIENGE_SUBDOMAIN": "sua-empresa",
        "SIENGE_BASE_URL": "https://api.sienge.com.br/{subdomain}/public/api/v1",
        "SIENGE_MEDICOES_ENDPOINT_PATH": "/contracts/measurements"
      }
    }
  }
}
```

## Codex

Para usar no Codex, instale o pacote localmente e configure o MCP server no arquivo de configuração do Codex. Como o servidor carrega `.env.local` automaticamente quando executado com `cwd` na pasta do projeto, mantenha os segredos no `.env.local` e não no arquivo de configuração.

Exemplo de `.env.local`:

```bash
SIENGE_USERNAME=usuario
SIENGE_PASSWORD=senha
SIENGE_SUBDOMAIN=seu-subdominio
SIENGE_BASE_URL=https://api.sienge.com.br/seu-subdominio/public/api/v1
SIENGE_MEDICOES_ENDPOINT_PATH=/CONFIRMAR_ENDPOINT_OFICIAL_DE_CRIACAO
```

Exemplo para `~/.codex/config.toml`:

```toml
[mcp_servers.sienge]
command = "C:\\MCP\\sienge-mcp\\.venv\\Scripts\\python.exe"
args = ["-m", "sienge_mcp.server"]
cwd = "C:\\MCP\\sienge-mcp"
```

Prompt de teste GET read-only:

```text
Use o MCP Sienge e liste os contratos ativos, limite 5.
Não use POST.
```

O agente deve chamar `listar_contratos_sienge` sem exigir datas; a tool usa automaticamente os últimos 365 dias.

## Tool

### `listar_contratos_sienge`

Consulta contratos do Sienge com `GET /supply-contracts/all`. A tool calcula automaticamente `contractStartDate` e `contractEndDate` quando o usuário não informa datas.

Parâmetros principais:

- `data_inicio`: opcional, data ISO `YYYY-MM-DD`
- `data_fim`: opcional, data ISO `YYYY-MM-DD`; padrão: data atual
- `periodo_dias`: opcional; padrão: `365`
- `limite`: opcional; padrão: `10`, máximo `200`
- `offset`: opcional; padrão: `0`
- `building_id`: opcional
- `company_id`: opcional
- `somente_ativos`: opcional; padrão: `true`

Exemplo de prompt:

```text
Liste os contratos ativos no Sienge, limite 5.
```

Isso chama a tool sem exigir que a pessoa informe datas; o agente usa automaticamente o período dos últimos 365 dias.

### `criar_medicoes_contratos_sienge`

`criar_medicoes_contratos_sienge`

Parametros:

- `contratos`: lista de contratos
- `data_medicao`: data ISO `YYYY-MM-DD`; se omitida, usa a data atual
- `data_vencimento`: data ISO `YYYY-MM-DD`, opcional
- `dia_vencimento`: dia do mês da medição, opcional
- `dry_run`: `true` por padrão para simular sem enviar ao Sienge

Exemplo de chamada:

```json
{
  "contratos": [
    {
      "numero_contrato": "CT/EXEMPLO-001",
      "valor": 1234.56,
      "obra": "Obra Exemplo Alpha"
    },
    {
      "numero_contrato": "CT/EXEMPLO-002",
      "valor": 2345.67,
      "obra": "Obra Exemplo Beta"
    },
    {
      "numero_contrato": "CT/EXEMPLO-003",
      "valor": 3456.78,
      "building_id": 101
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

Cada contrato retorna:

- `contrato`
- `status`: `sucesso`, `erro` ou `simulado`
- `http_status`
- `mensagem`
- `payload_enviado`
- `resposta_sienge`

Mensagens especiais:

- `422`: `há medição anterior pendente de autorização no Sienge`
- `403`: `permissões de API foram alteradas; verificar com o gerenciador`
- `401`: `falha de autenticação`
- timeout: `tempo limite excedido`

## Prompt final para o usuário

```text
Crie as medições mensais no Sienge para estes contratos:
- CT/EXEMPLO-001 - R$ 1.234,56/mês - Obra Exemplo Alpha
- CT/EXEMPLO-002 - R$ 2.345,67/mês - Obra Exemplo Beta
- CT/EXEMPLO-003 - R$ 3.456,78/mês - buildingId 101
- CT/EXEMPLO-004 - R$ 4.568,00/mês - buildingId 101, 2 itens

Use data de medição hoje e vencimento dia 25.
Execute primeiro em dry_run=true e reporte o resultado completo.
Se eu confirmar, execute com dry_run=false.
Ao final, responda com uma tabela: contrato | valor | status | mensagem.
```

## Testes

```bash
pytest
```

Os testes cobrem:

- validação Pydantic de contrato
- montagem de payload
- cálculo de vencimento por dia do mês
- modo `dry_run`
- tratamento de `422`, `403`, `401` e timeout
