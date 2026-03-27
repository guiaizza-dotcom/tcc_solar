import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'dados', 'solar.db')

def criar_banco():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS medicoes (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp        TEXT NOT NULL,
            temp_ambiente    REAL,
            temp_placa_limpa REAL,
            temp_placa_suja  REAL,
            tensao_limpa     REAL,
            corrente_limpa   REAL,
            tensao_suja      REAL,
            corrente_suja    REAL,
            irradiancia      REAL,
            potencia_limpa   REAL,
            potencia_suja    REAL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS analise_limpeza (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp         TEXT NOT NULL,
            geracao_prevista  REAL,
            geracao_real      REAL,
            perda_percentual  REAL,
            indicativo_sujeira INTEGER,
            perda_financeira  REAL,
            custo_limpeza     REAL,
            compensa_limpar   INTEGER,
            mensagem_status   TEXT
        )
    ''')

    conn.commit()
    conn.close()
    print("Banco de dados criado com sucesso!")

if __name__ == '__main__':
    criar_banco()