import sqlite3
import os
import random
from datetime import datetime, timedelta
import math

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'dados', 'solar.db')

POTENCIA_NOMINAL   = 20.0
EFICIENCIA_BASE    = 0.85
IRRADIANCIA_STC    = 1000.0
TARIFA_KWH         = 0.75
CUSTO_LIMPEZA      = 5.00
LIMIAR_SUJEIRA     = 10.0

def calcular_irradiancia(hora, minuto):
    hora_decimal = hora + minuto / 60.0
    angulo = math.pi * (hora_decimal - 6) / 12
    irradiancia = max(0, 1000 * math.sin(angulo))
    irradiancia *= random.uniform(0.95, 1.05)
    return round(irradiancia, 2)

def simular_medicao(timestamp, fator_sujeira):
    hora   = timestamp.hour
    minuto = timestamp.minute

    irradiancia      = calcular_irradiancia(hora, minuto)
    temp_ambiente    = round(random.uniform(22, 35), 1)
    temp_placa_limpa = round(temp_ambiente + (irradiancia / 1000) * 25 + random.uniform(-1, 1), 1)
    temp_placa_suja  = round(temp_placa_limpa + fator_sujeira * 5 + random.uniform(-0.5, 0.5), 1)

    potencia_limpa = round((irradiancia / IRRADIANCIA_STC) * POTENCIA_NOMINAL * EFICIENCIA_BASE * random.uniform(0.97, 1.03), 3)
    tensao_limpa   = round(random.uniform(17.5, 18.5) * (irradiancia / 1000 + 0.05), 2)
    corrente_limpa = round(potencia_limpa / tensao_limpa if tensao_limpa > 0 else 0, 3)

    perda_sujeira  = fator_sujeira * 0.40
    potencia_suja  = round(potencia_limpa * (1 - perda_sujeira) * random.uniform(0.97, 1.03), 3)
    tensao_suja    = round(tensao_limpa * (1 - perda_sujeira * 0.5), 2)
    corrente_suja  = round(potencia_suja / tensao_suja if tensao_suja > 0 else 0, 3)

    return {
        'timestamp':        timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        'temp_ambiente':    temp_ambiente,
        'temp_placa_limpa': temp_placa_limpa,
        'temp_placa_suja':  temp_placa_suja,
        'tensao_limpa':     tensao_limpa,
        'corrente_limpa':   corrente_limpa,
        'tensao_suja':      tensao_suja,
        'corrente_suja':    corrente_suja,
        'irradiancia':      irradiancia,
        'potencia_limpa':   potencia_limpa,
        'potencia_suja':    potencia_suja,
    }

def calcular_analise(medicao):
    potencia_limpa   = medicao['potencia_limpa']
    potencia_suja    = medicao['potencia_suja']
    geracao_prevista = potencia_limpa
    geracao_real     = potencia_suja

    if geracao_prevista > 0:
        perda_percentual = round((geracao_prevista - geracao_real) / geracao_prevista * 100, 2)
    else:
        perda_percentual = 0.0

    indicativo_sujeira    = 1 if perda_percentual > LIMIAR_SUJEIRA else 0
    perda_w               = geracao_prevista - geracao_real
    perda_kwh             = perda_w * 0.25 / 1000
    perda_financeira      = round(perda_kwh * TARIFA_KWH, 4)
    perda_diaria_estimada = perda_financeira * 48
    compensa_limpar       = 1 if (indicativo_sujeira and perda_diaria_estimada > CUSTO_LIMPEZA) else 0

    if not indicativo_sujeira:
        mensagem = "Placa dentro do desempenho esperado. Limpeza nao necessaria."
    elif compensa_limpar:
        mensagem = f"Sujeira detectada! Perda de {perda_percentual:.1f}%. Perda diaria estimada: R${perda_diaria_estimada:.2f}. Custo de limpeza: R${CUSTO_LIMPEZA:.2f}. COMPENSA LIMPAR."
    else:
        mensagem = f"Sujeira detectada ({perda_percentual:.1f}% de perda), mas perda diaria (R${perda_diaria_estimada:.2f}) nao supera o custo de limpeza (R${CUSTO_LIMPEZA:.2f}). Aguardar."

    return {
        'timestamp':          medicao['timestamp'],
        'geracao_prevista':   round(geracao_prevista, 3),
        'geracao_real':       round(geracao_real, 3),
        'perda_percentual':   perda_percentual,
        'indicativo_sujeira': indicativo_sujeira,
        'perda_financeira':   perda_financeira,
        'custo_limpeza':      CUSTO_LIMPEZA,
        'compensa_limpar':    compensa_limpar,
        'mensagem_status':    mensagem,
    }

def inserir_dados():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn   = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM medicoes")
    cursor.execute("DELETE FROM analise_limpeza")

    inicio = datetime.now() - timedelta(days=7)
    total  = 0

    print("Gerando dados de teste para 7 dias...")

    for dia in range(7):
        fator_sujeira = (dia / 6) * 0.8
        for hora in range(6, 18):
            for minuto in [0, 15, 30, 45]:
                ts      = inicio + timedelta(days=dia, hours=hora, minutes=minuto)
                medicao = simular_medicao(ts, fator_sujeira)
                analise = calcular_analise(medicao)

                cursor.execute('''
                    INSERT INTO medicoes (
                        timestamp, temp_ambiente, temp_placa_limpa, temp_placa_suja,
                        tensao_limpa, corrente_limpa, tensao_suja, corrente_suja,
                        irradiancia, potencia_limpa, potencia_suja
                    ) VALUES (
                        :timestamp, :temp_ambiente, :temp_placa_limpa, :temp_placa_suja,
                        :tensao_limpa, :corrente_limpa, :tensao_suja, :corrente_suja,
                        :irradiancia, :potencia_limpa, :potencia_suja
                    )
                ''', medicao)

                cursor.execute('''
                    INSERT INTO analise_limpeza (
                        timestamp, geracao_prevista, geracao_real, perda_percentual,
                        indicativo_sujeira, perda_financeira, custo_limpeza,
                        compensa_limpar, mensagem_status
                    ) VALUES (
                        :timestamp, :geracao_prevista, :geracao_real, :perda_percentual,
                        :indicativo_sujeira, :perda_financeira, :custo_limpeza,
                        :compensa_limpar, :mensagem_status
                    )
                ''', analise)

                total += 1

    conn.commit()
    conn.close()
    print(f"{total} registros inseridos com sucesso!")

if __name__ == '__main__':
    inserir_dados()