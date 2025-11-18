from fastapi import APIRouter, HTTPException, Depends
from typing import List

from api.services.carteira_service import CarteiraService
from api.persistence.repositories.carteira_repository import CarteiraRepository
from api.models.carteira_models import (
    Carteira, CarteiraCriada, SaldosCarteira,
    DepositoRequest, SaqueRequest, OperacaoResponse,
    ConversaoRequest, ConversaoResponse,
    TransferenciaRequest, TransferenciaResponse
)


router = APIRouter(prefix="/carteiras", tags=["carteiras"])


def get_carteira_service() -> CarteiraService:
    repo = CarteiraRepository()
    return CarteiraService(repo)


@router.post("", response_model=CarteiraCriada, status_code=201)
def criar_carteira(
    service: CarteiraService = Depends(get_carteira_service),
)->CarteiraCriada:
    """
    Cria uma nova carteira. O body é opcional .
    Retorna endereço e chave privada (apenas nesta resposta).
    """
    try:
        return service.criar_carteira()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[Carteira])
def listar_carteiras(service: CarteiraService = Depends(get_carteira_service)):
    return service.listar()


@router.get("/{endereco_carteira}", response_model=Carteira)
def buscar_carteira(
    endereco_carteira: str,
    service: CarteiraService = Depends(get_carteira_service),
):
    try:
        return service.buscar_por_endereco(endereco_carteira)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{endereco_carteira}", response_model=Carteira)
def bloquear_carteira(
    endereco_carteira: str,
    service: CarteiraService = Depends(get_carteira_service),
):
    try:
        return service.bloquear(endereco_carteira)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{endereco_carteira}/saldos", response_model=SaldosCarteira)
def buscar_saldos(
    endereco_carteira: str,
    service: CarteiraService = Depends(get_carteira_service),
):
    """
    Retorna o saldo da carteira em cada uma das moedas (BTC, ETH, SOL, USD, BRL).
    """
    try:
        return service.buscar_saldos_carteira(endereco_carteira)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{endereco_carteira}/depositos", response_model=OperacaoResponse, status_code=201)
def realizar_deposito(
    endereco_carteira: str,
    request: DepositoRequest,
    service: CarteiraService = Depends(get_carteira_service),
):
    """
    Registra um depósito em uma moeda específica.
    - Não exige autenticação
    - Não aplica taxa
    - Atualiza o saldo da carteira
    """
    try:
        return service.realizar_deposito(endereco_carteira, request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{endereco_carteira}/saques", response_model=OperacaoResponse, status_code=201)
def realizar_saque(
    endereco_carteira: str,
    request: SaqueRequest,
    service: CarteiraService = Depends(get_carteira_service),
):
    """
    Registra um saque em uma moeda específica.
    - Exige chave privada para autenticação
    - Aplica taxa de saque (configurada no .env)
    - Atualiza o saldo da carteira
    - Verifica se há saldo suficiente (valor + taxa)
    """
    try:
        return service.realizar_saque(endereco_carteira, request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{endereco_carteira}/conversoes", response_model=ConversaoResponse, status_code=201)
async def realizar_conversao(
    endereco_carteira: str,
    request: ConversaoRequest,
    service: CarteiraService = Depends(get_carteira_service),
):
    """
    Converte valor de uma moeda de origem para uma moeda de destino.
    - Exige chave privada para autenticação
    - Usa cotação obtida da API da Coinbase
    - Aplica taxa de conversão (configurada no .env)
    - Atualiza saldo das duas moedas na carteira
    - Registra os detalhes da conversão
    """
    try:
        return await service.realizar_conversao(endereco_carteira, request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{endereco_origem}/transferencias", response_model=TransferenciaResponse, status_code=201)
def realizar_transferencia(
    endereco_origem: str,
    request: TransferenciaRequest,
    service: CarteiraService = Depends(get_carteira_service),
):
    """
    Realiza uma transferência entre carteiras.
    - Exige chave privada da carteira de origem para autenticação
    - Aplica taxa sobre a carteira de origem (configurada no .env)
    - Debita da carteira de origem (valor + taxa)
    - Credita na carteira de destino (valor sem taxa)
    - Valida que ambas as carteiras existem e estão ativas
    - Valida que há saldo suficiente na origem
    - Registra os detalhes da transferência
    """
    try:
        return service.realizar_transferencia(endereco_origem, request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))