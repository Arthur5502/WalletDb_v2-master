import os
import secrets
import hashlib
from typing import Dict, Any, Optional, List
from decimal import Decimal

from sqlalchemy import text

from api.persistence.db import get_connection


class CarteiraRepository:
    """
    Acesso a dados da carteira usando SQLAlchemy Core + SQL puro.
    """

    def criar(self) -> Dict[str, Any]:
        """
        Gera chave pública, chave privada, salva no banco (apenas hash da privada)
        e retorna os dados da carteira + chave privada em claro.
        """
        # 1) Geração das chaves
        private_key_size:int = int(os.getenv("PRIVATE_KEY_SIZE"))
        public_key_size:int = int(os.getenv("PUBLIC_KEY_SIZE"))
        chave_privada = secrets.token_hex(private_key_size)      # 32 bytes -> 64 hex chars (configurável depois)
        endereco = secrets.token_hex(public_key_size)           # "chave pública" simplificada
        hash_privada = hashlib.sha256(chave_privada.encode()).hexdigest()

        with get_connection() as conn:
            # 2) INSERT
            conn.execute(
                text("""
                    INSERT INTO carteira (endereco_carteira, hash_chave_privada)
                    VALUES (:endereco, :hash_privada)
                """),
                {"endereco": endereco, "hash_privada": hash_privada},
            )

            # 2.1) Criar saldos zerados para todas as moedas
            conn.execute(
                text("""
                    INSERT INTO saldo_carteira (endereco_carteira, id_moeda, saldo)
                    SELECT :endereco, id_moeda, 0.00000000
                    FROM moeda
                """),
                {"endereco": endereco},
            )

            # 3) SELECT para retornar a carteira criada
            row = conn.execute(
                text("""
                    SELECT endereco_carteira,
                           data_criacao,
                           status,
                           hash_chave_privada
                      FROM carteira
                     WHERE endereco_carteira = :endereco
                """),
                {"endereco": endereco},
            ).mappings().first()

        carteira = dict(row)
        carteira["chave_privada"] = chave_privada
        return carteira

    def buscar_por_endereco(self, endereco_carteira: str) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            row = conn.execute(
                text("""
                    SELECT endereco_carteira,
                           data_criacao,
                           status,
                           hash_chave_privada
                      FROM carteira
                     WHERE endereco_carteira = :endereco
                """),
                {"endereco": endereco_carteira},
            ).mappings().first()

        return dict(row) if row else None

    def listar(self) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            rows = conn.execute(
                text("""
                    SELECT endereco_carteira,
                           data_criacao,
                           status,
                           hash_chave_privada
                      FROM carteira
                """)
            ).mappings().all()

        return [dict(r) for r in rows]

    def atualizar_status(self, endereco_carteira: str, status: str) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            conn.execute(
                text("""
                    UPDATE carteira
                       SET status = :status
                     WHERE endereco_carteira = :endereco
                """),
                {"status": status, "endereco": endereco_carteira},
            )

            row = conn.execute(
                text("""
                    SELECT endereco_carteira,
                           data_criacao,
                           status,
                           hash_chave_privada
                      FROM carteira
                     WHERE endereco_carteira = :endereco
                """),
                {"endereco": endereco_carteira},
            ).mappings().first()

        return dict(row) if row else None

    def buscar_saldos(self, endereco_carteira: str) -> List[Dict[str, Any]]:
        """
        Retorna todos os saldos da carteira com informações da moeda.
        """
        with get_connection() as conn:
            rows = conn.execute(
                text("""
                    SELECT 
                        m.codigo as codigo_moeda,
                        m.nome as nome_moeda,
                        m.tipo as tipo_moeda,
                        s.saldo
                    FROM saldo_carteira s
                    INNER JOIN moeda m ON s.id_moeda = m.id_moeda
                    WHERE s.endereco_carteira = :endereco
                    ORDER BY m.tipo, m.codigo
                """),
                {"endereco": endereco_carteira},
            ).mappings().all()

        return [dict(r) for r in rows]

    def validar_chave_privada(self, endereco_carteira: str, chave_privada: str) -> bool:
        """
        Valida se a chave privada fornecida corresponde ao hash armazenado.
        """
        hash_fornecido = hashlib.sha256(chave_privada.encode()).hexdigest()
        
        with get_connection() as conn:
            row = conn.execute(
                text("""
                    SELECT hash_chave_privada
                    FROM carteira
                    WHERE endereco_carteira = :endereco
                """),
                {"endereco": endereco_carteira},
            ).mappings().first()
        
        if not row:
            return False
        
        return row["hash_chave_privada"] == hash_fornecido

    def buscar_saldo_moeda(self, endereco_carteira: str, codigo_moeda: str) -> Optional[Decimal]:
        """
        Retorna o saldo atual de uma moeda específica na carteira.
        """
        with get_connection() as conn:
            row = conn.execute(
                text("""
                    SELECT s.saldo
                    FROM saldo_carteira s
                    INNER JOIN moeda m ON s.id_moeda = m.id_moeda
                    WHERE s.endereco_carteira = :endereco AND m.codigo = :moeda
                """),
                {"endereco": endereco_carteira, "moeda": codigo_moeda},
            ).mappings().first()
        
        return Decimal(str(row["saldo"])) if row else None

    def atualizar_saldo(self, endereco_carteira: str, codigo_moeda: str, novo_saldo: Decimal) -> None:
        """
        Atualiza o saldo de uma moeda na carteira.
        """
        with get_connection() as conn:
            conn.execute(
                text("""
                    UPDATE saldo_carteira
                    SET saldo = :novo_saldo
                    WHERE endereco_carteira = :endereco 
                    AND id_moeda = (SELECT id_moeda FROM moeda WHERE codigo = :moeda)
                """),
                {"novo_saldo": novo_saldo, "endereco": endereco_carteira, "moeda": codigo_moeda},
            )

    def registrar_deposito(
        self, 
        endereco_carteira: str, 
        codigo_moeda: str, 
        valor: Decimal,
        saldo_anterior: Decimal,
        saldo_atual: Decimal
    ) -> Dict[str, Any]:
        """
        Registra um depósito na tabela DEPOSITO_SAQUE.
        """
        with get_connection() as conn:
            row = conn.execute(
                text("""
                    INSERT INTO deposito_saque 
                    (endereco_carteira, id_moeda, tipo, valor, taxa_valor)
                    VALUES (:endereco, (SELECT id_moeda FROM moeda WHERE codigo = :moeda), 'DEPOSITO', :valor, 0.00000000)
                    RETURNING id_movimento, endereco_carteira, id_moeda, tipo, 
                              valor, taxa_valor, data_hora
                """),
                {
                    "endereco": endereco_carteira,
                    "moeda": codigo_moeda,
                    "valor": valor
                },
            ).mappings().first()
            
            # Buscar código da moeda e mapear para nomes esperados pelo service
            row_dict = dict(row)
            moeda_row = conn.execute(
                text("SELECT codigo as codigo_moeda FROM moeda WHERE id_moeda = :id_moeda"),
                {"id_moeda": row_dict["id_moeda"]}
            ).mappings().first()
            
            # Mapear para os nomes que o service espera
            resultado = {
                "id_operacao": row_dict["id_movimento"],
                "endereco_carteira": row_dict["endereco_carteira"],
                "codigo_moeda": moeda_row["codigo_moeda"],
                "tipo_operacao": row_dict["tipo"],
                "valor": row_dict["valor"],
                "taxa": row_dict["taxa_valor"],
                "valor_liquido": row_dict["valor"],  # Para depósito, valor_liquido = valor
                "saldo_anterior": saldo_anterior,
                "saldo_atual": saldo_atual,
                "data_operacao": row_dict["data_hora"]
            }
        
        return resultado

    def registrar_saque(
        self, 
        endereco_carteira: str, 
        codigo_moeda: str, 
        valor: Decimal,
        taxa: Decimal,
        valor_liquido: Decimal,
        saldo_anterior: Decimal,
        saldo_atual: Decimal
    ) -> Dict[str, Any]:
        """
        Registra um saque na tabela DEPOSITO_SAQUE.
        """
        with get_connection() as conn:
            row = conn.execute(
                text("""
                    INSERT INTO deposito_saque 
                    (endereco_carteira, id_moeda, tipo, valor, taxa_valor)
                    VALUES (:endereco, (SELECT id_moeda FROM moeda WHERE codigo = :moeda), 'SAQUE', :valor, :taxa)
                    RETURNING id_movimento, endereco_carteira, id_moeda, tipo, 
                              valor, taxa_valor, data_hora
                """),
                {
                    "endereco": endereco_carteira,
                    "moeda": codigo_moeda,
                    "valor": valor,
                    "taxa": taxa
                },
            ).mappings().first()
            
            # Buscar código da moeda e mapear para nomes esperados pelo service
            row_dict = dict(row)
            moeda_row = conn.execute(
                text("SELECT codigo as codigo_moeda FROM moeda WHERE id_moeda = :id_moeda"),
                {"id_moeda": row_dict["id_moeda"]}
            ).mappings().first()
            
            # Mapear para os nomes que o service espera
            resultado = {
                "id_operacao": row_dict["id_movimento"],
                "endereco_carteira": row_dict["endereco_carteira"],
                "codigo_moeda": moeda_row["codigo_moeda"],
                "tipo_operacao": row_dict["tipo"],
                "valor": row_dict["valor"],
                "taxa": row_dict["taxa_valor"],
                "valor_liquido": valor_liquido,
                "saldo_anterior": saldo_anterior,
                "saldo_atual": saldo_atual,
                "data_operacao": row_dict["data_hora"]
            }
        
        return resultado

    def registrar_conversao(
        self,
        endereco_carteira: str,
        moeda_origem: str,
        moeda_destino: str,
        valor_origem: Decimal,
        cotacao: Decimal,
        taxa_conversao: Decimal,
        valor_destino: Decimal,
        saldo_origem_anterior: Decimal,
        saldo_origem_atual: Decimal,
        saldo_destino_anterior: Decimal,
        saldo_destino_atual: Decimal
    ) -> Dict[str, Any]:
        """
        Registra uma conversão na tabela CONVERSAO.
        """
        # Calcular taxa_percentual e taxa_valor
        taxa_percentual = taxa_conversao / valor_origem if valor_origem > 0 else Decimal("0")
        
        with get_connection() as conn:
            row = conn.execute(
                text("""
                    INSERT INTO conversao 
                    (endereco_carteira, id_moeda_origem, id_moeda_destino, valor_origem, valor_destino,
                     taxa_percentual, taxa_valor, cotacao_utilizada)
                    VALUES (:endereco, 
                            (SELECT id_moeda FROM moeda WHERE codigo = :moeda_origem), 
                            (SELECT id_moeda FROM moeda WHERE codigo = :moeda_destino), 
                            :valor_origem, :valor_destino,
                            :taxa_percentual, :taxa_valor, :cotacao)
                    RETURNING id_conversao, endereco_carteira, id_moeda_origem, id_moeda_destino,
                              valor_origem, valor_destino, taxa_percentual, taxa_valor, 
                              cotacao_utilizada, data_hora
                """),
                {
                    "endereco": endereco_carteira,
                    "moeda_origem": moeda_origem,
                    "moeda_destino": moeda_destino,
                    "valor_origem": valor_origem,
                    "valor_destino": valor_destino,
                    "taxa_percentual": taxa_percentual,
                    "taxa_valor": taxa_conversao,
                    "cotacao": cotacao
                },
            ).mappings().first()
            
            # Buscar códigos das moedas e mapear para nomes esperados pelo service
            row_dict = dict(row)
            moeda_origem_row = conn.execute(
                text("SELECT codigo FROM moeda WHERE id_moeda = :id_moeda"),
                {"id_moeda": row_dict["id_moeda_origem"]}
            ).mappings().first()
            moeda_destino_row = conn.execute(
                text("SELECT codigo FROM moeda WHERE id_moeda = :id_moeda"),
                {"id_moeda": row_dict["id_moeda_destino"]}
            ).mappings().first()
            
            # Mapear para os nomes que o service espera
            resultado = {
                "id_conversao": row_dict["id_conversao"],
                "endereco_carteira": row_dict["endereco_carteira"],
                "moeda_origem": moeda_origem_row["codigo"],
                "moeda_destino": moeda_destino_row["codigo"],
                "valor_origem": row_dict["valor_origem"],
                "cotacao": row_dict["cotacao_utilizada"],
                "taxa_conversao": row_dict["taxa_valor"],
                "valor_destino": row_dict["valor_destino"],
                "saldo_origem_anterior": saldo_origem_anterior,
                "saldo_origem_atual": saldo_origem_atual,
                "saldo_destino_anterior": saldo_destino_anterior,
                "saldo_destino_atual": saldo_destino_atual,
                "data_conversao": row_dict["data_hora"]
            }
        
        return resultado

    def registrar_transferencia(
        self,
        endereco_origem: str,
        endereco_destino: str,
        codigo_moeda: str,
        valor: Decimal,
        taxa: Decimal,
        valor_liquido: Decimal,
        saldo_origem_anterior: Decimal,
        saldo_origem_atual: Decimal,
        saldo_destino_anterior: Decimal,
        saldo_destino_atual: Decimal
    ) -> Dict[str, Any]:
        """
        Registra uma transferência na tabela TRANSFERENCIA.
        """
        with get_connection() as conn:
            row = conn.execute(
                text("""
                    INSERT INTO transferencia 
                    (endereco_origem, endereco_destino, id_moeda, valor, taxa_valor)
                    VALUES (:endereco_origem, :endereco_destino, 
                            (SELECT id_moeda FROM moeda WHERE codigo = :codigo_moeda), 
                            :valor, :taxa)
                    RETURNING id_transferencia, endereco_origem, endereco_destino, id_moeda,
                              valor, taxa_valor, data_hora
                """),
                {
                    "endereco_origem": endereco_origem,
                    "endereco_destino": endereco_destino,
                    "codigo_moeda": codigo_moeda,
                    "valor": valor,
                    "taxa": taxa
                },
            ).mappings().first()
            
            # Buscar código da moeda e mapear para nomes esperados pelo service
            row_dict = dict(row)
            moeda_row = conn.execute(
                text("SELECT codigo as codigo_moeda FROM moeda WHERE id_moeda = :id_moeda"),
                {"id_moeda": row_dict["id_moeda"]}
            ).mappings().first()
            
            # Mapear para os nomes que o service espera
            resultado = {
                "id_transferencia": row_dict["id_transferencia"],
                "endereco_origem": row_dict["endereco_origem"],
                "endereco_destino": row_dict["endereco_destino"],
                "codigo_moeda": moeda_row["codigo_moeda"],
                "valor": row_dict["valor"],
                "taxa": row_dict["taxa_valor"],
                "valor_liquido": valor_liquido,
                "saldo_origem_anterior": saldo_origem_anterior,
                "saldo_origem_atual": saldo_origem_atual,
                "saldo_destino_anterior": saldo_destino_anterior,
                "saldo_destino_atual": saldo_destino_atual,
                "data_transferencia": row_dict["data_hora"]
            }
        
        return resultado