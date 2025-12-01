CREATE USER wallet_api_homolog WITH PASSWORD 'api123';

GRANT CONNECT ON DATABASE wallet_homolog TO wallet_api_homolog;

GRANT USAGE ON SCHEMA public TO wallet_api_homolog;

ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT
SELECT
,
INSERT
,
UPDATE
,
    DELETE ON TABLES TO wallet_api_homolog;

ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE,
SELECT
    ON SEQUENCES TO wallet_api_homolog;

CREATE
OR REPLACE FUNCTION update_modified_column() RETURNS TRIGGER AS $ $ BEGIN NEW.data_atualizacao = NOW();

RETURN NEW;

END;

$ $ language 'plpgsql';

CREATE TABLE IF NOT EXISTS carteira (
    endereco_carteira VARCHAR(255) NOT NULL,
    hash_chave_privada VARCHAR(255) NOT NULL,
    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'ATIVA',
    PRIMARY KEY (endereco_carteira)
);

CREATE TABLE IF NOT EXISTS moeda (
    id_moeda SERIAL PRIMARY KEY,
    codigo VARCHAR(10) NOT NULL UNIQUE,
    nome VARCHAR(50) NOT NULL,
    tipo VARCHAR(10) NOT NULL
);

CREATE TABLE IF NOT EXISTS saldo_carteira (
    endereco_carteira VARCHAR(255) NOT NULL,
    id_moeda INTEGER NOT NULL,
    saldo DECIMAL(18, 8) NOT NULL DEFAULT 0.00000000,
    data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (endereco_carteira, id_moeda),
    FOREIGN KEY (endereco_carteira) REFERENCES carteira(endereco_carteira),
    FOREIGN KEY (id_moeda) REFERENCES moeda(id_moeda)
);

CREATE TRIGGER update_saldo_modtime BEFORE
UPDATE
    ON saldo_carteira FOR EACH ROW EXECUTE PROCEDURE update_modified_column();

CREATE TABLE IF NOT EXISTS deposito_saque (
    id_movimento BIGSERIAL PRIMARY KEY,
    endereco_carteira VARCHAR(255) NOT NULL,
    id_moeda INTEGER NOT NULL,
    tipo VARCHAR(20) NOT NULL,
    valor DECIMAL(18, 8) NOT NULL,
    taxa_valor DECIMAL(18, 8) DEFAULT 0,
    data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (endereco_carteira) REFERENCES carteira(endereco_carteira),
    FOREIGN KEY (id_moeda) REFERENCES moeda(id_moeda)
);

CREATE TABLE IF NOT EXISTS conversao (
    id_conversao BIGSERIAL PRIMARY KEY,
    endereco_carteira VARCHAR(255) NOT NULL,
    id_moeda_origem INTEGER NOT NULL,
    id_moeda_destino INTEGER NOT NULL,
    valor_origem DECIMAL(18, 8) NOT NULL,
    valor_destino DECIMAL(18, 8) NOT NULL,
    taxa_percentual DECIMAL(5, 4),
    taxa_valor DECIMAL(18, 8),
    cotacao_utilizada DECIMAL(18, 8),
    data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (endereco_carteira) REFERENCES carteira(endereco_carteira),
    FOREIGN KEY (id_moeda_origem) REFERENCES moeda(id_moeda),
    FOREIGN KEY (id_moeda_destino) REFERENCES moeda(id_moeda)
);

CREATE TABLE IF NOT EXISTS transferencia (
    id_transferencia BIGSERIAL PRIMARY KEY,
    endereco_origem VARCHAR(255) NOT NULL,
    endereco_destino VARCHAR(255) NOT NULL,
    id_moeda INTEGER NOT NULL,
    valor DECIMAL(18, 8) NOT NULL,
    taxa_valor DECIMAL(18, 8),
    data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (endereco_origem) REFERENCES carteira(endereco_carteira),
    FOREIGN KEY (endereco_destino) REFERENCES carteira(endereco_carteira),
    FOREIGN KEY (id_moeda) REFERENCES moeda(id_moeda)
);

INSERT INTO
    moeda (codigo, nome, tipo)
VALUES
    ('BTC', 'Bitcoin', 'CRYPTO'),
    ('ETH', 'Ethereum', 'CRYPTO'),
    ('SOL', 'Solana', 'CRYPTO'),
    ('USDT', 'Tether', 'CRYPTO'),
    ('USD', 'Dolar Americano', 'FIAT'),
    ('BRL', 'Real Brasileiro', 'FIAT') ON CONFLICT (codigo) DO NOTHING;