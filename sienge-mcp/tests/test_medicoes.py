from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal

import httpx
import pytest

from sienge_mcp.auth_check import montar_resultado_autenticacao
from sienge_mcp.client import SiengeApiResponse
from sienge_mcp.models import ContratoMedicao, CriarMedicoesContratosRequest
from sienge_mcp.tools.medicoes import montar_payload_medicao, processar_criacao_medicoes


class FakeClient:
    def __init__(self, responses: list[SiengeApiResponse] | None = None) -> None:
        self.responses = responses or []
        self.payloads: list[dict] = []

    async def post_json(self, path: str, payload: dict) -> SiengeApiResponse:
        self.payloads.append({"path": path, "payload": payload})
        return self.responses.pop(0)


class TimeoutClient:
    async def post_json(self, path: str, payload: dict) -> SiengeApiResponse:
        raise httpx.TimeoutException("timeout")


def test_monta_payload_com_data_vencimento_e_split_de_itens() -> None:
    contrato = ContratoMedicao.model_validate(
        {
            "numero_contrato": " CT/EXEMPLO-004 ",
            "valor": Decimal("4568.00"),
            "building_id": 101,
            "quantidade_itens": 2,
        }
    )

    payload = montar_payload_medicao(
        contrato=contrato,
        data_medicao=date(2026, 6, 26),
        data_vencimento=date(2026, 6, 25),
    )

    assert payload["contractNumber"] == "CT/EXEMPLO-004"
    assert payload["measurementDate"] == "2026-06-26"
    assert payload["dueDate"] == "2026-06-25"
    assert payload["buildingId"] == 101
    assert payload["itemsQuantity"] == 2
    assert [item["amount"] for item in payload["items"]] == [2284.0, 2284.0]


def test_calcula_vencimento_por_dia_no_mes_da_medicao() -> None:
    request = CriarMedicoesContratosRequest.model_validate(
        {
            "contratos": [
                {
                    "numero_contrato": "CT/EXEMPLO-001",
                    "valor": 1234.56,
                    "obra": "Obra Exemplo Alpha",
                }
            ],
            "data_medicao": "2026-06-26",
            "dia_vencimento": 25,
        }
    )

    assert request.obter_data_vencimento() == date(2026, 6, 25)


def test_valida_obra_ou_building_id() -> None:
    with pytest.raises(ValueError, match="obra ou building_id"):
        ContratoMedicao.model_validate(
            {
                "numero_contrato": "CT/EXEMPLO-001",
                "valor": 1234.56,
            }
        )


def test_dry_run_nao_chama_cliente() -> None:
    request = CriarMedicoesContratosRequest.model_validate(
        {
            "contratos": [
                {
                    "numero_contrato": "CT/EXEMPLO-001",
                    "valor": 1234.56,
                    "obra": "Obra Exemplo Alpha",
                }
            ],
            "data_medicao": "2026-06-26",
            "dia_vencimento": 25,
            "dry_run": True,
        }
    )
    client = FakeClient()

    response = asyncio.run(processar_criacao_medicoes(request, client=client))

    assert response.simulados == 1
    assert response.resultados[0].status == "simulado"
    assert client.payloads == []


def test_trata_422_medicao_pendente() -> None:
    response = _executar_com_status(422, {"message": "unprocessable"})

    assert response.resultados[0].status == "erro"
    assert response.resultados[0].http_status == 422
    assert response.resultados[0].mensagem == (
        "há medição anterior pendente de autorização no Sienge"
    )


def test_trata_403_permissoes_alteradas() -> None:
    response = _executar_com_status(403, {"message": "forbidden"})

    assert response.resultados[0].mensagem == (
        "permissões de API foram alteradas; verificar com o gerenciador"
    )


def test_trata_401_autenticacao() -> None:
    response = _executar_com_status(401, {"message": "unauthorized"})

    assert response.resultados[0].mensagem == "falha de autenticação"


def test_trata_timeout() -> None:
    request = _request_exemplo()

    response = asyncio.run(
        processar_criacao_medicoes(
            request,
            client=TimeoutClient(),
            endpoint_path="/teste-medicoes",
        )
    )

    assert response.resultados[0].status == "erro"
    assert response.resultados[0].http_status is None
    assert response.resultados[0].mensagem == "tempo limite excedido"


def test_sucesso_envia_payload_para_endpoint_configurado() -> None:
    request = _request_exemplo()
    client = FakeClient([SiengeApiResponse(status_code=201, body={"id": 123})])

    response = asyncio.run(
        processar_criacao_medicoes(
            request,
            client=client,
            endpoint_path="/teste-medicoes",
        )
    )

    assert response.sucessos == 1
    assert response.resultados[0].status == "sucesso"
    assert response.resultados[0].resposta_sienge == {"id": 123}
    assert client.payloads[0]["path"] == "/teste-medicoes"
    assert client.payloads[0]["payload"]["contractNumber"] == "CT/EXEMPLO-001"


def test_auth_check_mapeia_401_sem_expor_segredos() -> None:
    resultado = montar_resultado_autenticacao(
        response=SiengeApiResponse(status_code=401, body={"message": "unauthorized"}),
        base_url="https://api.sienge.com.br/cliente/public/api/v1",
        endpoint_path="/companies",
        metodo="basic",
    )

    assert resultado["status"] == "erro"
    assert resultado["mensagem"] == "falha de autenticação"
    assert resultado["metodo_autenticacao"] == "basic"
    assert "password" not in str(resultado).lower()
    assert "authorization" not in str(resultado).lower()


def test_auth_check_mapeia_sucesso() -> None:
    resultado = montar_resultado_autenticacao(
        response=SiengeApiResponse(status_code=200, body=[{"id": 1}]),
        base_url="https://api.sienge.com.br/cliente/public/api/v1",
        endpoint_path="/companies",
        metodo="basic",
    )

    assert resultado["status"] == "sucesso"
    assert resultado["mensagem"] == "autenticação validada com sucesso"


def _executar_com_status(status_code: int, body: dict) -> object:
    request = _request_exemplo()
    client = FakeClient([SiengeApiResponse(status_code=status_code, body=body)])
    return asyncio.run(
        processar_criacao_medicoes(
            request,
            client=client,
            endpoint_path="/teste-medicoes",
        )
    )


def _request_exemplo() -> CriarMedicoesContratosRequest:
    return CriarMedicoesContratosRequest.model_validate(
        {
            "contratos": [
                {
                    "numero_contrato": "CT/EXEMPLO-001",
                    "valor": 1234.56,
                    "obra": "Obra Exemplo Alpha",
                }
            ],
            "data_medicao": "2026-06-26",
            "dia_vencimento": 25,
            "dry_run": False,
        }
    )
