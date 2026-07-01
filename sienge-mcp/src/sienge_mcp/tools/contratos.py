from __future__ import annotations

from datetime import date
from typing import Any
from urllib.parse import urlencode

import httpx

from sienge_mcp.client import SiengeApiResponse, SiengeClient
from sienge_mcp.config import SiengeSettings
from sienge_mcp.models import (
    ContratoResumo,
    ListarContratosRequest,
    ListarContratosResponse,
)


CONTRATOS_ENDPOINT_PATH = "/supply-contracts/all"
STATUS_ATIVOS = {"PENDING", "PARTIALLY_MEASURED"}


async def listar_contratos_sienge(
    data_inicio: str | None = None,
    data_fim: str | None = None,
    periodo_dias: int = 365,
    limite: int = 10,
    offset: int = 0,
    building_id: int | None = None,
    company_id: int | None = None,
    status_aprovacao: str | None = None,
    autorizacao: str | None = None,
    consistencia: str | None = None,
    somente_ativos: bool = True,
) -> dict[str, Any]:
    """Lista contratos do Sienge por GET, calculando datas quando omitidas."""
    entrada: dict[str, Any] = {
        "periodo_dias": periodo_dias,
        "limite": limite,
        "offset": offset,
        "somente_ativos": somente_ativos,
    }

    if data_inicio is not None:
        entrada["data_inicio"] = data_inicio
    if data_fim is not None:
        entrada["data_fim"] = data_fim
    if building_id is not None:
        entrada["building_id"] = building_id
    if company_id is not None:
        entrada["company_id"] = company_id
    if status_aprovacao is not None:
        entrada["status_aprovacao"] = status_aprovacao
    if autorizacao is not None:
        entrada["autorizacao"] = autorizacao
    if consistencia is not None:
        entrada["consistencia"] = consistencia

    request = ListarContratosRequest.model_validate(entrada)
    response = await processar_listagem_contratos(request)
    return response.model_dump(mode="json")


async def processar_listagem_contratos(
    request: ListarContratosRequest,
    client: SiengeClient | None = None,
) -> ListarContratosResponse:
    settings = SiengeSettings.from_env()
    owns_client = client is None
    client = client or SiengeClient(settings=settings)
    endpoint_path = montar_endpoint_contratos(request)

    try:
        api_response = await _get_contratos(client, endpoint_path)
    finally:
        if owns_client:
            await client.aclose()

    if api_response.status_code is None or not (200 <= api_response.status_code < 300):
        return ListarContratosResponse(
            status="erro",
            http_status=api_response.status_code,
            mensagem=_mensagem_from_response(api_response),
            endpoint_path=endpoint_path,
            filtros=_filtros_response(request),
            total_sienge=None,
            total_retornado=0,
            contratos=[],
            resposta_sienge=api_response.body,
        )

    contratos_raw = _results(api_response.body)
    if request.somente_ativos:
        contratos_raw = [
            contrato for contrato in contratos_raw if contrato.get("status") in STATUS_ATIVOS
        ]

    contratos = [_resumir_contrato(contrato) for contrato in contratos_raw]

    return ListarContratosResponse(
        status="sucesso",
        http_status=api_response.status_code,
        mensagem="Contratos consultados com sucesso no Sienge.",
        endpoint_path=endpoint_path,
        filtros=_filtros_response(request),
        total_sienge=_total_sienge(api_response.body),
        total_retornado=len(contratos),
        contratos=contratos,
        resposta_sienge=None,
    )


def montar_endpoint_contratos(request: ListarContratosRequest) -> str:
    data_inicio, data_fim = request.obter_periodo()
    params: dict[str, Any] = {
        "contractStartDate": data_inicio.isoformat(),
        "contractEndDate": data_fim.isoformat(),
        "limit": request.limite,
        "offset": request.offset,
    }

    if request.building_id is not None:
        params["buildingId"] = request.building_id
    if request.company_id is not None:
        params["companyId"] = request.company_id
    if request.status_aprovacao is not None:
        params["statusApproval"] = request.status_aprovacao
    if request.autorizacao is not None:
        params["authorization"] = request.autorizacao
    if request.consistencia is not None:
        params["consistency"] = request.consistencia

    return f"{CONTRATOS_ENDPOINT_PATH}?{urlencode(params)}"


async def _get_contratos(
    client: SiengeClient,
    endpoint_path: str,
) -> SiengeApiResponse:
    try:
        return await client.get_json(endpoint_path)
    except httpx.TimeoutException:
        return SiengeApiResponse(
            status_code=None,
            error_type="timeout",
            message="tempo limite excedido",
        )
    except httpx.RequestError as exc:
        return SiengeApiResponse(
            status_code=None,
            error_type="request_error",
            message=str(exc),
        )


def _mensagem_from_response(response: SiengeApiResponse) -> str:
    if response.error_type == "timeout":
        return "tempo limite excedido"

    if response.status_code == 401:
        return "falha de autenticação"

    if response.status_code == 403:
        return "permissões de API foram alteradas; verificar com o gerenciador"

    if isinstance(response.body, dict):
        for key in ("clientMessage", "developerMessage", "message", "error"):
            value = response.body.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    return response.message or "Erro retornado pelo Sienge."


def _results(body: Any) -> list[dict[str, Any]]:
    if not isinstance(body, dict):
        return []

    results = body.get("results")
    if not isinstance(results, list):
        return []

    return [item for item in results if isinstance(item, dict)]


def _total_sienge(body: Any) -> int | None:
    if not isinstance(body, dict):
        return None

    metadata = body.get("resultSetMetadata")
    if not isinstance(metadata, dict):
        return None

    count = metadata.get("count")
    return count if isinstance(count, int) else None


def _resumir_contrato(contrato: dict[str, Any]) -> ContratoResumo:
    return ContratoResumo(
        document_id=contrato.get("documentId"),
        numero_contrato=contrato.get("contractNumber"),
        fornecedor=contrato.get("supplierName"),
        status=contrato.get("status"),
        status_aprovacao=contrato.get("statusApproval"),
        autorizado=contrato.get("isAuthorized"),
        data_contrato=contrato.get("contractDate"),
        data_inicio=contrato.get("startDate"),
        data_fim=contrato.get("endDate"),
        empresa=contrato.get("companyName"),
        company_id=contrato.get("companyId"),
        obras=_obras(contrato),
        valor_mao_obra=contrato.get("totalLaborValue"),
        valor_material=contrato.get("totalMaterialValue"),
        objeto=contrato.get("object"),
    )


def _obras(contrato: dict[str, Any]) -> list[dict[str, Any]]:
    buildings = contrato.get("buildings")
    if not isinstance(buildings, list):
        return []

    obras: list[dict[str, Any]] = []
    for building in buildings:
        if not isinstance(building, dict):
            continue
        obras.append(
            {
                "building_id": building.get("buildingId"),
                "nome": building.get("name"),
            }
        )
    return obras


def _filtros_response(request: ListarContratosRequest) -> dict[str, Any]:
    data_inicio, data_fim = request.obter_periodo()
    return {
        "data_inicio": data_inicio.isoformat(),
        "data_fim": data_fim.isoformat(),
        "periodo_dias": request.periodo_dias,
        "limite": request.limite,
        "offset": request.offset,
        "building_id": request.building_id,
        "company_id": request.company_id,
        "status_aprovacao": request.status_aprovacao,
        "autorizacao": request.autorizacao,
        "consistencia": request.consistencia,
        "somente_ativos": request.somente_ativos,
    }
