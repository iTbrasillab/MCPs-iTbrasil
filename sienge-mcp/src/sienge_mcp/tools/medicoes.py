from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import httpx

from sienge_mcp.client import SiengeApiResponse, SiengeClient
from sienge_mcp.config import SiengeSettings
from sienge_mcp.models import (
    ContratoMedicao,
    CriarMedicoesContratosRequest,
    CriarMedicoesContratosResponse,
    ResultadoMedicaoContrato,
)


CENTAVOS = Decimal("0.01")


async def criar_medicoes_contratos_sienge(
    contratos: list[dict[str, Any]],
    data_medicao: str | None = None,
    data_vencimento: str | None = None,
    dia_vencimento: int | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Cria ou simula medições mensais de contratos no Sienge."""
    entrada: dict[str, Any] = {
        "contratos": contratos,
        "dry_run": dry_run,
    }

    if data_medicao is not None:
        entrada["data_medicao"] = data_medicao
    if data_vencimento is not None:
        entrada["data_vencimento"] = data_vencimento
    if dia_vencimento is not None:
        entrada["dia_vencimento"] = dia_vencimento

    request = CriarMedicoesContratosRequest.model_validate(entrada)
    response = await processar_criacao_medicoes(request)
    return response.model_dump(mode="json")


async def processar_criacao_medicoes(
    request: CriarMedicoesContratosRequest,
    client: SiengeClient | None = None,
    endpoint_path: str | None = None,
) -> CriarMedicoesContratosResponse:
    settings = SiengeSettings.from_env()
    endpoint = endpoint_path or settings.medicoes_endpoint_path
    data_vencimento = request.obter_data_vencimento()
    owns_client = False

    if not request.dry_run and client is None:
        client = SiengeClient(settings=settings)
        owns_client = True

    resultados: list[ResultadoMedicaoContrato] = []

    try:
        for contrato in request.contratos:
            payload = montar_payload_medicao(
                contrato=contrato,
                data_medicao=request.data_medicao,
                data_vencimento=data_vencimento,
            )

            if request.dry_run:
                resultados.append(
                    ResultadoMedicaoContrato(
                        contrato=contrato.numero_contrato,
                        status="simulado",
                        http_status=None,
                        mensagem="Simulação concluída; payload não enviado ao Sienge.",
                        payload_enviado=payload,
                        resposta_sienge=None,
                    )
                )
                continue

            assert client is not None
            api_response = await _post_medicao(client, endpoint, payload)
            resultados.append(
                ResultadoMedicaoContrato(
                    contrato=contrato.numero_contrato,
                    status=_status_from_response(api_response),
                    http_status=api_response.status_code,
                    mensagem=_mensagem_from_response(api_response),
                    payload_enviado=payload,
                    resposta_sienge=api_response.body,
                )
            )
    finally:
        if owns_client and client is not None:
            await client.aclose()

    return CriarMedicoesContratosResponse(
        endpoint_path=endpoint,
        dry_run=request.dry_run,
        total=len(resultados),
        sucessos=sum(1 for item in resultados if item.status == "sucesso"),
        erros=sum(1 for item in resultados if item.status == "erro"),
        simulados=sum(1 for item in resultados if item.status == "simulado"),
        resultados=resultados,
    )


def montar_payload_medicao(
    contrato: ContratoMedicao,
    data_medicao: date,
    data_vencimento: date | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "contractNumber": contrato.numero_contrato,
        "measurementDate": data_medicao.isoformat(),
        "amount": _decimal_to_json_number(contrato.valor),
        "itemsQuantity": contrato.quantidade_itens,
        "items": [
            {
                "sequence": index + 1,
                "amount": _decimal_to_json_number(valor_item),
                "description": f"Medição mensal do contrato {contrato.numero_contrato}",
            }
            for index, valor_item in enumerate(
                _dividir_valor_em_itens(contrato.valor, contrato.quantidade_itens)
            )
        ],
    }

    if data_vencimento is not None:
        payload["dueDate"] = data_vencimento.isoformat()

    if contrato.building_id is not None:
        payload["buildingId"] = contrato.building_id

    if contrato.obra is not None:
        payload["buildingName"] = contrato.obra

    if contrato.observacao is not None:
        payload["notes"] = contrato.observacao

    return payload


async def _post_medicao(
    client: SiengeClient,
    endpoint: str,
    payload: dict[str, Any],
) -> SiengeApiResponse:
    try:
        return await client.post_json(endpoint, payload)
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


def _status_from_response(response: SiengeApiResponse) -> str:
    if response.status_code is not None and 200 <= response.status_code < 300:
        return "sucesso"

    return "erro"


def _mensagem_from_response(response: SiengeApiResponse) -> str:
    if response.error_type == "timeout":
        return "tempo limite excedido"

    if response.status_code == 422:
        return "há medição anterior pendente de autorização no Sienge"

    if response.status_code == 403:
        return "permissões de API foram alteradas; verificar com o gerenciador"

    if response.status_code == 401:
        return "falha de autenticação"

    if response.status_code is not None and 200 <= response.status_code < 300:
        return "Medição criada com sucesso no Sienge."

    if response.message:
        return response.message

    if isinstance(response.body, dict):
        for key in ("message", "mensagem", "error", "erro"):
            value = response.body.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    return "Erro retornado pelo Sienge."


def _dividir_valor_em_itens(valor: Decimal, quantidade_itens: int) -> list[Decimal]:
    total_centavos = int(
        (valor.quantize(CENTAVOS, rounding=ROUND_HALF_UP) * 100).to_integral_value()
    )
    base = total_centavos // quantidade_itens
    resto = total_centavos % quantidade_itens

    valores = []
    for index in range(quantidade_itens):
        centavos = base + (1 if index < resto else 0)
        valores.append((Decimal(centavos) / Decimal(100)).quantize(CENTAVOS))

    return valores


def _decimal_to_json_number(value: Decimal) -> float:
    return float(value.quantize(CENTAVOS, rounding=ROUND_HALF_UP))
