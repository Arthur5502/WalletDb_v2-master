from typing import Literal, List
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, field_serializer


class Carteira(BaseModel):
    endereco_carteira: str
    data_criacao: datetime
    status: Literal["ATIVA","BLOQUEADA"]


class CarteiraCriada(Carteira):
    chave_privada: str


class Moeda(BaseModel):
    codigo_moeda: str
    nome_moeda: str
    tipo_moeda: Literal["CRYPTO", "FIAT"]


class SaldoMoeda(BaseModel):
    codigo_moeda: str
    nome_moeda: str
    tipo_moeda: Literal["CRYPTO", "FIAT"]
    saldo: Decimal = Field(default=Decimal("0.00000000"))

    @field_serializer('saldo')
    def serialize_saldo(self, value: Decimal) -> str:
        """Formata o saldo para ter sempre 8 casas decimais"""
        return f"{value:.8f}"


class SaldosCarteira(BaseModel):
    endereco_carteira: str
    saldos: List[SaldoMoeda]


# ========== Modelos de Depósito e Saque ==========
class DepositoRequest(BaseModel):
    codigo_moeda: str = Field(..., description="Código da moeda (BTC, ETH, SOL, USD, BRL)")
    valor: Decimal = Field(..., gt=0, description="Valor a depositar (deve ser maior que 0)")


class SaqueRequest(BaseModel):
    codigo_moeda: str = Field(..., description="Código da moeda (BTC, ETH, SOL, USD, BRL)")
    valor: Decimal = Field(..., gt=0, description="Valor a sacar (deve ser maior que 0)")
    chave_privada: str = Field(..., description="Chave privada para autorizar o saque")


class OperacaoResponse(BaseModel):
    id_operacao: int
    endereco_carteira: str
    codigo_moeda: str
    tipo_operacao: Literal["DEPOSITO", "SAQUE"]
    valor: Decimal
    taxa: Decimal
    valor_liquido: Decimal
    saldo_anterior: Decimal
    saldo_atual: Decimal
    data_operacao: datetime

    @field_serializer('valor', 'taxa', 'valor_liquido', 'saldo_anterior', 'saldo_atual')
    def serialize_decimal(self, value: Decimal) -> str:
        """Formata valores decimais para ter sempre 8 casas decimais"""
        return f"{value:.8f}"


# ========== Modelos de Conversão ==========
class ConversaoRequest(BaseModel):
    moeda_origem: str = Field(..., description="Código da moeda de origem (BTC, ETH, SOL, USD, BRL)")
    moeda_destino: str = Field(..., description="Código da moeda de destino (BTC, ETH, SOL, USD, BRL)")
    valor: Decimal = Field(..., gt=0, description="Valor a converter (deve ser maior que 0)")
    chave_privada: str = Field(..., description="Chave privada para autorizar a conversão")


class ConversaoResponse(BaseModel):
    id_conversao: int
    endereco_carteira: str
    moeda_origem: str
    moeda_destino: str
    valor_origem: Decimal
    cotacao: Decimal
    taxa_conversao: Decimal
    valor_destino: Decimal
    saldo_origem_anterior: Decimal
    saldo_origem_atual: Decimal
    saldo_destino_anterior: Decimal
    saldo_destino_atual: Decimal
    data_conversao: datetime

    @field_serializer('valor_origem', 'cotacao', 'taxa_conversao', 'valor_destino', 
                      'saldo_origem_anterior', 'saldo_origem_atual', 
                      'saldo_destino_anterior', 'saldo_destino_atual')
    def serialize_decimal(self, value: Decimal) -> str:
        """Formata valores decimais para ter sempre 8 casas decimais"""
        return f"{value:.8f}"


# ========== Modelos de Transferência ==========
class TransferenciaRequest(BaseModel):
    endereco_destino: str = Field(..., description="Endereço da carteira de destino")
    codigo_moeda: str = Field(..., description="Código da moeda (BTC, ETH, SOL, USD, BRL)")
    valor: Decimal = Field(..., gt=0, description="Valor a transferir (deve ser maior que 0)")
    chave_privada: str = Field(..., description="Chave privada para autorizar a transferência")


class TransferenciaResponse(BaseModel):
    id_transferencia: int
    endereco_origem: str
    endereco_destino: str
    codigo_moeda: str
    valor: Decimal
    taxa: Decimal
    valor_liquido: Decimal
    saldo_origem_anterior: Decimal
    saldo_origem_atual: Decimal
    saldo_destino_anterior: Decimal
    saldo_destino_atual: Decimal
    data_transferencia: datetime

    @field_serializer('valor', 'taxa', 'valor_liquido', 
                      'saldo_origem_anterior', 'saldo_origem_atual', 
                      'saldo_destino_anterior', 'saldo_destino_atual')
    def serialize_decimal(self, value: Decimal) -> str:
        """Formata valores decimais para ter sempre 8 casas decimais"""
        return f"{value:.8f}"