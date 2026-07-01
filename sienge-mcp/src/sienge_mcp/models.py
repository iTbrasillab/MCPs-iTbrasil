from __future__ import annotations

import calendar
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ContratoMedicao(BaseModel):
    model_config = ConfigDict(extra="forbid")

    numero_contrato: str = Field(..., min_length=1)
    valor: Decimal = Field(..., gt=Decimal("0"))
    obra: str | None = Field(default=None, min_length=1)
    building_id: int | None = Field(default=None, ge=1)
    quantidade_itens: int = Field(default=1, ge=1)
    observacao: str | None = Field(default=None)

    @field_validator("numero_contrato")
    @classmethod
    def validar_numero_contrato(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("numero_contrato e obrigatorio.")
        return value

    @field_validator("obra", "observacao")
    @classmethod
    def normalizar_texto_opcional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def validar_obra_ou_building(self) -> "ContratoMedicao":
        if self.obra is None and self.building_id is None:
            raise ValueError("Informe obra ou building_id para localizar o contrato no Sienge.")
        return self


class CriarMedicoesContratosRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contratos: list[ContratoMedicao] = Field(..., min_length=1)
    data_medicao: date = Field(default_factory=date.today)
    data_vencimento: date | None = None
    dia_vencimento: int | None = Field(default=None, ge=1, le=31)
    dry_run: bool = Field(default=True)

    def obter_data_vencimento(self) -> date | None:
        if self.data_vencimento is not None:
            return self.data_vencimento

        if self.dia_vencimento is None:
            return None

        ultimo_dia = calendar.monthrange(self.data_medicao.year, self.data_medicao.month)[1]
        if self.dia_vencimento > ultimo_dia:
            raise ValueError(
                f"dia_vencimento {self.dia_vencimento} nao existe em "
                f"{self.data_medicao.year}-{self.data_medicao.month:02d}."
            )

        return date(self.data_medicao.year, self.data_medicao.month, self.dia_vencimento)


class ResultadoMedicaoContrato(BaseModel):
    contrato: str
    status: Literal["sucesso", "erro", "simulado"]
    http_status: int | None
    mensagem: str
    payload_enviado: dict[str, Any]
    resposta_sienge: Any | None


class CriarMedicoesContratosResponse(BaseModel):
    endpoint_path: str
    dry_run: bool
    total: int
    sucessos: int
    erros: int
    simulados: int
    resultados: list[ResultadoMedicaoContrato]


class ListarContratosRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data_inicio: date | None = None
    data_fim: date = Field(default_factory=date.today)
    periodo_dias: int = Field(default=365, ge=1, le=3650)
    limite: int = Field(default=10, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    building_id: int | None = Field(default=None, ge=1)
    company_id: int | None = Field(default=None, ge=1)
    status_aprovacao: str | None = Field(default=None)
    autorizacao: str | None = Field(default=None)
    consistencia: str | None = Field(default=None)
    somente_ativos: bool = True

    @field_validator("status_aprovacao")
    @classmethod
    def validar_status_aprovacao(cls, value: str | None) -> str | None:
        return _validar_codigo_opcional(value, {"A", "D"}, "status_aprovacao")

    @field_validator("autorizacao")
    @classmethod
    def validar_autorizacao(cls, value: str | None) -> str | None:
        return _validar_codigo_opcional(value, {"T", "S", "A", "N"}, "autorizacao")

    @field_validator("consistencia")
    @classmethod
    def validar_consistencia(cls, value: str | None) -> str | None:
        return _validar_codigo_opcional(value, {"T", "S", "N", "I"}, "consistencia")

    def obter_periodo(self) -> tuple[date, date]:
        data_inicio = self.data_inicio or (self.data_fim - timedelta(days=self.periodo_dias))
        if data_inicio > self.data_fim:
            raise ValueError("data_inicio deve ser menor ou igual a data_fim.")
        return data_inicio, self.data_fim


class ContratoResumo(BaseModel):
    document_id: str | None
    numero_contrato: str | None
    fornecedor: str | None
    status: str | None
    status_aprovacao: str | None
    autorizado: bool | None
    data_contrato: str | None
    data_inicio: str | None
    data_fim: str | None
    empresa: str | None
    company_id: int | None
    obras: list[dict[str, Any]]
    valor_mao_obra: float | None
    valor_material: float | None
    objeto: str | None


class ListarContratosResponse(BaseModel):
    status: Literal["sucesso", "erro"]
    http_status: int | None
    mensagem: str
    endpoint_path: str
    filtros: dict[str, Any]
    total_sienge: int | None
    total_retornado: int
    contratos: list[ContratoResumo]
    resposta_sienge: Any | None = None


def _validar_codigo_opcional(
    value: str | None,
    permitidos: set[str],
    campo: str,
) -> str | None:
    if value is None:
        return None

    value = value.strip().upper()
    if not value:
        return None

    if value not in permitidos:
        raise ValueError(f"{campo} deve ser um de: {', '.join(sorted(permitidos))}.")

    return value
