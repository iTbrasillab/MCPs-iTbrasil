from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from sienge_mcp.client import SiengeApiResponse, SiengeClient
from sienge_mcp.config import SiengeSettings


async def testar_autenticacao_sienge(
    endpoint_path: str | None = None,
) -> dict[str, Any]:
    settings = SiengeSettings.from_env()
    path = endpoint_path or settings.auth_test_endpoint_path
    metodo = "bearer" if settings.api_key else "basic"

    client = SiengeClient(settings=settings)
    try:
        response = await client.get_json(path)
    finally:
        await client.aclose()

    return montar_resultado_autenticacao(
        response=response,
        base_url=settings.base_url,
        endpoint_path=path,
        metodo=metodo,
    )


def montar_resultado_autenticacao(
    response: SiengeApiResponse,
    base_url: str,
    endpoint_path: str,
    metodo: str,
) -> dict[str, Any]:
    http_status = response.status_code

    if response.error_type == "timeout":
        status = "erro"
        mensagem = "tempo limite excedido"
    elif http_status == 401:
        status = "erro"
        mensagem = "falha de autenticação"
    elif http_status == 403:
        status = "erro"
        mensagem = "permissões de API foram alteradas; verificar com o gerenciador"
    elif http_status is not None and 200 <= http_status < 300:
        status = "sucesso"
        mensagem = "autenticação validada com sucesso"
    elif http_status == 404:
        status = "indeterminado"
        mensagem = (
            "endpoint de teste não encontrado; ajuste SIENGE_AUTH_TEST_ENDPOINT_PATH "
            "para um recurso GET disponível"
        )
    else:
        status = "erro"
        mensagem = response.message or "erro retornado pelo Sienge"

    return {
        "status": status,
        "http_status": http_status,
        "mensagem": mensagem,
        "base_url": base_url,
        "endpoint_path": endpoint_path,
        "metodo_autenticacao": metodo,
        "resposta_sienge": response.body,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Valida autenticação Sienge sem imprimir credenciais."
    )
    parser.add_argument(
        "--env-file",
        default=".env.local",
        help="Arquivo de variáveis de ambiente. Default: .env.local",
    )
    parser.add_argument(
        "--endpoint-path",
        default=None,
        help="Endpoint GET read-only para testar autenticação.",
    )
    args = parser.parse_args()

    env_path = Path(args.env_file)
    if env_path.exists():
        load_dotenv(env_path)

    resultado = asyncio.run(testar_autenticacao_sienge(args.endpoint_path))
    print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
