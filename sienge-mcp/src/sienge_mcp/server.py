from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from fastmcp import FastMCP


def load_local_env() -> None:
    """Load .env.local from likely local install locations.

    Claude Desktop may not always launch the server with the expected working
    directory, so relying only on Path.cwd() can make credentials invisible.
    """
    candidates = [
        Path.cwd() / ".env.local",
        Path(__file__).resolve().parents[2] / ".env.local",
    ]

    seen: set[Path] = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.exists():
            load_dotenv(candidate, override=False)


load_local_env()

from sienge_mcp.tools.contratos import listar_contratos_sienge
from sienge_mcp.tools.medicoes import criar_medicoes_contratos_sienge

mcp = FastMCP("sienge-mcp")

mcp.tool(
    name="criar_medicoes_contratos_sienge",
    description=(
        "Cria ou simula medicoes mensais de contratos no Sienge. "
        "Recebe uma lista de contratos com numero_contrato, valor, obra ou building_id, "
        "quantidade_itens opcional, data_medicao, data_vencimento ou dia_vencimento, "
        "e dry_run para simular sem enviar."
    ),
)(criar_medicoes_contratos_sienge)

mcp.tool(
    name="listar_contratos_sienge",
    description=(
        "Consulta contratos do Sienge por GET read-only. "
        "Calcula automaticamente contractStartDate e contractEndDate quando "
        "data_inicio/data_fim nao forem informadas, aceita filtros como building_id, "
        "company_id, limite, offset e somente_ativos, e resume os contratos retornados."
    ),
)(listar_contratos_sienge)


def main() -> None:
    mcp.run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
