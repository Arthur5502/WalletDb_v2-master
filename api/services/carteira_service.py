from typing import List, Tuple
from decimal import Decimal, InvalidOperation
import os
import logging

from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from api.persistence.repositories.carteira_repository import CarteiraRepository
from api.services.coinbase_service import CoinbaseService
from api.models.carteira_models import (
    Carteira, CarteiraCriada, SaldosCarteira, SaldoMoeda, 
    DepositoRequest, SaqueRequest, OperacaoResponse,
    ConversaoRequest, ConversaoResponse,
    TransferenciaRequest, TransferenciaResponse
)

logger = logging.getLogger(__name__)


class CarteiraService:
    """
    Serviço responsável pela lógica de negócio de carteiras digitais.
    Gerencia operações de depósito, saque, conversão e transferência.
    """
    def __init__(self, carteira_repo: CarteiraRepository):
        self.carteira_repo = carteira_repo

    # ==================== Métodos Privados - Validações ====================

    def _validar_endereco(self, endereco: str, nome_campo: str = "Endereço da carteira") -> None:
        """Valida se o endereço não é vazio."""
        if not endereco or not endereco.strip():
            raise ValueError(f"{nome_campo} é obrigatório")

    def _validar_chave_privada(self, chave_privada: str) -> None:
        """Valida se a chave privada não é vazia."""
        if not chave_privada or not chave_privada.strip():
            raise ValueError("Chave privada é obrigatória")

    def _obter_carteira_ativa(self, endereco: str) -> dict:
        """
        Busca uma carteira e valida se está ativa.
        Raises ValueError se não encontrada ou bloqueada.
        """
        carteira = self.carteira_repo.buscar_por_endereco(endereco)
        if not carteira:
            raise ValueError("Carteira não encontrada")
        if carteira["status"] != "ATIVA":
            raise ValueError("Carteira bloqueada")
        return carteira

    def _autenticar_carteira(self, endereco: str, chave_privada: str) -> None:
        """
        Valida chave privada da carteira.
        Raises ValueError se inválida.
        """
        if not self.carteira_repo.validar_chave_privada(endereco, chave_privada):
            raise ValueError("Chave privada inválida")

    def _obter_saldo_ou_erro(self, endereco: str, codigo_moeda: str) -> Decimal:
        """
        Busca saldo de uma moeda ou lança erro se não encontrada.
        Raises ValueError se moeda não existe.
        """
        saldo = self.carteira_repo.buscar_saldo_moeda(endereco, codigo_moeda)
        if saldo is None:
            raise ValueError(f"Moeda {codigo_moeda} não encontrada")
        return saldo

    def _obter_taxa_percentual(self, chave_env: str, valor_padrao: str) -> Decimal:
        """Obtém taxa percentual do .env com fallback para valor padrão."""
        try:
            return Decimal(os.getenv(chave_env, valor_padrao))
        except (InvalidOperation, ValueError) as e:
            logger.warning(f"Taxa inválida em {chave_env}, usando padrão {valor_padrao}: {e}")
            return Decimal(valor_padrao)

    def _converter_para_decimal(self, valor: any) -> Decimal:
        """Converte valor para Decimal de forma segura."""
        return Decimal(str(valor))

    # ==================== Métodos Públicos ====================

    def criar_carteira(self) -> CarteiraCriada:
        """Cria uma nova carteira com chaves criptográficas e saldos zerados."""
        try:
            row = self.carteira_repo.criar()
            return CarteiraCriada(
                endereco_carteira=row["endereco_carteira"],
                data_criacao=row["data_criacao"],
                status=row["status"],
                chave_privada=row["chave_privada"],
            )
        except IntegrityError as e:
            logger.error(f"Erro de integridade ao criar carteira: {e}")
            raise RuntimeError("Erro ao gerar chaves únicas. Tente novamente.")
        except (SQLAlchemyError, KeyError) as e:
            logger.error(f"Erro ao criar carteira: {e}")
            raise RuntimeError("Erro ao criar carteira no banco de dados")

    def buscar_por_endereco(self, endereco_carteira: str) -> Carteira:
        """Busca uma carteira pelo endereço."""
        try:
            self._validar_endereco(endereco_carteira)
            row = self.carteira_repo.buscar_por_endereco(endereco_carteira)
            if not row:
                raise ValueError("Carteira não encontrada")

            return Carteira(
                endereco_carteira=row["endereco_carteira"],
                data_criacao=row["data_criacao"],
                status=row["status"],
            )
        except ValueError:
            raise
        except (SQLAlchemyError, KeyError) as e:
            logger.error(f"Erro ao buscar carteira {endereco_carteira}: {e}")
            raise RuntimeError("Erro ao buscar carteira no banco de dados")

    def listar(self) -> List[Carteira]:
        """Lista todas as carteiras."""
        try:
            rows = self.carteira_repo.listar()
            return [
                Carteira(
                    endereco_carteira=r["endereco_carteira"],
                    data_criacao=r["data_criacao"],
                    status=r["status"],
                )
                for r in rows
            ]
        except (SQLAlchemyError, KeyError) as e:
            logger.error(f"Erro ao listar carteiras: {e}")
            raise RuntimeError("Erro ao listar carteiras no banco de dados")

    def bloquear(self, endereco_carteira: str) -> Carteira:
        """Bloqueia uma carteira."""
        try:
            self._validar_endereco(endereco_carteira)
            row = self.carteira_repo.atualizar_status(endereco_carteira, "BLOQUEADA")
            if not row:
                raise ValueError("Carteira não encontrada")

            return Carteira(
                endereco_carteira=row["endereco_carteira"],
                data_criacao=row["data_criacao"],
                status=row["status"],
            )
        except ValueError:
            raise
        except (SQLAlchemyError, KeyError) as e:
            logger.error(f"Erro ao bloquear carteira {endereco_carteira}: {e}")
            raise RuntimeError("Erro ao bloquear carteira no banco de dados")

    def buscar_saldos_carteira(self, endereco_carteira: str) -> SaldosCarteira:
        """Busca saldos de todas as moedas de uma carteira."""
        try:
            self._validar_endereco(endereco_carteira)
            self._obter_carteira_ativa(endereco_carteira)  # Valida existência

            rows = self.carteira_repo.buscar_saldos(endereco_carteira)
            saldos = [
                SaldoMoeda(
                    codigo_moeda=r["codigo_moeda"],
                    nome_moeda=r["nome_moeda"],
                    tipo_moeda=r["tipo_moeda"],
                    saldo=self._converter_para_decimal(r["saldo"])
                )
                for r in rows
            ]

            return SaldosCarteira(endereco_carteira=endereco_carteira, saldos=saldos)
        except ValueError:
            raise
        except (InvalidOperation, SQLAlchemyError, KeyError) as e:
            logger.error(f"Erro ao buscar saldos da carteira {endereco_carteira}: {e}")
            raise RuntimeError("Erro ao buscar saldos no banco de dados")

    def realizar_deposito(self, endereco_carteira: str, request: DepositoRequest) -> OperacaoResponse:
        """Realiza um depósito na carteira (sem taxa, sem autenticação)."""
        try:
            self._validar_endereco(endereco_carteira)
            self._obter_carteira_ativa(endereco_carteira)

            saldo_anterior = self._obter_saldo_ou_erro(endereco_carteira, request.codigo_moeda)
            saldo_atual = saldo_anterior + request.valor

            self.carteira_repo.atualizar_saldo(endereco_carteira, request.codigo_moeda, saldo_atual)

            operacao = self.carteira_repo.registrar_deposito(
                endereco_carteira=endereco_carteira,
                codigo_moeda=request.codigo_moeda,
                valor=request.valor,
                saldo_anterior=saldo_anterior,
                saldo_atual=saldo_atual
            )

            return self._criar_operacao_response(operacao)
        except ValueError:
            raise
        except (InvalidOperation, SQLAlchemyError, KeyError) as e:
            logger.error(f"Erro ao realizar depósito: {e}")
            raise RuntimeError("Erro ao processar depósito no banco de dados")

    def _criar_operacao_response(self, operacao: dict) -> OperacaoResponse:
        """Cria response de operação convertendo valores para Decimal."""
        return OperacaoResponse(
            id_operacao=operacao["id_operacao"],
            endereco_carteira=operacao["endereco_carteira"],
            codigo_moeda=operacao["codigo_moeda"],
            tipo_operacao=operacao["tipo_operacao"],
            valor=self._converter_para_decimal(operacao["valor"]),
            taxa=self._converter_para_decimal(operacao["taxa"]),
            valor_liquido=self._converter_para_decimal(operacao["valor_liquido"]),
            saldo_anterior=self._converter_para_decimal(operacao["saldo_anterior"]),
            saldo_atual=self._converter_para_decimal(operacao["saldo_atual"]),
            data_operacao=operacao["data_operacao"]
        )

    def realizar_saque(self, endereco_carteira: str, request: SaqueRequest) -> OperacaoResponse:
        """Realiza um saque na carteira (com taxa, requer autenticação)."""
        try:
            self._validar_endereco(endereco_carteira)
            self._validar_chave_privada(request.chave_privada)
            self._obter_carteira_ativa(endereco_carteira)
            self._autenticar_carteira(endereco_carteira, request.chave_privada)

            saldo_anterior = self._obter_saldo_ou_erro(endereco_carteira, request.codigo_moeda)

            taxa_percentual = self._obter_taxa_percentual("TAXA_SAQUE_PERCENTUAL", "0.01")
            taxa = request.valor * taxa_percentual
            valor_total = request.valor + taxa

            if saldo_anterior < valor_total:
                raise ValueError(
                    f"Saldo insuficiente. Necessário: {valor_total:.8f} "
                    f"(valor: {request.valor:.8f} + taxa: {taxa:.8f})"
                )

            saldo_atual = saldo_anterior - valor_total

            self.carteira_repo.atualizar_saldo(endereco_carteira, request.codigo_moeda, saldo_atual)

            operacao = self.carteira_repo.registrar_saque(
                endereco_carteira=endereco_carteira,
                codigo_moeda=request.codigo_moeda,
                valor=request.valor,
                taxa=taxa,
                valor_liquido=request.valor,
                saldo_anterior=saldo_anterior,
                saldo_atual=saldo_atual
            )

            return self._criar_operacao_response(operacao)
        except ValueError:
            raise
        except (InvalidOperation, SQLAlchemyError, KeyError) as e:
            logger.error(f"Erro ao realizar saque: {e}")
            raise RuntimeError("Erro ao processar saque no banco de dados")

    def _obter_saldos_duas_moedas(
        self, endereco: str, moeda1: str, moeda2: str
    ) -> Tuple[Decimal, Decimal]:
        """Obtém saldos de duas moedas e valida se existem."""
        saldo1 = self._obter_saldo_ou_erro(endereco, moeda1)
        saldo2 = self._obter_saldo_ou_erro(endereco, moeda2)
        return saldo1, saldo2

    async def realizar_conversao(self, endereco_carteira: str, request: ConversaoRequest) -> ConversaoResponse:
        """Realiza conversão entre moedas (com taxa, requer autenticação, consulta Coinbase)."""
        try:
            self._validar_endereco(endereco_carteira)
            self._validar_chave_privada(request.chave_privada)
            self._obter_carteira_ativa(endereco_carteira)
            self._autenticar_carteira(endereco_carteira, request.chave_privada)

            if request.moeda_origem == request.moeda_destino:
                raise ValueError("Moeda de origem e destino devem ser diferentes")

            saldo_origem_anterior, saldo_destino_anterior = self._obter_saldos_duas_moedas(
                endereco_carteira, request.moeda_origem, request.moeda_destino
            )

            if saldo_origem_anterior < request.valor:
                raise ValueError(
                    f"Saldo insuficiente em {request.moeda_origem}. "
                    f"Disponível: {saldo_origem_anterior:.8f}"
                )

            # Obtém cotação da API Coinbase
            try:
                cotacao = await CoinbaseService.obter_cotacao(request.moeda_origem, request.moeda_destino)
            except Exception as e:
                logger.error(f"Erro ao obter cotação da Coinbase: {e}")
                raise RuntimeError("Erro ao consultar cotação das moedas. Tente novamente mais tarde.")

            # Calcula taxa e valores
            taxa_percentual = self._obter_taxa_percentual("TAXA_CONVERSAO_PERCENTUAL", "0.02")
            valor_convertido_bruto = request.valor * cotacao
            taxa_conversao = valor_convertido_bruto * taxa_percentual
            valor_destino = valor_convertido_bruto - taxa_conversao

            # Atualiza saldos
            saldo_origem_atual = saldo_origem_anterior - request.valor
            saldo_destino_atual = saldo_destino_anterior + valor_destino

            self.carteira_repo.atualizar_saldo(endereco_carteira, request.moeda_origem, saldo_origem_atual)
            self.carteira_repo.atualizar_saldo(endereco_carteira, request.moeda_destino, saldo_destino_atual)

            # Registra conversão
            conversao = self.carteira_repo.registrar_conversao(
                endereco_carteira=endereco_carteira,
                moeda_origem=request.moeda_origem,
                moeda_destino=request.moeda_destino,
                valor_origem=request.valor,
                cotacao=cotacao,
                taxa_conversao=taxa_conversao,
                valor_destino=valor_destino,
                saldo_origem_anterior=saldo_origem_anterior,
                saldo_origem_atual=saldo_origem_atual,
                saldo_destino_anterior=saldo_destino_anterior,
                saldo_destino_atual=saldo_destino_atual
            )

            return self._criar_conversao_response(conversao)
        except ValueError:
            raise
        except (InvalidOperation, SQLAlchemyError, KeyError) as e:
            logger.error(f"Erro ao realizar conversão: {e}")
            raise RuntimeError("Erro ao processar conversão no banco de dados")

    def _criar_conversao_response(self, conversao: dict) -> ConversaoResponse:
        """Cria response de conversão convertendo valores para Decimal."""
        return ConversaoResponse(
            id_conversao=conversao["id_conversao"],
            endereco_carteira=conversao["endereco_carteira"],
            moeda_origem=conversao["moeda_origem"],
            moeda_destino=conversao["moeda_destino"],
            valor_origem=self._converter_para_decimal(conversao["valor_origem"]),
            cotacao=self._converter_para_decimal(conversao["cotacao"]),
            taxa_conversao=self._converter_para_decimal(conversao["taxa_conversao"]),
            valor_destino=self._converter_para_decimal(conversao["valor_destino"]),
            saldo_origem_anterior=self._converter_para_decimal(conversao["saldo_origem_anterior"]),
            saldo_origem_atual=self._converter_para_decimal(conversao["saldo_origem_atual"]),
            saldo_destino_anterior=self._converter_para_decimal(conversao["saldo_destino_anterior"]),
            saldo_destino_atual=self._converter_para_decimal(conversao["saldo_destino_atual"]),
            data_conversao=conversao["data_conversao"]
        )

    def realizar_transferencia(self, endereco_origem: str, request: TransferenciaRequest) -> TransferenciaResponse:
        """Realiza transferência entre carteiras (com taxa, requer autenticação)."""
        try:
            # Validações iniciais
            self._validar_endereco(endereco_origem, "Endereço da carteira de origem")
            self._validar_endereco(request.endereco_destino, "Endereço da carteira de destino")
            self._validar_chave_privada(request.chave_privada)

            if endereco_origem == request.endereco_destino:
                raise ValueError("Não é possível transferir para a mesma carteira")

            # Valida ambas as carteiras
            self._obter_carteira_ativa(endereco_origem)
            carteira_destino = self.carteira_repo.buscar_por_endereco(request.endereco_destino)
            if not carteira_destino:
                raise ValueError("Carteira de destino não encontrada")
            if carteira_destino["status"] != "ATIVA":
                raise ValueError("Carteira de destino bloqueada")

            self._autenticar_carteira(endereco_origem, request.chave_privada)

            # Busca saldos
            saldo_origem_anterior = self._obter_saldo_ou_erro(endereco_origem, request.codigo_moeda)
            saldo_destino_anterior = self.carteira_repo.buscar_saldo_moeda(
                request.endereco_destino, request.codigo_moeda
            )
            if saldo_destino_anterior is None:
                raise ValueError(
                    f"Moeda {request.codigo_moeda} não encontrada na carteira de destino"
                )

            # Calcula taxa e valores
            taxa_percentual = self._obter_taxa_percentual("TAXA_TRANSFERENCIA_PERCENTUAL", "0.005")
            taxa = request.valor * taxa_percentual
            valor_total_origem = request.valor + taxa

            if saldo_origem_anterior < valor_total_origem:
                raise ValueError(
                    f"Saldo insuficiente. Necessário: {valor_total_origem:.8f} "
                    f"(valor: {request.valor:.8f} + taxa: {taxa:.8f})"
                )

            # Calcula novos saldos
            saldo_origem_atual = saldo_origem_anterior - valor_total_origem
            saldo_destino_atual = saldo_destino_anterior + request.valor  # Destino recebe sem taxa

            # Atualiza saldos
            self.carteira_repo.atualizar_saldo(endereco_origem, request.codigo_moeda, saldo_origem_atual)
            self.carteira_repo.atualizar_saldo(
                request.endereco_destino, request.codigo_moeda, saldo_destino_atual
            )

            # Registra transferência
            transferencia = self.carteira_repo.registrar_transferencia(
                endereco_origem=endereco_origem,
                endereco_destino=request.endereco_destino,
                codigo_moeda=request.codigo_moeda,
                valor=request.valor,
                taxa=taxa,
                valor_liquido=request.valor,
                saldo_origem_anterior=saldo_origem_anterior,
                saldo_origem_atual=saldo_origem_atual,
                saldo_destino_anterior=saldo_destino_anterior,
                saldo_destino_atual=saldo_destino_atual
            )

            return self._criar_transferencia_response(transferencia)
        except ValueError:
            raise
        except (InvalidOperation, SQLAlchemyError, KeyError) as e:
            logger.error(f"Erro ao realizar transferência: {e}")
            raise RuntimeError("Erro ao processar transferência no banco de dados")

    def _criar_transferencia_response(self, transferencia: dict) -> TransferenciaResponse:
        """Cria response de transferência convertendo valores para Decimal."""
        return TransferenciaResponse(
            id_transferencia=transferencia["id_transferencia"],
            endereco_origem=transferencia["endereco_origem"],
            endereco_destino=transferencia["endereco_destino"],
            codigo_moeda=transferencia["codigo_moeda"],
            valor=self._converter_para_decimal(transferencia["valor"]),
            taxa=self._converter_para_decimal(transferencia["taxa"]),
            valor_liquido=self._converter_para_decimal(transferencia["valor_liquido"]),
            saldo_origem_anterior=self._converter_para_decimal(transferencia["saldo_origem_anterior"]),
            saldo_origem_atual=self._converter_para_decimal(transferencia["saldo_origem_atual"]),
            saldo_destino_anterior=self._converter_para_decimal(transferencia["saldo_destino_anterior"]),
            saldo_destino_atual=self._converter_para_decimal(transferencia["saldo_destino_atual"]),
            data_transferencia=transferencia["data_transferencia"]
        )