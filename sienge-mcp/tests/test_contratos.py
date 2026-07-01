from __future__ import annotations

import asyncio
from datetime import date

import pytest

from sienge_mcp.client import SiengeApiResponse
from sienge_mcp.models import ListarContratosRequest
from sienge_mcp.tools.contratos import (
    listar_contratos_sienge,
    montar_endpoint_contratos,
    processar_listagem_contratos,
)


class FakeClient:
    def __init__(self, response: SiengeApiResponse) -> None:
        self.response = response
        self.paths: list[str] = []

    async def get_json(self, path: str) -> SiengeApiResponse:
        self.paths.append(path)
        return self.response

    async def aclose(self) -> None:
        return None


def test_monta_endpoint_com_periodo_calculado_e_filtros() -> None:
    request = ListarContratosRequest.model_validate(
        {
            "data_fim": "2026-06-29",
            "periodo_dias": 30,
            "limite": 5,
            "building_id": 101,
            "status_aprovacao": "a",
            "autorizacao": "t",
        }
    )

    endpoint = montar_endpoint_contratos(request)

    assert endpoint.startswith("/supply-contracts/all?")
    assert "contractStartDate=2026-05-30" in endpoint
    assert "contractEndDate=2026-06-29" in endpoint
    assert "limit=5" in endpoint
    assert "buildingId=101" in endpoint
    assert "statusApproval=A" in endpoint
    assert "authorization=T" in endpoint


def test_rejeita_periodo_invertido() -> None:
    request = ListarContratosRequest.model_validate(
        {
            "data_inicio": "2026-07-01",
            "data_fim": "2026-06-29",
        }
    )

    with pytest.raises(ValueError, match="data_inicio"):
        request.obter_periodo()


def test_filtra_somente_contratos_ativos() -> None:
    request = ListarContratosRequest.model_validate(
        {
            "data_inicio": "2026-01-01",
            "data_fim": "2026-06-29",
            "limite": 10,
            "somente_ativos": True,
        }
    )
    client = FakeClient(
        SiengeApiResponse(
            status_code=200,
            body={
                "resultSetMetadata": {"count": 2},
                "results": [
                    {
                        "documentId": "CT",
                        "contractNumber": "2932",
                        "supplierName": "Fornecedor A",
                        "status": "PARTIALLY_MEASURED",
                        "statusApproval": "APPROVED",
                        "isAuthorized": True,
                        "contractDate": "2026-01-10",
                        "startDate": "2026-01-10",
                        "endDate": "2026-12-31",
                        "companyName": "Empresa",
                        "companyId": 1,
                        "buildings": [{"buildingId": 101, "name": "Obra"}],
                        "totalLaborValue": 100.0,
                        "totalMaterialValue": 0.0,
                        "object": "Contrato ativo",
                    },
                    {
                        "documentId": "CT",
                        "contractNumber": "2739",
                        "status": "COMPLETED",
                    },
                ],
            },
        )
    )

    response = asyncio.run(processar_listagem_contratos(request, client=client))

    assert response.status == "sucesso"
    assert response.total_sienge == 2
    assert response.total_retornado == 1
    assert response.contratos[0].numero_contrato == "2932"
    assert response.contratos[0].obras == [{"building_id": 101, "nome": "Obra"}]


def test_mapeia_erro_403() -> None:
    request = ListarContratosRequest.model_validate(
        {
            "data_inicio": "2026-01-01",
            "data_fim": "2026-06-29",
        }
    )
    client = FakeClient(
        SiengeApiResponse(status_code=403, body={"message": "Permission denied"})
    )

    response = asyncio.run(processar_listagem_contratos(request, client=client))

    assert response.status == "erro"
    assert response.http_status == 403
    assert response.mensagem == "permissões de API foram alteradas; verificar com o gerenciador"


def test_tool_calcula_data_inicio_quando_omitida() -> None:
    request = ListarContratosRequest.model_validate(
        {
            "data_fim": "2026-06-29",
            "limite": 3,
        }
    )

    assert request.obter_periodo() == (date(2025, 6, 29), date(2026, 6, 29))


def test_tool_schema_retorna_dict_com_json(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_processar(request: ListarContratosRequest):
        return await processar_listagem_contratos(
            request,
            client=FakeClient(
                SiengeApiResponse(
                    status_code=200,
                    body={"resultSetMetadata": {"count": 0}, "results": []},
                )
            ),
        )

    monkeypatch.setattr("sienge_mcp.tools.contratos.processar_listagem_contratos", fake_processar)

    response = asyncio.run(listar_contratos_sienge(limite=1, somente_ativos=False))

    assert response["status"] == "sucesso"
    assert response["total_retornado"] == 0
