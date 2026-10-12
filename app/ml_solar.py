"""
🤖 TCC Solar — Machine Learning (potência esperada da placa limpa)
==================================================================
Módulo único usado tanto pelo app (dashboard.py) quanto pelos scripts de
treino/avaliação (pasta ml/). Assim as variáveis de entrada são calculadas
EXATAMENTE do mesmo jeito no treino e no uso.

Ideia: o modelo aprende quanto uma placa LIMPA gera nas condições do momento
(irradiância do sensor, posição do sol em relação à placa, temperaturas).
Para julgar qualquer placa:
    índice = energia real / energia esperada pelo modelo
    perda  = 1 − índice

Não depende do Streamlit (o cache fica no dashboard.py).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

PASTA_MODELOS = Path(__file__).resolve().parent.parent / "modelos"

# Arquivos de cada modelo (salvos pelo ml/treinar_modelo.py)
ARQUIVOS_MODELOS = {
    "Regressão Linear": "regressao_linear.joblib",
    "Random Forest": "random_forest.joblib",
    "XGBoost": "xgboost.joblib",
}
MODELO_PADRAO = "XGBoost"
FISICO = "Fórmula física"          # Pmax × G/1000 — referência sem treino
ORDEM_MODELOS = [FISICO, "Regressão Linear", "Random Forest", "XGBoost"]

# Geometria / janela usadas no TREINO (o modelo vale para esta instalação).
# Ficam gravadas em modelos/modelo_info.json junto com o modelo.
INFO_PADRAO = {
    "latitude": -23.0903, "longitude": -47.2181, "fuso_h": -3.0,
    "inclinacao": 23.0, "azimute": 132.0, "pmax": 20.0,
    "janela_inicio_h": 7, "janela_fim_h": 13,          # 7:00–12:59
    "irr_min": 100.0, "limiar_indice": 0.80,           # dia SUJO se gerar < 80% do esperado
    "features": ["irradiancia", "cos_incidencia", "cos_zenite", "fator_geometrico",
                 "irr_no_plano", "temp_placa", "t_externa"],
}


# ---------------------------------------------------------------------------
# Geometria solar
# ---------------------------------------------------------------------------
def posicao_solar(ts, info):
    """cos do zênite e cos do ângulo de incidência no plano da placa (NOAA/Spencer)."""
    ts = pd.to_datetime(pd.Series(ts)).reset_index(drop=True)
    doy = ts.dt.dayofyear.to_numpy(dtype=float)
    hora = (ts.dt.hour + ts.dt.minute / 60 + ts.dt.second / 3600).to_numpy(dtype=float)
    g = 2 * np.pi / 365 * (doy - 1 + (hora - 12) / 24)
    eot = 229.18 * (0.000075 + 0.001868 * np.cos(g) - 0.032077 * np.sin(g)
                    - 0.014615 * np.cos(2 * g) - 0.040849 * np.sin(2 * g))
    decl = (0.006918 - 0.399912 * np.cos(g) + 0.070257 * np.sin(g) - 0.006758 * np.cos(2 * g)
            + 0.000907 * np.sin(2 * g) - 0.002697 * np.cos(3 * g) + 0.00148 * np.sin(3 * g))
    hora_solar = hora + (eot + 4 * info["longitude"] - 60 * info["fuso_h"]) / 60
    H = np.radians(15 * (hora_solar - 12))
    lat = np.radians(info["latitude"])
    cos_z = np.clip(np.sin(lat) * np.sin(decl) + np.cos(lat) * np.cos(decl) * np.cos(H), -1, 1)
    zen = np.arccos(cos_z)
    az = np.degrees(np.arctan2(np.sin(H), np.cos(H) * np.sin(lat) - np.tan(decl) * np.cos(lat))) + 180
    b, azp = np.radians(info["inclinacao"]), np.radians(info["azimute"])
    cos_inc = np.cos(zen) * np.cos(b) + np.sin(zen) * np.sin(b) * np.cos(np.radians(az) - azp)
    return cos_z, np.clip(cos_inc, 0, None)


def montar_features(ts, irradiancia, temp_placa, t_externa, info):
    """Tabela de entrada do modelo (mesma ordem de info['features'])."""
    cos_z, cos_inc = posicao_solar(ts, info)
    irr = pd.to_numeric(pd.Series(irradiancia), errors="coerce").to_numpy(dtype=float)
    fator = np.clip(cos_inc / np.clip(cos_z, 0.1, None), 0, 4)
    X = pd.DataFrame({
        "irradiancia": irr,
        "cos_incidencia": cos_inc,
        "cos_zenite": cos_z,
        "fator_geometrico": fator,
        "irr_no_plano": irr * fator,
        "temp_placa": pd.to_numeric(pd.Series(temp_placa), errors="coerce").to_numpy(dtype=float),
        "t_externa": pd.to_numeric(pd.Series(t_externa), errors="coerce").to_numpy(dtype=float),
    })
    return X[info["features"]]


# ---------------------------------------------------------------------------
# Preparação das leituras (mesmo critério do treino)
# ---------------------------------------------------------------------------
def amostrar_15min(df, col_ts="timestamp"):
    """Deixa no máximo 1 leitura por bloco de 15 min (a primeira). Dados antigos vinham
    de 1 em 1 min; o modelo foi treinado com 1 leitura a cada 15 min."""
    if df.empty:
        return df
    bloco = pd.to_datetime(df[col_ts]).dt.floor("15min")
    return df.loc[~bloco.duplicated()].reset_index(drop=True)


def janela_util(df, info, col_ts="timestamp", col_irr="irradiancia"):
    """Máscara da janela de julgamento: 7h–13h e irradiância ≥ irr_min."""
    h = pd.to_datetime(df[col_ts]).dt.hour
    return (h >= info["janela_inicio_h"]) & (h < info["janela_fim_h"]) & (df[col_irr] >= info["irr_min"])


def preparar_placa(df, col_pot, col_temp, info, col_irr="field7", col_text="field8"):
    """
    Converte leituras do ThingSpeak (fields) de UMA placa em tabela pronta p/ o modelo:
    15 em 15 min, só janela útil. NÃO descarta potência baixa — placa gerando pouco
    é justamente o que queremos detectar.
    """
    cols = ["timestamp", col_pot, col_temp, col_irr, col_text]
    if df is None or df.empty or any(c not in df for c in cols):
        return pd.DataFrame()
    d = df[cols].dropna(subset=["timestamp", col_pot, col_irr]).sort_values("timestamp")
    d = amostrar_15min(d).rename(columns={col_pot: "potencia", col_temp: "temp_placa",
                                         col_irr: "irradiancia", col_text: "t_externa"})
    d = d[janela_util(d, info)].reset_index(drop=True)
    if d.empty:
        return d
    d["temp_placa"] = d["temp_placa"].fillna(d["t_externa"])
    d["t_externa"] = d["t_externa"].fillna(d["temp_placa"])
    d["data"] = pd.to_datetime(d["timestamp"]).dt.date
    return d.dropna(subset=["temp_placa", "t_externa"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------
def carregar_modelos(pasta=PASTA_MODELOS):
    """Devolve (modelos, info, avaliacao). Modelos que não carregarem ficam de fora."""
    import joblib
    pasta = Path(pasta)
    info = dict(INFO_PADRAO)
    try:
        info.update(json.loads((pasta / "modelo_info.json").read_text(encoding="utf-8")))
    except Exception:
        pass
    modelos, erros = {}, {}
    for nome, arq in ARQUIVOS_MODELOS.items():
        try:
            modelos[nome] = joblib.load(pasta / arq)
        except Exception as e:
            erros[nome] = str(e)
    try:
        avaliacao = json.loads((pasta / "avaliacao.json").read_text(encoding="utf-8"))
    except Exception:
        avaliacao = {}
    info["erros_carregamento"] = erros
    return modelos, info, avaliacao


def prever(nome, modelos, d, info):
    """Potência esperada (W) de uma placa limpa para cada linha de `d` (saída de preparar_placa)."""
    if d.empty:
        return np.array([])
    if nome == FISICO:
        return (info["pmax"] * d["irradiancia"] / 1000).to_numpy(dtype=float)
    X = montar_features(d["timestamp"], d["irradiancia"], d["temp_placa"], d["t_externa"], info)
    return np.clip(modelos[nome].predict(X), 0, None)


def energia(d, coluna):
    """Wh na janela útil: cada leitura representa 15 min."""
    return float((d[coluna].clip(lower=0) * 0.25).sum()) if not d.empty else 0.0


def indice_diario(d, modelos, info, nomes=None):
    """Energia real x esperada por DIA, para cada modelo. Colunas: data, modelo,
    leituras, real_wh, esperado_wh, indice, veredito."""
    if d.empty:
        return pd.DataFrame()
    nomes = nomes or [n for n in ORDEM_MODELOS if n == FISICO or n in modelos]
    linhas = []
    for nome in nomes:
        p = prever(nome, modelos, d, info)
        tmp = d.assign(esperado=p).groupby("data").agg(
            leituras=("potencia", "size"),
            real_wh=("potencia", lambda s: float((s.clip(lower=0) * 0.25).sum())),
            esperado_wh=("esperado", lambda s: float((s * 0.25).sum())),
        ).reset_index()
        erro = d.assign(err=np.abs(p - d["potencia"].to_numpy())).groupby("data")["err"].mean()
        tmp["mae_w"] = tmp["data"].map(erro)
        tmp["modelo"] = nome
        linhas.append(tmp)
    out = pd.concat(linhas, ignore_index=True)
    out["indice"] = out["real_wh"] / out["esperado_wh"].replace(0, np.nan)
    out["veredito"] = np.where(out["indice"] < info["limiar_indice"], "SUJA", "LIMPA")
    return out
