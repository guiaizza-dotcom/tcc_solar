# ============================================================================
# 🌞 TCC SOLAR - DETECÇÃO DE SUJEIRA EM PLACAS FOTOVOLTAICAS
# ============================================================================

import re
import smtplib
from email.mime.text import MIMEText
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import requests

# ============================================================================
# ✅ CONFIGURAÇÃO DA PÁGINA (com PWA)
# ============================================================================

st.set_page_config(
    page_title="TCC Solar - Monitoramento",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://github.com/guiaizza-dotcom/tcc_solar",
        "Report a bug": "https://github.com/guiaizza-dotcom/tcc_solar/issues",
        "About": "🎓 TCC - Detecção de Sujeira em Placas Fotovoltaicas"
    }
)

# ============================================================================
# 📱 CONFIGURAÇÃO PWA (Progressive Web App para iPhone/Android)
# ============================================================================

pwa_html = """
<link rel="manifest" href="https://raw.githubusercontent.com/guiaizza-dotcom/tcc_solar/main/.streamlit/app_manifest.json">
<meta name="theme-color" content="#FACC15">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="TCC Solar">
<link rel="apple-touch-icon" href="https://raw.githubusercontent.com/guiaizza-dotcom/tcc_solar/main/app/icon.png">
"""

st.markdown(pwa_html, unsafe_allow_html=True)

# ============================================================================
# ⚙️ CONSTANTES E CONFIGURAÇÃO
# ============================================================================

SHEET_ID = "19jK526ZMo0BPvZ6sW3U5O0faVK16rsejEkpyYMBZ7Ec"
CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSuKaaNCw3461krN9wiYOhL01NISccPj1VMKRx6s3NdeK1G7Lj7G7tYs7C3Tr_oLcOwMCsLhsgTHrOc/pub?output=csv"
CRED_FILE = "credenciais.json"
EFICIENCIA = 0.85
IRRADIANCIA_STC = 1000.0
TARIFA_KWH = 0.75
LIMIAR_SUJEIRA = 10.0
EMAIL_ALERTA_PADRAO = "bittoleoguio@gmail.com"  # usado só se a planilha ainda não tiver e-mail salvo

# --- 💧 Parâmetros de CUSTO DE LIMPEZA (valores padrão; editáveis na barra lateral) ---
# O custo da limpeza considera apenas a ÁGUA utilizada (litros × preço do m³).
AGUA_LITROS_PADRAO        = 5.0    # litros de água por limpeza
AGUA_PRECO_M3_PADRAO      = 5.50   # R$ por m³ (veja na sua conta de água/saneamento)

# --- ThingSpeak (Minha Placa ao Vivo) ---
THINGSPEAK_CHANNEL_ID = "3337625"
THINGSPEAK_READ_API_KEY = "I7LHJFAFLIN4J5HJ"
THINGSPEAK_FIELD_IRRADIANCIA = 7  # Field 7 = Irradiação

# --- ThingSpeak (Canal "TCC" — Radiação Solar Estimada via Open-Meteo) ---
# Canal separado que grava a previsão da API do Open-Meteo, para comparar com o
# sensor real de irradiância do canal acima (field7).
THINGSPEAK_CHANNEL_ID_METEO = "3426951"
THINGSPEAK_READ_API_KEY_METEO = "NHG9H2BKG2NR1M3N"
THINGSPEAK_FIELD_RADIACAO_ESTIMADA = 1  # Field 1 = Radiação Solar Estimada (Open-Meteo)

# ============================================================================
# 🎨 ESTILOS CSS
# ============================================================================

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&display=swap');

html, body, [class*="css"], .stMarkdown, p, span, label { font-family:'Inter',sans-serif; }

/* 🌲 Fundo: verde escuro com um brilho de sol no canto — o painel "olha" pro céu */
.stApp{
    background:
        radial-gradient(ellipse 900px 520px at 88% -6%, rgba(250,204,21,0.16), transparent 60%),
        linear-gradient(180deg,#04140E 0%,#0B3D2A 32%,#0E4C36 58%,#04140E 100%);
}

h1,h2,h3{ font-family:'Space Grotesk',sans-serif; letter-spacing:.2px; }
h1{color:#facc15!important; text-shadow:0 0 22px rgba(250,204,21,.35);}
h2,h3{color:#bae6fd!important}

/* 🔲 Cards com cara de célula fotovoltaica: fundo escuro + grade + brilho diagonal (vidro) */
.card{
    background-color:#0b2239;
    background-image:
        linear-gradient(#123a63 1px, transparent 1px),
        linear-gradient(90deg,#123a63 1px, transparent 1px);
    background-size:18px 18px;
    border:1px solid #1e6091;
    border-radius:10px;
    padding:18px 14px;
    text-align:center;
    margin-bottom:10px;
    position:relative;
    overflow:hidden;
}
.card::after{
    content:"";
    position:absolute; inset:0; pointer-events:none;
    background:linear-gradient(115deg, transparent 42%, rgba(255,255,255,.06) 50%, transparent 58%);
}
.card-title{font-size:11px;color:#7da9c7;margin-bottom:4px;text-transform:uppercase;letter-spacing:.06em;position:relative;z-index:1}
.card-value{font-size:28px;font-weight:700;color:#f1f5f9;position:relative;z-index:1}
.card-unit{font-size:11px;color:#3e6c8f;margin-top:2px;position:relative;z-index:1}

/* 🚦 Caixa de diagnóstico */
.decision-box{border-radius:10px;padding:22px 28px;font-size:17px;font-weight:600;text-align:center;margin:8px 0 16px 0;border-width:2px;border-style:solid}
.ok{background:#0b3b24;border-color:#22c55e;color:#bbf7d0}
.alert{background:#4a1416;border-color:#ef4444;color:#fecaca}
.warn{background:#4a320b;border-color:#f59e0b;color:#fef3c7}

/* ⚖️ Veredito por placa (aba Comparação) */
.veredito{border:2px solid;border-radius:12px;padding:16px 14px;text-align:center;margin-bottom:12px}
.veredito-placa{font-family:'Space Grotesk',sans-serif;font-size:18px;font-weight:700}
.veredito-label{font-family:'Space Grotesk',sans-serif;font-size:36px;font-weight:700;letter-spacing:.05em;margin:2px 0}
.veredito-sub{font-size:13px;color:#cbd5e1}

/* 🧽 Requisitos de limpeza (aba Comparação) */
.req{background:#0b2239;border:1px solid #1e6091;border-radius:10px;padding:12px 16px;margin:4px 0 12px 0}
.req-titulo{font-size:11px;color:#7da9c7;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px}
.req-linha{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:7px 0;border-bottom:1px solid rgba(30,96,145,.4);font-size:14px;color:#e2e8f0}
.req-valor{font-weight:600;white-space:nowrap}
.req-decisao{margin-top:10px;padding:10px;border-radius:8px;text-align:center;font-weight:700;font-size:15px;border:1px solid}

/* 📱 Sidebar com o mesmo tom de céu/painel + filete dourado */
section[data-testid="stSidebar"]{
    background:linear-gradient(180deg,#071b2e 0%,#0b2239 100%);
    border-right:1px solid rgba(245,158,11,.25);
}

/* ☀️ Botões: dourado do sol, como se fossem "energia" clicável */
.stButton>button{
    background:linear-gradient(135deg,#facc15,#f59e0b);
    color:#1a1a1a; font-weight:700; border:none; border-radius:8px;
    transition:box-shadow .2s ease, transform .2s ease;
}
.stButton>button:hover{
    box-shadow:0 0 16px rgba(250,204,21,.5);
    transform:translateY(-1px);
    color:#1a1a1a;
}

/* 📑 Abas: destaque dourado na aba ativa */
.stTabs [aria-selected="true"]{ color:#facc15!important; border-bottom-color:#facc15!important; }

hr{ border-color:rgba(30,96,145,.5)!important; }
</style>""", unsafe_allow_html=True)

# ============================================================================
# 💧 CUSTO DE LIMPEZA — calculado a partir da água utilizada
# ============================================================================

def custo_total_limpeza(agua_litros, agua_preco_m3):
    """
    Custo de UMA limpeza (R$), considerando apenas a água:
      (litros / 1000) m³ × preço do m³
    """
    return (agua_litros / 1000.0) * agua_preco_m3

# ============================================================================
# 📡 FUNÇÕES DE DADOS
# ============================================================================

def gravar_potencia(potencia):
    """Grava potência na planilha do Google Sheets"""
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        if "gcp_service_account" in st.secrets:
            creds = Credentials.from_service_account_info(
                dict(st.secrets["gcp_service_account"]), scopes=scopes)
        else:
            creds = Credentials.from_service_account_file(CRED_FILE, scopes=scopes)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(SHEET_ID)
        ws = sh.sheet1
        ws.update("H2", [[potencia]])
        return True
    except Exception as e:
        st.error(f"Erro ao gravar na planilha: {e}")
        return False

def gravar_emails_alerta(emails):
    """Grava a lista de e-mails de alerta (até 10) na planilha do Google Sheets
    (célula I2, separados por vírgula), para persistir entre sessões."""
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        if "gcp_service_account" in st.secrets:
            creds = Credentials.from_service_account_info(
                dict(st.secrets["gcp_service_account"]), scopes=scopes)
        else:
            creds = Credentials.from_service_account_file(CRED_FILE, scopes=scopes)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(SHEET_ID)
        ws = sh.sheet1
        ws.update("I2", [[", ".join(emails)]])
        return True
    except Exception as e:
        st.error(f"Erro ao gravar e-mails na planilha: {e}")
        return False

@st.cache_data(ttl=30)
def carregar_emails_alerta():
    """Lê a lista de e-mails de alerta salva na planilha (célula I2, separados por
    vírgula). Retorna o e-mail padrão se a planilha nunca foi usada, ou lista
    vazia em caso de erro."""
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        if "gcp_service_account" in st.secrets:
            creds = Credentials.from_service_account_info(
                dict(st.secrets["gcp_service_account"]), scopes=scopes)
        else:
            creds = Credentials.from_service_account_file(CRED_FILE, scopes=scopes)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(SHEET_ID)
        ws = sh.sheet1
        valor = ws.acell("I2").value
        if not valor or not valor.strip():
            return [EMAIL_ALERTA_PADRAO]
        return [e.strip() for e in valor.split(",") if e.strip()][:10]
    except Exception:
        return []

def _abrir_planilha():
    """Abre a 1ª aba da planilha do Google Sheets com a service account."""
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    if "gcp_service_account" in st.secrets:
        creds = Credentials.from_service_account_info(
            dict(st.secrets["gcp_service_account"]), scopes=scopes)
    else:
        creds = Credentials.from_service_account_file(CRED_FILE, scopes=scopes)
    return gspread.authorize(creds).open_by_key(SHEET_ID).sheet1

def gravar_ultima_limpeza(data_hora, celula="J2"):
    """Grava a data/hora (horário de Brasília) da última limpeza de UMA placa na
    planilha (J2 = Placa Limpa, K2 = Placa Suja). Persiste entre sessões."""
    try:
        _abrir_planilha().update(celula, [[data_hora.strftime("%Y-%m-%d %H:%M:%S")]])
        return True
    except Exception as e:
        st.error(f"Erro ao gravar a data da limpeza na planilha: {e}")
        return False

@st.cache_data(ttl=30)
def carregar_ultima_limpeza(celula="J2"):
    """Lê a data/hora da última limpeza de UMA placa (J2 = Placa Limpa,
    K2 = Placa Suja). Retorna None se não houver registro ou em caso de erro."""
    try:
        valor = _abrir_planilha().acell(celula).value
        if not valor or not str(valor).strip():
            return None
        ts = pd.to_datetime(str(valor).strip(), errors="coerce")
        return None if pd.isna(ts) else ts.to_pydatetime()
    except Exception:
        return None

@st.cache_data(ttl=60)
def carregar_sheets():
    """Carrega dados da planilha Google Sheets"""
    try:
        df = pd.read_csv(CSV_URL)
        df.columns = [c.strip() for c in df.columns]

        # Renomear colunas
        rename = {}
        for col in df.columns:
            cl = col.lower()
            if "data" in cl or "hora" in cl:
                rename[col] = "timestamp"
            elif "nuven" in cl:
                rename[col] = "nuvens_pct"
            elif "temp" in cl:
                rename[col] = "temp_ambiente"
            elif "irradi" in cl:
                rename[col] = "irradiancia"
            elif "gera" in cl or "estimad" in cl:
                rename[col] = "geracao_estimada"

        df = df.rename(columns=rename)

        # Processar timestamp
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
            df = df.dropna(subset=["timestamp"]).sort_values("timestamp")

        # Converter colunas numéricas
        for col in ["nuvens_pct", "temp_ambiente", "irradiancia", "geracao_estimada"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", "."), errors="coerce").fillna(0)

        return df
    except Exception as e:
        st.error(f"Erro ao carregar planilha: {e}")
        return pd.DataFrame()

# Nomes amigáveis de cada field do canal (conforme Channel Settings do ThingSpeak)
THINGSPEAK_CAMPOS = {
    "field1": {"nome": "Potência Placa Suja", "unidade": "W", "cor": "#f59e0b"},
    "field2": {"nome": "Tensão Placa Suja", "unidade": "V", "cor": "#60a5fa"},
    "field3": {"nome": "Temperatura Placa Suja", "unidade": "°C", "cor": "#ef4444"},
    "field4": {"nome": "Potência Placa Limpa", "unidade": "W", "cor": "#22c55e"},
    "field5": {"nome": "Tensão Placa Limpa", "unidade": "V", "cor": "#34d399"},
    "field6": {"nome": "Temperatura Placa Limpa", "unidade": "°C", "cor": "#fb923c"},
    "field7": {"nome": "Irradiação", "unidade": "W/m²", "cor": "#facc15"},
    "field8": {"nome": "Temperatura Externa", "unidade": "°C", "cor": "#a78bfa"},
}

# Nomes amigáveis dos fields do canal "TCC" (Open-Meteo), conforme os widgets
# já criados no ThingSpeak: Field 1 = Radiação Solar Estimada, Field 2 = Umidade
# do Ar, Field 3 = Previsão de Chuva.
THINGSPEAK_CAMPOS_METEO = {
    "field1": {"nome": "Radiação Solar Estimada", "unidade": "W/m²", "cor": "#38bdf8"},
    "field2": {"nome": "Umidade do Ar (prevista)", "unidade": "%", "cor": "#818cf8"},
    "field3": {"nome": "Previsão de Chuva", "unidade": "%", "cor": "#94a3b8"},
}

def agora_brasil():
    """Retorna o datetime atual no horário de Brasília (UTC-3), não importa o fuso do servidor."""
    return datetime.utcnow() - pd.Timedelta(hours=3)

@st.cache_data(ttl=60)
def buscar_historico_thingspeak(data_inicio, data_fim, channel_id=THINGSPEAK_CHANNEL_ID,
                                 api_key=THINGSPEAK_READ_API_KEY, campos=None):
    """
    Busca o histórico do ThingSpeak entre duas datas (inclusive), já no horário de
    Brasília (UTC-3). O ThingSpeak grava tudo em UTC, então:
      1) convertemos o período pedido (horário local) para UTC antes de consultar a API;
      2) convertemos cada timestamp recebido de volta para horário local antes de devolver.
    Sem isso, uma leitura feita às 22h de um dia no Brasil chega marcada como
    01h do dia seguinte em UTC — e "hoje" na tela virava "amanhã".
    Pagina automaticamente porque o ThingSpeak limita 8000 registros por chamada.

    Aceita canal/API key/campos como parâmetros para poder reaproveitar esta mesma
    função com QUALQUER canal do ThingSpeak — por padrão usa o canal da Minha Placa
    (sensores), mas também é usada para buscar o canal "TCC" com a previsão do
    Open-Meteo (veja THINGSPEAK_CHANNEL_ID_METEO / THINGSPEAK_CAMPOS_METEO).
    """
    campos = campos or THINGSPEAK_CAMPOS
    url = f"https://api.thingspeak.com/channels/{channel_id}/feeds.json"
    todos_registros = []

    # Período pedido é local (Brasil) -> converte para UTC para consultar a API
    inicio_utc = datetime.combine(data_inicio, datetime.min.time()) + pd.Timedelta(hours=3)
    fim_utc = datetime.combine(data_fim, datetime.max.time()) + pd.Timedelta(hours=3)
    inicio_atual = inicio_utc

    while inicio_atual <= fim_utc:
        params = {
            "api_key": api_key,
            "start": inicio_atual.strftime("%Y-%m-%d %H:%M:%S"),
            "end": fim_utc.strftime("%Y-%m-%d %H:%M:%S"),
            "results": 8000,
        }
        try:
            resp = requests.get(url, params=params, timeout=20)
            resp.raise_for_status()
            feeds = resp.json().get("feeds", [])
        except Exception as e:
            st.error(f"Erro ao buscar histórico do ThingSpeak (canal {channel_id}): {e}")
            break

        if not feeds:
            break

        for f in feeds:
            ts_utc = pd.to_datetime(f.get("created_at"), utc=True)
            ts_local = ts_utc.tz_convert(None) - pd.Timedelta(hours=3) if pd.notna(ts_utc) else pd.NaT
            registro = {"timestamp": ts_local}
            for campo in campos:
                registro[campo] = pd.to_numeric(f.get(campo), errors="coerce")
            todos_registros.append(registro)

        # Se voltou menos que o limite de página, já cobrimos tudo
        if len(feeds) < 8000:
            break

        ultimo_ts_utc = pd.to_datetime(feeds[-1]["created_at"], utc=True).tz_convert(None)
        inicio_atual = ultimo_ts_utc + pd.Timedelta(seconds=1)

    df_hist = pd.DataFrame(todos_registros)
    if not df_hist.empty:
        df_hist = df_hist.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    return df_hist


@st.cache_data(ttl=60)
def buscar_comparacao_irradiancia(data_inicio, data_fim):
    """
    Junta, para o mesmo período, a irradiância REAL medida pelo sensor (canal
    THINGSPEAK_CHANNEL_ID, field7) com a irradiância ESTIMADA pelo Open-Meteo
    (canal THINGSPEAK_CHANNEL_ID_METEO, field1 = "Radiação Solar Estimada").

    Os dois canais não gravam exatamente no mesmo instante, então usamos
    merge_asof para casar cada leitura do sensor com a leitura de previsão mais
    próxima no tempo (tolerância de 15 min — além disso não casa).
    """
    df_sensor = buscar_historico_thingspeak(data_inicio, data_fim)
    df_meteo = buscar_historico_thingspeak(
        data_inicio, data_fim,
        channel_id=THINGSPEAK_CHANNEL_ID_METEO,
        api_key=THINGSPEAK_READ_API_KEY_METEO,
        campos=THINGSPEAK_CAMPOS_METEO,
    )

    if df_sensor.empty or df_meteo.empty:
        return pd.DataFrame()

    sensor = (
        df_sensor[["timestamp", "field7"]]
        .rename(columns={"field7": "irradiancia_sensor"})
        .dropna(subset=["irradiancia_sensor"])
        .sort_values("timestamp")
    )
    meteo = (
        df_meteo[["timestamp", "field1", "field2", "field3"]]
        .rename(columns={
            "field1": "irradiancia_estimada",
            "field2": "umidade_estimada",
            "field3": "chuva_estimada",
        })
        .sort_values("timestamp")
    )

    comp = pd.merge_asof(
        sensor, meteo, on="timestamp", direction="nearest",
        tolerance=pd.Timedelta("15min"),
    )
    return comp.dropna(subset=["irradiancia_estimada"]).reset_index(drop=True)

def analisar(df, potencia_w, custo_limpeza):
    """
    Analisa os dados e decide se compensa limpar.

    NOVA LÓGICA (integrada ao custo real de limpeza):
      - A perda de energia de cada amostra é calculada usando o INTERVALO REAL de
        tempo entre uma leitura e a anterior (não mais o antigo "× 48", que assumia
        12 h de sol constante). Isso torna a perda em R$ defensável na banca.
      - A DECISÃO é feita no nível do período: soma-se a perda em R$ de todas as
        amostras, calcula-se a PERDA MÉDIA POR DIA e compara-se diretamente com o
        CUSTO DA LIMPEZA (água utilizada):

              compensa_limpar  =  (perda_diaria  >=  custo_limpeza)

        Ou seja: quando a placa perde por dia MAIS do que custa limpá-la, recomenda
        limpar. Se perde menos, o sistema informa em quantos dias a sujeira
        acumulada vai "pagar" a limpeza (payback).

    Recebe o custo de limpeza já calculado (R$) para não recalcular a cada linha.
    """
    df = df.sort_values("timestamp").reset_index(drop=True)

    # Intervalo real (horas) entre cada leitura e a anterior.
    # A 1ª leitura (e o caso de leitura única) assume 15 min = 0.25 h como padrão.
    dt_h = df["timestamp"].diff().dt.total_seconds().div(3600)
    dt_h = dt_h.bfill().fillna(0.25)

    rows = []
    for i, row in df.iterrows():
        irrad    = row.get("irradiancia", 0)
        ger_prev = row.get("geracao_estimada", 0)                       # W (previsto pela API)
        ger_real = (irrad / IRRADIANCIA_STC) * potencia_w * EFICIENCIA  # W (teórico da placa)

        # Perda percentual instantânea
        perda_pct = max(0, (ger_prev - ger_real) / ger_prev * 100) if ger_prev > 0 else 0
        ind = perda_pct > LIMIAR_SUJEIRA

        # Energia perdida NESTA amostra (kWh), usando o intervalo REAL entre leituras:
        #   potência_perdida(W) × tempo(h) / 1000 = energia(kWh)
        e_perd_kwh = max(0, ger_prev - ger_real) * dt_h[i] / 1000.0
        p_fin      = e_perd_kwh * TARIFA_KWH   # R$ perdidos nesta amostra

        rows.append({
            "geracao_prevista": ger_prev,
            "geracao_real": round(ger_real, 3),
            "perda_percentual": round(perda_pct, 2),
            "indicativo_sujeira": ind,
            "energia_perdida_kwh": e_perd_kwh,
            "perda_financeira": round(p_fin, 4),
            "custo_limpeza": round(custo_limpeza, 4),
        })

    an = pd.DataFrame(rows)

    # ---- DECISÃO no nível do PERÍODO: perda em R$ acumulada vs custo de limpeza ----
    dias = max(1, (df["timestamp"].max() - df["timestamp"].min()).days + 1)
    perda_acumulada = an["perda_financeira"].sum()      # R$ perdidos no período todo
    perda_diaria    = perda_acumulada / dias            # R$/dia médio

    compensa = bool(perda_diaria >= custo_limpeza) and bool(an["indicativo_sujeira"].any())
    dias_payback = (custo_limpeza / perda_diaria) if perda_diaria > 0 else float("inf")

    if not an["indicativo_sujeira"].any():
        msg = "✅ Placa OK. Limpeza não necessária."
    elif compensa:
        msg = (f"🚨 Sujeira detectada. Perda ~R${perda_diaria:.2f}/dia ≥ "
               f"custo de limpeza R${custo_limpeza:.2f}. COMPENSA LIMPAR.")
    else:
        payback_txt = f"{dias_payback:.1f} dias" if dias_payback != float("inf") else "—"
        msg = (f"⚠️ Sujeira leve. Perda ~R${perda_diaria:.2f}/dia < "
               f"custo R${custo_limpeza:.2f}. Aguardar (a sujeira paga a limpeza em ~{payback_txt}).")

    # Valores de período replicados em todas as linhas (facilita ler an.iloc[-1])
    an["compensa_limpar"]  = compensa
    an["mensagem_status"]  = msg
    an["perda_diaria_est"] = round(perda_diaria, 4)
    an["dias_payback"]     = round(dias_payback, 2) if dias_payback != float("inf") else None
    return an

def card(titulo, valor, unidade="", cor="#f1f5f9"):
    """Exibe um card com métrica"""
    st.markdown(
        f'<div class="card"><div class="card-title">{titulo}</div><div class="card-value" style="color:{cor}">{valor}</div><div class="card-unit">{unidade}</div></div>',
        unsafe_allow_html=True
    )

# ============================================================================
# 📊 CONFIGURAÇÕES DE LAYOUT DOS GRÁFICOS
# ============================================================================

def hex_para_rgba(hex_color, alpha=0.15):
    """Converte '#RRGGBB' em 'rgba(r,g,b,alpha)' — formato aceito por todas as versões do Plotly
    (o formato antigo '#RRGGBB' + hex de transparência, ex: '#f59e0b26', passou a ser rejeitado)."""
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"

LAY = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#cbd5e1", size=12),
    legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor="#334155", borderwidth=1),
    margin=dict(l=10, r=10, t=36, b=10),
    xaxis=dict(gridcolor="#1e293b", linecolor="#334155"),
    yaxis=dict(gridcolor="#1e293b", linecolor="#334155"),
    hovermode="x unified"
)

# ============================================================================
# 🧪 TESTE DE NOTIFICAÇÃO (usando Streamlit, sem JavaScript)
# ============================================================================

def mostrar_botao_teste_notificacao():
    """Mostra um botão para testar a notificação"""
    st.sidebar.markdown("---")
    st.sidebar.subheader("🧪 Teste")
    if st.sidebar.button("📢 Testar Notificação", use_container_width=True):
        st.success("✅ NOTIFICAÇÃO DE TESTE DISPARADA!")
        st.info("📢 TESTE: LIMPEZA NECESSÁRIA!\n\nEsta é uma notificação de teste! Perda: 25.5%. Perda diária: R$12.50. COMPENSA LIMPAR!")

# ============================================================================
# 📧 ABA: NOTIFICAÇÃO AUTOMÁTICA POR E-MAIL (Gmail SMTP)
# ============================================================================
# Como funciona (gratuito, usando a SUA própria conta Gmail — configurada 1x por você,
# o cliente final não precisa fazer nenhum cadastro, só digitar o e-mail dele):
# 1. Ative a verificação em 2 etapas na sua Conta Google (necessário p/ o próximo passo).
# 2. Crie uma "Senha de app" em: https://myaccount.google.com/apppasswords
#    (escolha "outro" e dê um nome, ex: "TCC Solar"). Você recebe uma senha de 16 letras.
# 3. Salve essas credenciais no arquivo .streamlit/secrets.toml do projeto:
#      gmail_remetente = "seuemail@gmail.com"
#      gmail_senha_app = "xxxxxxxxxxxxxxxx"
#    Assim o cliente final NUNCA vê nem precisa saber dessas credenciais — ele só
#    digita o próprio e-mail no campo da aba e pronto, os alertas chegam sozinhos.

def email_valido(email: str) -> bool:
    """Validação simples de formato de e-mail."""
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) is not None

def enviar_email_gmail(remetente: str, senha_app: str, destinatarios, assunto: str, mensagem: str):
    """Envia e-mail via Gmail SMTP para um ou mais destinatários (lista de até 10).
    Retorna (sucesso: bool, detalhe: str)."""
    if isinstance(destinatarios, str):
        destinatarios = [destinatarios]
    destinatarios = [d.strip() for d in destinatarios if d and d.strip()]
    if not destinatarios:
        return False, "Nenhum destinatário informado."
    try:
        msg = MIMEText(mensagem)
        msg["Subject"] = assunto
        msg["From"] = remetente
        msg["To"] = ", ".join(destinatarios)

        with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as servidor:
            servidor.starttls()
            servidor.login(remetente, senha_app)
            servidor.sendmail(remetente, destinatarios, msg.as_string())
        return True, "OK"
    except smtplib.SMTPAuthenticationError:
        return False, "Falha de autenticação — confira o e-mail e a Senha de app do Gmail (configurados em secrets.toml)."
    except Exception as e:
        return False, f"Falha ao enviar: {e}"

def render_aba_email():
    """
    Aba onde o cliente final cadastra até 10 e-mails para receber alerta automático
    (sem nenhuma senha ou cadastro complexo). A lista fica salva na planilha do
    Google Sheets (persiste entre sessões e reinicializações do app). Sempre que
    o sistema detectar que compensa limpar a placa, TODOS os e-mails da lista
    recebem o alerta.
    """
    st.subheader("📧 Alertas por e-mail")
    st.caption(
        "Cadastre até **10 e-mails** abaixo. Sempre que o sistema detectar que a limpeza "
        "da placa compensa financeiramente, todos eles recebem um alerta automático — "
        "não é preciso nenhum cadastro."
    )

    if "emails_alerta" not in st.session_state:
        st.session_state["emails_alerta"] = carregar_emails_alerta()
    if "ultimo_alerta_enviado" not in st.session_state:
        st.session_state["ultimo_alerta_enviado"] = False
    if "erro_email" not in st.session_state:
        st.session_state["erro_email"] = ""

    def _adicionar_email():
        novo = st.session_state.get("novo_email_input", "").strip()
        lista = list(st.session_state.get("emails_alerta", []))
        if not novo:
            return
        if not email_valido(novo):
            st.session_state["erro_email"] = "E-mail inválido. Confira o formato digitado."
            return
        if novo.lower() in [e.lower() for e in lista]:
            st.session_state["erro_email"] = "Esse e-mail já está na lista."
            return
        if len(lista) >= 10:
            st.session_state["erro_email"] = "Limite de 10 e-mails atingido. Remova algum para adicionar outro."
            return
        lista.append(novo)
        st.session_state["emails_alerta"] = lista
        st.session_state["erro_email"] = ""
        if gravar_emails_alerta(lista):
            st.cache_data.clear()
        st.session_state["novo_email_input"] = ""

    def _remover_email(indice):
        def _callback():
            lista = list(st.session_state.get("emails_alerta", []))
            if 0 <= indice < len(lista):
                lista.pop(indice)
                st.session_state["emails_alerta"] = lista
                if gravar_emails_alerta(lista):
                    st.cache_data.clear()
        return _callback

    emails = st.session_state["emails_alerta"]

    st.markdown(f"**E-mails cadastrados ({len(emails)}/10):**")
    if not emails:
        st.info("Nenhum e-mail cadastrado ainda. Adicione um abaixo.")
    else:
        for i, e in enumerate(emails):
            col_e1, col_e2 = st.columns([5, 1])
            with col_e1:
                st.markdown(
                    f'<div class="card" style="text-align:left;padding:10px 16px;margin-bottom:6px">'
                    f'<span style="color:#f1f5f9">📩 {e}</span></div>',
                    unsafe_allow_html=True,
                )
            with col_e2:
                st.button(
                    "🗑️ Remover", key=f"remover_email_{i}", use_container_width=True,
                    on_click=_remover_email(i),
                )

    if len(emails) < 10:
        col_a1, col_a2 = st.columns([4, 1])
        with col_a1:
            st.text_input(
                "Adicionar e-mail", key="novo_email_input",
                placeholder="seuemail@exemplo.com", label_visibility="collapsed",
            )
        with col_a2:
            st.button("➕ Adicionar", use_container_width=True, on_click=_adicionar_email)
    else:
        st.warning("Limite de 10 e-mails atingido. Remova algum da lista acima para adicionar outro.")

    if st.session_state.get("erro_email"):
        st.error(st.session_state["erro_email"])

    st.markdown("---")
    st.subheader("🧪 Diagnóstico e teste manual")

    remetente = st.secrets.get("gmail_remetente", "") if hasattr(st, "secrets") else ""
    senha_app = st.secrets.get("gmail_senha_app", "") if hasattr(st, "secrets") else ""

    if remetente and senha_app:
        st.success(f"Credenciais do Gmail encontradas nos Secrets (remetente: {remetente}).")
    else:
        st.error(
            "❌ Não encontrei 'gmail_remetente' e/ou 'gmail_senha_app' nos Secrets do Streamlit Cloud. "
            "Vá em Settings → Secrets do seu app e confira se estão salvos exatamente com esses nomes."
        )

    if st.button("📨 Enviar e-mail de teste agora", use_container_width=True):
        emails_validos = [e for e in st.session_state.get("emails_alerta", []) if email_valido(e)]
        if not emails_validos:
            st.error("Cadastre ao menos um e-mail válido na lista acima antes de testar.")
        elif not remetente or not senha_app:
            st.error("Não é possível testar: credenciais do Gmail não configuradas nos Secrets.")
        else:
            with st.spinner(f"Enviando e-mail de teste para {len(emails_validos)} destinatário(s)..."):
                sucesso, detalhe = enviar_email_gmail(
                    remetente, senha_app, emails_validos,
                    "TCC Solar - Teste de notificação",
                    "Esta é uma mensagem de teste enviada manualmente pela aba de e-mail do TCC Solar.",
                )
            if sucesso:
                st.success(
                    f"✅ E-mail de teste enviado para {len(emails_validos)} destinatário(s)! "
                    "Confira a caixa de entrada (e o Spam) em alguns segundos."
                )
            else:
                st.error(f"❌ Falha ao enviar: {detalhe}")

def verificar_e_enviar_alerta_email(compensa_limpar: bool, mensagem_alerta: str):
    """
    Chamada a cada carregamento da página: se 'compensa_limpar' for True e houver
    e-mails cadastrados na sessão, envia o alerta automaticamente para TODOS eles
    (uma vez só por ocorrência, evitando reenviar a cada atualização da página).
    """
    emails = st.session_state.get("emails_alerta")
    if emails is None:
        emails = carregar_emails_alerta()
        st.session_state["emails_alerta"] = emails
    emails_validos = [e for e in emails if email_valido(e)]
    if not emails_validos:
        return

    remetente = st.secrets.get("gmail_remetente", "") if hasattr(st, "secrets") else ""
    senha_app = st.secrets.get("gmail_senha_app", "") if hasattr(st, "secrets") else ""
    if not remetente or not senha_app:
        return  # credenciais não configuradas em secrets.toml — nada a fazer

    if compensa_limpar and not st.session_state.get("ultimo_alerta_enviado", False):
        sucesso, _ = enviar_email_gmail(
            remetente, senha_app, emails_validos,
            "TCC Solar - Limpeza da placa recomendada",
            mensagem_alerta,
        )
        st.session_state["ultimo_alerta_enviado"] = True
        if sucesso:
            st.toast(f"📧 Alerta enviado para {len(emails_validos)} e-mail(s)!")
    elif not compensa_limpar:
        # Reseta a trava assim que a placa deixa de precisar de limpeza,
        # para que um novo alerta seja disparado na próxima vez que voltar a compensar.
        st.session_state["ultimo_alerta_enviado"] = False

# ============================================================================
# ☀️ ABA: MINHA PLACA AO VIVO (ThingSpeak)
# ============================================================================

def render_placa_ao_vivo():
    """Aba que mostra os dados do ThingSpeak (todos os 8 fields do canal) para o período escolhido"""
    st.subheader("☀️ Minha Placa ao Vivo — ThingSpeak")

    # ============================================================================
    # 📅 PERÍODO DE ANÁLISE — controla TUDO nesta aba (cards, gráficos e tabelas)
    # ============================================================================
    hoje = agora_brasil().date()
    if "ts_data_inicio" not in st.session_state:
        st.session_state["ts_data_inicio"] = hoje
    if "ts_data_fim" not in st.session_state:
        st.session_state["ts_data_fim"] = hoje

    def _definir_periodo_hoje():
        # Roda ANTES da página recriar os widgets (callback do on_click), por isso
        # pode alterar session_state de "ts_data_inicio"/"ts_data_fim" sem conflito.
        d = agora_brasil().date()
        st.session_state["ts_data_inicio"] = d
        st.session_state["ts_data_fim"] = d

    col_p1, col_p2, col_p3, col_p4 = st.columns([1, 1, 1, 1])
    with col_p1:
        data_inicio = st.date_input("De:", key="ts_data_inicio")
    with col_p2:
        data_fim = st.date_input("Até:", key="ts_data_fim")
    with col_p3:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        st.button("📆 Só hoje", use_container_width=True, key="btn_ts_hoje", on_click=_definir_periodo_hoje)
    with col_p4:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        if st.button("🔄 Atualizar", use_container_width=True, key="btn_atualizar_thingspeak"):
            st.cache_data.clear()
            st.rerun()

    if data_inicio > data_fim:
        st.error("A data 'De' não pode ser depois da data 'Até'.")
        return

    with st.spinner("Buscando dados do ThingSpeak..."):
        df_ts = buscar_historico_thingspeak(data_inicio, data_fim)

    if df_ts.empty:
        st.warning("⚠️ Sem dados no ThingSpeak para o período selecionado.")
        return

    ultima = df_ts.iloc[-1]
    st.caption(
        f"Período: {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')} "
        f"— {len(df_ts)} leituras — última: {ultima['timestamp'].strftime('%d/%m/%Y %H:%M:%S')} (horário de Brasília)"
    )

    # Cards com o valor mais recente de cada field
    st.subheader("Valores Atuais")
    campos = list(THINGSPEAK_CAMPOS.items())
    linha1, linha2 = campos[:4], campos[4:]

    cols1 = st.columns(4)
    for col, (campo, info) in zip(cols1, linha1):
        with col:
            valor = ultima.get(campo)
            texto = f"{valor:.1f}" if pd.notna(valor) else "—"
            card(info["nome"], texto, info["unidade"], info["cor"])

    cols2 = st.columns(4)
    for col, (campo, info) in zip(cols2, linha2):
        with col:
            valor = ultima.get(campo)
            texto = f"{valor:.1f}" if pd.notna(valor) else "—"
            card(info["nome"], texto, info["unidade"], info["cor"])

    st.markdown("---")

    # Gráfico comparativo: Placa Suja vs Placa Limpa (potência) — período inteiro, escala única
    st.subheader("Potência: Placa Suja vs Placa Limpa")
    fig_pot = go.Figure()
    fig_pot.add_trace(go.Scatter(
        x=df_ts["timestamp"], y=df_ts["field1"],
        name="Placa Suja", mode="lines", line=dict(color="#f59e0b", width=2)
    ))
    fig_pot.add_trace(go.Scatter(
        x=df_ts["timestamp"], y=df_ts["field4"],
        name="Placa Limpa", mode="lines", line=dict(color="#22c55e", width=2)
    ))
    fig_pot.update_layout(**LAY, title="Potência (W)", yaxis_title="W")
    st.plotly_chart(fig_pot, use_container_width=True)

    st.markdown("---")

    # ============================================================================
    # 🛰️ COMPARAÇÃO: SENSOR DE IRRADIÂNCIA (real) vs OPEN-METEO (previsto)
    # ============================================================================
    st.subheader("🛰️ Irradiância: Sensor Real vs Previsão (Open-Meteo)")
    st.caption(
        "Mesma ideia da comparação Placa Suja vs Placa Limpa, mas aqui comparando o "
        "sensor de irradiância (canal ThingSpeak da placa) com a radiação solar "
        "estimada pela API do Open-Meteo (canal ThingSpeak separado) — ajuda a "
        "validar se o sensor está calibrado e se a previsão bate com a realidade."
    )

    with st.spinner("Buscando dados do canal Open-Meteo..."):
        df_comp = buscar_comparacao_irradiancia(data_inicio, data_fim)

    if df_comp.empty:
        st.warning(
            "⚠️ Sem dados suficientes para comparar sensor e previsão nesse período "
            "(confira se o canal 'TCC' (Open-Meteo) tem leituras nesse intervalo)."
        )
    else:
        ultima_comp = df_comp.iloc[-1]
        cc1, cc2, cc3 = st.columns(3)
        with cc1:
            card("Sensor (real)", f"{ultima_comp['irradiancia_sensor']:.0f}", "W/m²", "#facc15")
        with cc2:
            card("Open-Meteo (previsto)", f"{ultima_comp['irradiancia_estimada']:.0f}", "W/m²", "#38bdf8")
        with cc3:
            estimada = ultima_comp["irradiancia_estimada"]
            diff = ultima_comp["irradiancia_sensor"] - estimada
            diff_pct = (diff / estimada * 100) if estimada else 0
            cor_diff = "#22c55e" if abs(diff_pct) <= 10 else "#ef4444"
            card("Diferença", f"{diff:+.0f} W/m² ({diff_pct:+.1f}%)", "sensor − previsto", cor_diff)

        fig_comp = go.Figure()
        fig_comp.add_trace(go.Scatter(
            x=df_comp["timestamp"], y=df_comp["irradiancia_sensor"],
            name="Sensor (real)", mode="lines", line=dict(color="#facc15", width=2)
        ))
        fig_comp.add_trace(go.Scatter(
            x=df_comp["timestamp"], y=df_comp["irradiancia_estimada"],
            name="Open-Meteo (previsto)", mode="lines",
            line=dict(color="#38bdf8", width=2, dash="dash")
        ))
        fig_comp.add_trace(go.Scatter(
            x=pd.concat([df_comp["timestamp"], df_comp["timestamp"][::-1]]),
            y=pd.concat([df_comp["irradiancia_sensor"], df_comp["irradiancia_estimada"][::-1]]),
            fill="toself", fillcolor="rgba(56,189,248,0.12)",
            line=dict(color="rgba(0,0,0,0)"),
            name="Diferença", hoverinfo="skip"
        ))
        fig_comp.update_layout(**LAY, title="Irradiância: Sensor vs Open-Meteo (W/m²)", yaxis_title="W/m²")
        st.plotly_chart(fig_comp, use_container_width=True)

        with st.expander("📋 Ver dados da comparação Sensor x Open-Meteo"):
            st.dataframe(
                df_comp.rename(columns={
                    "irradiancia_sensor": "Sensor (W/m²)",
                    "irradiancia_estimada": "Open-Meteo (W/m²)",
                    "umidade_estimada": "Umidade prevista (%)",
                    "chuva_estimada": "Chance de chuva (%)",
                }).sort_values("timestamp", ascending=False),
                use_container_width=True, hide_index=True,
            )

    st.markdown("---")

    # Um gráfico de histórico para cada field, dois por linha — mesmo período, escala única
    st.subheader("Histórico por Sensor")
    itens = list(THINGSPEAK_CAMPOS.items())
    for i in range(0, len(itens), 2):
        par = itens[i:i+2]
        cols = st.columns(len(par))
        for col, (campo, info) in zip(cols, par):
            with col:
                fig = go.Figure(go.Scatter(
                    x=df_ts["timestamp"], y=df_ts[campo],
                    fill="tozeroy", fillcolor=hex_para_rgba(info["cor"], 0.15),
                    line=dict(color=info["cor"], width=2), name=info["nome"]
                ))
                fig.update_layout(**LAY, title=f"{info['nome']} ({info['unidade']})", yaxis_title=info["unidade"])
                st.plotly_chart(fig, use_container_width=True)

    with st.expander(f"📋 Ver todas as leituras do período ({len(df_ts)})"):
        st.dataframe(df_ts.sort_values("timestamp", ascending=False), use_container_width=True, hide_index=True)

    # ============================================================================
    # 📅 HISTÓRICO POR DATA — mesma consulta acima, organizada em tabela por dia
    # ============================================================================
    st.markdown("---")
    st.subheader("📅 Histórico Organizado por Data")
    st.caption(
        "O mesmo período selecionado acima, agora organizado por dia em tabela — "
        "dá pra ver todas as leituras de cada dia, ou só o **pico** (maior valor) de cada dia."
    )

    col_h1, col_h2 = st.columns([1.4, 1])
    with col_h1:
        campo_pico = st.selectbox(
            "Campo para calcular o pico:",
            options=list(THINGSPEAK_CAMPOS.keys()),
            format_func=lambda c: THINGSPEAK_CAMPOS[c]["nome"],
            index=0,
            key="hist_campo_pico",
        )
    with col_h2:
        modo_hist = st.radio(
            "Como exibir:",
            ["📋 Todos os registros", "📈 Somente o pico de cada dia"],
            key="hist_modo",
        )

    df_hist = df_ts.copy()
    df_hist["data"] = df_hist["timestamp"].dt.date
    df_hist["hora"] = df_hist["timestamp"].dt.strftime("%H:%M:%S")

    nomes_colunas = {
        c: f'{THINGSPEAK_CAMPOS[c]["nome"]} ({THINGSPEAK_CAMPOS[c]["unidade"]})'
        for c in THINGSPEAK_CAMPOS
    }
    nomes_colunas["hora"] = "Hora"
    nomes_colunas["Data"] = "Data"

    if modo_hist.startswith("📋"):
        # Todos os registros, agrupados por dia (do mais recente para o mais antigo)
        for dia in sorted(df_hist["data"].unique(), reverse=True):
            df_dia = df_hist[df_hist["data"] == dia].sort_values("timestamp", ascending=False)
            with st.expander(f"📆 {dia.strftime('%d/%m/%Y')} — {len(df_dia)} leituras"):
                colunas = ["hora"] + list(THINGSPEAK_CAMPOS.keys())
                st.dataframe(
                    df_dia[colunas].rename(columns=nomes_colunas),
                    use_container_width=True,
                    hide_index=True,
                )
    else:
        # Somente o pico (valor máximo do campo escolhido) de cada dia
        linhas_pico = []
        for dia, df_dia in df_hist.groupby("data"):
            if df_dia[campo_pico].notna().any():
                linhas_pico.append(df_hist.loc[df_dia[campo_pico].idxmax()])

        if not linhas_pico:
            st.warning("Não há dados suficientes para calcular picos nesse período.")
        else:
            df_picos = pd.DataFrame(linhas_pico).sort_values("data", ascending=False)
            df_picos["Data"] = df_picos["data"].apply(lambda d: d.strftime("%d/%m/%Y"))
            colunas_pico = ["Data", "hora"] + list(THINGSPEAK_CAMPOS.keys())
            tabela_picos = df_picos[colunas_pico].rename(columns=nomes_colunas)
            st.dataframe(tabela_picos, use_container_width=True, hide_index=True)
            st.caption(f"Pico calculado com base em: **{THINGSPEAK_CAMPOS[campo_pico]['nome']}**")

            csv = tabela_picos.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Baixar picos em CSV", csv, "picos_por_dia.csv", "text/csv",
                use_container_width=True,
            )

# ============================================================================
# ⚖️ ABA: COMPARAÇÃO — JULGAMENTO LIMPA x SUJA DE CADA PLACA
# ============================================================================
# Objetivo: tela enxuta para a banca e para os testes. Para cada placa mostra só:
#   • veredito do sistema (LIMPA / SUJA)
#   • potência medida x potência esperada (Pmax × G/1000)
#   • energia gerada x energia esperada
#   • requisitos de limpeza (limiar de sujeira e perda R$/dia x custo da água)
# A irradiação é comum às duas placas e aparece uma vez só, no topo.

# Fields de cada placa no canal ThingSpeak (os nomes são só rótulos das bancadas)
PLACA_LIMPA = {"nome": "Placa Limpa", "emoji": "🟢", "cor": "#22c55e",
               "potencia": "field4", "celula": "J2"}
PLACA_SUJA  = {"nome": "Placa Suja",  "emoji": "🟠", "cor": "#f59e0b",
               "potencia": "field1", "celula": "K2"}

# Abaixo dessa irradiação (noite/amanhecer/entardecer) a comparação vira ruído,
# então essas leituras não entram no julgamento.
IRRAD_MIN_JULGAMENTO = 50.0    # W/m²
# Energia esperada mínima no período para o julgamento ser confiável
ENERGIA_MIN_JULGAMENTO = 1.0   # Wh

def _fmt(v, casas=1):
    """Formata número; devolve '—' se vazio/NaN."""
    return f"{v:.{casas}f}" if v is not None and pd.notna(v) else "—"

def _fmt_rs(v):
    """R$ com 2 casas para valores ≥ R$1 e 3 casas para centavos (a perda é pequena)."""
    if v is None or pd.isna(v):
        return "—"
    return f"R$ {v:.2f}" if abs(v) >= 1 else f"R$ {v:.3f}"

def perda_vs_esperado(df, campo_pot, pmax, g_min=0.0):
    """
    Perda de UMA placa em relação ao que ela deveria gerar pela regra física do TCC:
        P_esperada = Pmax × G / 1000      (G = irradiação, field7)
    Cada leitura é multiplicada pelo intervalo real até a anterior (limitado a
    30 min) → Wh. Leituras com G < g_min são descartadas (sem sol = ruído).
    Retorna None se não houver leituras suficientes.
    """
    d = df[["timestamp", campo_pot, "field7"]].dropna().sort_values("timestamp").copy()
    if len(d) < 2:
        return None
    d["dt_h"] = d["timestamp"].diff().dt.total_seconds().div(3600).fillna(0).clip(upper=0.5)
    d = d[d["field7"] >= g_min]
    if d.empty:
        return None
    d["esperada"] = pmax * d["field7"].clip(lower=0) / IRRADIANCIA_STC
    d["real"] = d[campo_pot].clip(lower=0)
    d["perda_w"] = (d["esperada"] - d["real"]).clip(lower=0)

    e_esperada = float((d["esperada"] * d["dt_h"]).sum())
    e_real = float((d["real"] * d["dt_h"]).sum())
    perda_wh = float((d["perda_w"] * d["dt_h"]).sum())
    return {
        "df": d,
        "e_esperada": e_esperada,
        "e_real": e_real,
        "perda_wh": perda_wh,
        "perda_pct": perda_wh / e_esperada * 100 if e_esperada > 0 else 0.0,
        "perda_rs": perda_wh / 1000.0 * TARIFA_KWH,
    }

def _avaliar_placa(df, placa, pmax, custo_limpeza):
    """
    Julga UMA placa no período e devolve tudo que a tela precisa:
      veredito  : 'LIMPA' | 'SUJA' | 'SEM SOL'
      req_sujeira : perda (% do esperado) > LIMIAR_SUJEIRA
      req_custo   : perda (R$/dia) ≥ custo da limpeza
      compensa    : SUJA  e  req_custo
    """
    ultima = df.iloc[-1]
    g = ultima.get("field7")
    pv = perda_vs_esperado(df, placa["potencia"], pmax, g_min=IRRAD_MIN_JULGAMENTO)

    a = {
        "pot_atual": ultima.get(placa["potencia"]),
        "pot_esperada": pmax * max(0.0, g) / IRRADIANCIA_STC if pd.notna(g) else None,
        "e_real": pv["e_real"] if pv else 0.0,
        "e_esperada": pv["e_esperada"] if pv else 0.0,
        "perda_pct": pv["perda_pct"] if pv else 0.0,
        "perda_rs": pv["perda_rs"] if pv else 0.0,
    }

    dias = max(1, (df["timestamp"].max() - df["timestamp"].min()).days + 1)
    a["perda_dia"] = a["perda_rs"] / dias
    a["payback"] = custo_limpeza / a["perda_dia"] if a["perda_dia"] > 0 else None

    if pv is None or a["e_esperada"] < ENERGIA_MIN_JULGAMENTO:
        a["veredito"] = "SEM SOL"
    elif a["perda_pct"] > LIMIAR_SUJEIRA:
        a["veredito"] = "SUJA"
    else:
        a["veredito"] = "LIMPA"

    a["req_sujeira"] = a["perda_pct"] > LIMIAR_SUJEIRA
    a["req_custo"] = a["perda_dia"] >= custo_limpeza
    a["compensa"] = a["veredito"] == "SUJA" and a["req_custo"]
    return a

def _bloco_veredito(placa, a):
    """Cartão grande com o resultado do julgamento."""
    estilos = {
        "LIMPA":   ("#0b3b24", "#22c55e", "#bbf7d0", "✅ LIMPA"),
        "SUJA":    ("#4a1416", "#ef4444", "#fecaca", "🚨 SUJA"),
        "SEM SOL": ("#1e293b", "#64748b", "#cbd5e1", "🌙 SEM SOL"),
    }
    bg, borda, texto, rotulo = estilos[a["veredito"]]
    sub = ("irradiação baixa demais para julgar" if a["veredito"] == "SEM SOL"
           else f"gerou {a['perda_pct']:.1f}% abaixo do esperado")
    st.markdown(
        f'<div class="veredito" style="background:{bg};border-color:{borda}">'
        f'<div class="veredito-placa" style="color:{placa["cor"]}">{placa["emoji"]} {placa["nome"]}</div>'
        f'<div class="veredito-label" style="color:{texto}">{rotulo}</div>'
        f'<div class="veredito-sub">{sub}</div></div>',
        unsafe_allow_html=True,
    )

def _bloco_requisitos(a, custo_limpeza):
    """Checklist dos requisitos de limpeza com os valores medidos e a decisão final."""
    def linha(ok, texto, valor):
        icone = "🔴" if ok else "🟢"
        return (f'<div class="req-linha"><span>{icone} {texto}</span>'
                f'<span class="req-valor">{valor}</span></div>')

    sinal_suj = "&gt;" if a["req_sujeira"] else "≤"
    sinal_cus = "≥" if a["req_custo"] else "&lt;"
    linhas = (
        linha(a["req_sujeira"], "Perda acima do limiar de sujeira",
              f'{a["perda_pct"]:.1f}% {sinal_suj} {LIMIAR_SUJEIRA:.0f}%')
        + linha(a["req_custo"], "Perda por dia paga a limpeza",
                f'{_fmt_rs(a["perda_dia"])}/dia {sinal_cus} {_fmt_rs(custo_limpeza)}')
    )

    if a["veredito"] == "SEM SOL":
        dec, bg, bd = "🌙 Aguardando sol para julgar", "#1e293b", "#64748b"
    elif a["compensa"]:
        dec, bg, bd = "🧽 LIMPAR AGORA — a perda já paga a água", "#4a1416", "#ef4444"
    elif a["veredito"] == "SUJA":
        pb = f"~{a['payback']:.1f} dias" if a["payback"] else "—"
        dec, bg, bd = f"⏳ AGUARDAR — a limpeza se paga em {pb}", "#4a320b", "#f59e0b"
    else:
        dec, bg, bd = "✅ NÃO PRECISA LIMPAR", "#0b3b24", "#22c55e"

    st.markdown(
        f'<div class="req"><div class="req-titulo">Requisitos de limpeza</div>{linhas}'
        f'<div class="req-decisao" style="background:{bg};border-color:{bd};color:#f1f5f9">{dec}</div></div>',
        unsafe_allow_html=True,
    )

def _controles_limpeza(placa, agora):
    """Botões para registrar a limpeza DESTA placa — o julgamento recomeça a partir daí."""
    sufixo = placa["potencia"]
    b1, b2 = st.columns(2)
    with b1:
        if st.button("🧽 Limpei agora", use_container_width=True, key=f"btn_limpar_{sufixo}"):
            if gravar_ultima_limpeza(agora_brasil(), placa["celula"]):
                st.cache_data.clear()
                st.rerun()
    with b2:
        manual = st.checkbox("Limpei em outro horário", key=f"chk_limpar_{sufixo}")
    if manual:
        m1, m2, m3 = st.columns(3)
        with m1:
            data_l = st.date_input("Data", value=agora.date(), max_value=agora.date(), key=f"data_limpar_{sufixo}")
        with m2:
            hora_l = st.time_input("Hora", value=agora.time().replace(second=0, microsecond=0), key=f"hora_limpar_{sufixo}")
        with m3:
            st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
            if st.button("Salvar", use_container_width=True, key=f"btn_salvar_limpar_{sufixo}"):
                if gravar_ultima_limpeza(datetime.combine(data_l, hora_l), placa["celula"]):
                    st.cache_data.clear()
                    st.rerun()

def _coluna_julgamento(df, placa, a, pmax, pmax_nominal, custo_limpeza, faixa_pot, origem, agora):
    """Uma coluna completa (veredito + limpeza + números + requisitos + 1 gráfico) para UMA placa."""
    cor = placa["cor"]

    if a is None:
        st.markdown(
            f'<div class="veredito" style="background:#1e293b;border-color:#64748b">'
            f'<div class="veredito-placa" style="color:{cor}">{placa["emoji"]} {placa["nome"]}</div>'
            f'<div class="veredito-label" style="color:#cbd5e1">⏳ AGUARDANDO</div>'
            f'<div class="veredito-sub">ainda não há leituras desde {origem}</div></div>',
            unsafe_allow_html=True,
        )
        _controles_limpeza(placa, agora)
        return

    _bloco_veredito(placa, a)
    sol = df[df["field7"] >= IRRAD_MIN_JULGAMENTO]
    st.caption(f"📍 Julgando desde **{origem}** — {len(sol)} leituras com sol.")
    _controles_limpeza(placa, agora)

    c1, c2 = st.columns(2)
    with c1:
        card("Potência medida", _fmt(a["pot_atual"]), "W (agora)", cor)
    with c2:
        card("Potência esperada", _fmt(a["pot_esperada"]), "W (Pmax × fator × G/1000)", "#facc15")
    c3, c4 = st.columns(2)
    with c3:
        card("Energia gerada", _fmt(a["e_real"], 2), "Wh desde o início do julgamento", cor)
    with c4:
        card("Energia esperada", _fmt(a["e_esperada"], 2), "Wh desde o início do julgamento", "#facc15")

    # Desempenho em relação ao nominal puro — ajuda a escolher o fator
    e_nom = float((pmax_nominal * sol["field7"] / IRRADIANCIA_STC).sum())
    if e_nom > 0:
        desemp = sol[placa["potencia"]].clip(lower=0).sum() / e_nom
        st.caption(f"Desempenho observado: {desemp:.0%} do nominal ({pmax_nominal:.0f} W × G_sensor/1000).")

    _bloco_requisitos(a, custo_limpeza)

    esperada = pmax * df["field7"].clip(lower=0) / IRRADIANCIA_STC
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["timestamp"], y=df[placa["potencia"]], name="Medida",
        fill="tozeroy", fillcolor=hex_para_rgba(cor, 0.15),
        line=dict(color=cor, width=2),
    ))
    fig.add_trace(go.Scatter(
        x=df["timestamp"], y=esperada, name="Esperada",
        line=dict(color="#facc15", width=2, dash="dash"),
    ))
    fig.update_layout(**LAY, title="Potência medida x esperada (W)", yaxis_title="W", height=300)
    if faixa_pot:
        fig.update_yaxes(range=faixa_pot)
    st.plotly_chart(fig, use_container_width=True, key=f"cmp_pot_{placa['potencia']}")

def render_comparacao(custo_limpeza, pmax_nominal, fator):
    """
    Aba de julgamento: cada placa (bancada) recebe o veredito LIMPA/SUJA e a decisão
    de limpeza. Por padrão o julgamento de cada placa começa na SUA última limpeza
    registrada — limpou, registra, e o processo recomeça do zero a partir dali.
    A referência é sempre o sensor: P_esperada = Pmax × fator × G_sensor/1000.
    """
    pmax = pmax_nominal * fator
    agora = agora_brasil()
    hoje = agora.date()

    st.subheader("⚖️ Comparação — julgamento de cada placa")
    st.caption(
        "Cada placa é comparada com a potência **esperada** pelo sensor de irradiação "
        "(Pmax × fator × G/1000). O sistema decide se ela está **LIMPA** ou **SUJA** e se a "
        f"limpeza compensa. Só entram leituras com irradiação ≥ {IRRAD_MIN_JULGAMENTO:.0f} W/m²."
    )

    m1, m2 = st.columns([3, 1])
    with m1:
        modo = st.radio(
            "Julgar a partir de:",
            ["🧽 Última limpeza de cada placa", "📅 Período escolhido"],
            horizontal=True, key="cmp_modo",
        )
    with m2:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        if st.button("🔄 Atualizar", use_container_width=True, key="btn_cmp_atualizar"):
            st.cache_data.clear()
            st.rerun()

    desde_limpeza = modo.startswith("🧽")

    if not desde_limpeza:
        if "cmp_data_inicio" not in st.session_state:
            st.session_state["cmp_data_inicio"] = hoje
        if "cmp_data_fim" not in st.session_state:
            st.session_state["cmp_data_fim"] = hoje

        def _definir_periodo_hoje_cmp():
            d = agora_brasil().date()
            st.session_state["cmp_data_inicio"] = d
            st.session_state["cmp_data_fim"] = d

        p1, p2, p3 = st.columns(3)
        with p1:
            data_inicio = st.date_input("De:", key="cmp_data_inicio")
        with p2:
            data_fim = st.date_input("Até:", key="cmp_data_fim")
        with p3:
            st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
            st.button("📆 Só hoje", use_container_width=True, key="btn_cmp_hoje", on_click=_definir_periodo_hoje_cmp)
        if data_inicio > data_fim:
            st.error("A data 'De' não pode ser depois da data 'Até'.")
            return

    # 📡 Dados de cada placa: desde a última limpeza dela, ou o período escolhido
    dados = {}
    with st.spinner("Buscando dados do ThingSpeak..."):
        for placa in (PLACA_LIMPA, PLACA_SUJA):
            if desde_limpeza:
                limpeza = carregar_ultima_limpeza(placa["celula"])
                inicio = limpeza or datetime.combine(hoje, datetime.min.time())
                origem = (f"a limpeza de {inicio.strftime('%d/%m %H:%M')}" if limpeza
                          else "hoje 00:00 (nenhuma limpeza registrada)")
                df = buscar_historico_thingspeak(inicio.date(), hoje)
                if not df.empty:
                    df = df[df["timestamp"] >= inicio].reset_index(drop=True)
            else:
                origem = f"{data_inicio.strftime('%d/%m')} a {data_fim.strftime('%d/%m')}"
                df = buscar_historico_thingspeak(data_inicio, data_fim)
            if df.empty or len(df) < 2 or "field7" not in df:
                dados[placa["potencia"]] = (pd.DataFrame(), None, origem)
            else:
                dados[placa["potencia"]] = (df, _avaliar_placa(df, placa, pmax, custo_limpeza), origem)

    # 🌤️ Condições do teste (comuns às duas placas) — leitura mais recente disponível
    df_agora = buscar_historico_thingspeak(hoje, hoje) if desde_limpeza else \
        max((d[0] for d in dados.values()), key=len)
    g_agora = df_agora.iloc[-1].get("field7") if not df_agora.empty else None
    t1, t2, t3 = st.columns(3)
    with t1:
        card("Irradiação do sensor", _fmt(g_agora, 0), "W/m² (última leitura)", "#facc15")
    with t2:
        card("Potência de referência", f"{pmax:.1f}",
             f"W = {pmax_nominal:.0f} W × fator {fator:.2f}", "#67e8f9")
    with t3:
        card("Custo da limpeza", _fmt_rs(custo_limpeza), "água por limpeza", "#a78bfa")

    # Mesma escala Y nos dois gráficos (inclui a curva esperada)
    series = []
    for placa in (PLACA_LIMPA, PLACA_SUJA):
        df = dados[placa["potencia"]][0]
        if not df.empty:
            series += [df[placa["potencia"]], pmax * df["field7"].clip(lower=0) / IRRADIANCIA_STC]
    valores = pd.concat(series).dropna() if series else pd.Series(dtype=float)
    faixa_pot = [0, max(1.0, float(valores.max()) * 1.08)] if not valores.empty else None

    col_esq, col_dir = st.columns(2, gap="large")
    for col, placa in ((col_esq, PLACA_LIMPA), (col_dir, PLACA_SUJA)):
        df, a, origem = dados[placa["potencia"]]
        with col:
            _coluna_julgamento(df, placa, a, pmax, pmax_nominal, custo_limpeza, faixa_pot, origem, agora)


# ============================================================================
# 🎯 FUNÇÃO PRINCIPAL
# ============================================================================

def main():
    # Cabeçalho
    st.markdown('<h1 style="margin:0">☀️ Monitor de Placas Fotovoltaicas</h1>', unsafe_allow_html=True)
    st.markdown("**Sistema inteligente de detecção de sujeira e análise de viabilidade econômica**")
    # 🟢 SELO DE VERSÃO — se você NÃO vê este selo no app, ele está rodando um arquivo ANTIGO.
    st.markdown(
        '<div style="display:inline-block;background:#0b3b24;border:1px solid #22c55e;'
        'color:#bbf7d0;border-radius:999px;padding:4px 14px;font-size:13px;font-weight:600;'
        'margin:6px 0">🟢 versão 2.8 — julgamento desde a última limpeza de cada placa</div>',
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # Carregar dados
    df = carregar_sheets()

    # Sidebar
    with st.sidebar:
        st.title("⚙️ Configurações")
        st.markdown("---")

        st.subheader("⚡ Minha Placa")
        potencia_cliente = st.number_input(
            "Potência da minha placa (W):",
            min_value=1.0, max_value=50000.0,
            value=20.0, step=10.0
        )

        if st.button("Salvar potência na planilha", use_container_width=True):
            if gravar_potencia(potencia_cliente):
                st.success(f"✅ Potência {potencia_cliente:.0f}W salva na planilha!")
                st.cache_data.clear()
                st.rerun()

        fator_desempenho = st.slider(
            "Fator de desempenho da placa:",
            min_value=0.30, max_value=1.00, value=EFICIENCIA, step=0.01,
            help="Fração da potência nominal que a placa entrega na prática (temperatura, "
                 "carga sem MPPT, perdas). A potência esperada na aba Comparação é "
                 "Pmax × fator × G_sensor/1000.",
        )
        st.caption(f"Referência: {potencia_cliente * fator_desempenho:.1f} W a 1000 W/m²")

        st.markdown("---")

        # ============================================================================
        # 💧 CUSTO DE LIMPEZA — água utilizada (editável)
        # ============================================================================
        st.subheader("💧 Custo de Limpeza")
        st.caption("Custo da **água** usada na limpeza. Ajuste conforme sua realidade.")

        with st.expander("Ajustar água da limpeza", expanded=False):
            agua_litros    = st.number_input("Água por limpeza (L)", min_value=0.0, value=AGUA_LITROS_PADRAO, step=0.5)
            agua_preco_m3  = st.number_input("Preço da água (R$/m³)", min_value=0.0, value=AGUA_PRECO_M3_PADRAO, step=0.5, format="%.2f")

        # Custo total desta limpeza (R$), usado em toda a análise e decisão
        custo_limpeza_atual = custo_total_limpeza(agua_litros, agua_preco_m3)
        card("Custo total da limpeza", f"R$ {custo_limpeza_atual:.2f}", "por limpeza", "#a78bfa")

        st.markdown("---")

        # Filtro de período
        if not df.empty and "timestamp" in df.columns:
            st.subheader("📅 Período")
            dmin = df["timestamp"].min().date()
            dmax = df["timestamp"].max().date()
            d1 = st.date_input("De:", value=dmin, min_value=dmin, max_value=dmax)
            d2 = st.date_input("Até:", value=dmax, min_value=dmin, max_value=dmax)

        st.markdown("---")
        st.markdown("**TCC Solar**\n- Dados via API climática\n- Python + Streamlit")
        st.markdown("---")

        if st.button("🔄 Atualizar dados", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        st.caption(f"Atualizado: {datetime.now().strftime('%H:%M:%S')}")

    # 🧪 BOTÃO DE TESTE DE NOTIFICAÇÃO
    mostrar_botao_teste_notificacao()

    tab1, tab2, tab_cmp, tab3 = st.tabs(
        ["📊 Dashboard", "☀️ Minha Placa ao Vivo", "⚖️ Comparação", "📧 E-mail"]
    )

    with tab2:
        render_placa_ao_vivo()

    with tab_cmp:
        render_comparacao(custo_limpeza_atual, potencia_cliente, fator_desempenho)

    with tab3:
        render_aba_email()

    with tab1:
        # Verificar se há dados
        if df.empty:
            st.warning("⚠️ Sem dados da planilha.")
            st.stop()

        # Filtrar por período
        mask = (df["timestamp"].dt.date >= d1) & (df["timestamp"].dt.date <= d2)
        df = df[mask].copy()

        if df.empty:
            st.warning("Nenhum dado para o período selecionado.")
            st.stop()

        # Análise (usa o custo de limpeza calculado a partir da água)
        an = analisar(df, potencia_cliente, custo_limpeza_atual)
        ultima = df.iloc[-1]
        ult_an = an.iloc[-1]

        # ============================================================================
        # 🔔 VERIFICAR SE COMPENSA LIMPAR E MOSTRAR NOTIFICAÇÃO
        # ============================================================================

        if ult_an["compensa_limpar"]:
            perda = ult_an["perda_percentual"]
            perda_diaria = ult_an["perda_diaria_est"]
            msg_alerta = (f"🚨 LIMPEZA NECESSÁRIA!\n\nPerda média: R${perda_diaria:.2f}/dia — "
                          f"maior ou igual ao custo de limpeza (R${custo_limpeza_atual:.2f}). COMPENSA LIMPAR!")
            st.error(msg_alerta)
            verificar_e_enviar_alerta_email(True, msg_alerta)
        else:
            verificar_e_enviar_alerta_email(False, "")

        # Info box
        st.info(
            f"Calculando para uma placa de {potencia_cliente:.0f}W — Geração máxima esperada: "
            f"{potencia_cliente * EFICIENCIA:.1f}W em condições ideais. "
            f"Custo de limpeza considerado: R${custo_limpeza_atual:.2f}."
        )

        # Diagnóstico atual
        st.subheader("Diagnóstico Atual")
        cls = "alert" if ult_an["compensa_limpar"] else ("warn" if ult_an["indicativo_sujeira"] else "ok")
        st.markdown(f'<div class="decision-box {cls}">{ult_an["mensagem_status"]}</div>', unsafe_allow_html=True)

        # Indicadores em tempo real
        st.subheader("Indicadores em Tempo Real")
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            card("Irradiância", f"{ultima.get('irradiancia', 0):.0f}", "W/m²", "#facc15")
        with c2:
            card("Geração Prevista", f"{ult_an['geracao_prevista']:.1f}", "W", "#60a5fa")
        with c3:
            card("Geração Real", f"{ult_an['geracao_real']:.1f}", "W", "#f59e0b")
        with c4:
            cor = "#ef4444" if ult_an["perda_percentual"] > LIMIAR_SUJEIRA else "#22c55e"
            card("Perda Estimada", f"{ult_an['perda_percentual']:.1f}", "%", cor)
        with c5:
            card("Temperatura", f"{ultima.get('temp_ambiente', 0):.1f}", "°C", "#34d399")

        c6, c7, c8, c9, c10 = st.columns(5)
        with c6:
            card("Nuvens", f"{ultima.get('nuvens_pct', 0):.0f}", "%", "#94a3b8")
        with c7:
            card("Perda/Medição", f"R$ {ult_an['perda_financeira']:.4f}", "", "#f87171")
        with c8:
            card("Perda Diária", f"R$ {ult_an['perda_diaria_est']:.2f}", "média/dia", "#fb923c")
        with c9:
            card("Custo Limpeza", f"R$ {custo_limpeza_atual:.2f}", "água", "#a78bfa")
        with c10:
            payback = ult_an["dias_payback"]
            payback_txt = f"{payback:.1f}" if payback is not None else "—"
            card("Paga limpeza em", payback_txt, "dias", "#67e8f9")

        st.markdown("---")

        # Gráfico: Geração Prevista vs Real
        st.subheader("Geração Prevista vs Real")
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(
            x=df["timestamp"], y=an["geracao_prevista"],
            name="Prevista (API)", mode="lines",
            line=dict(color="#60a5fa", width=2, dash="dash")
        ))
        fig1.add_trace(go.Scatter(
            x=df["timestamp"], y=an["geracao_real"],
            name="Real (sua placa)", mode="lines",
            line=dict(color="#f59e0b", width=2)
        ))
        fig1.add_trace(go.Scatter(
            x=pd.concat([df["timestamp"], df["timestamp"][::-1]]),
            y=pd.concat([an["geracao_prevista"], an["geracao_real"][::-1]]),
            fill="toself", fillcolor="rgba(239,68,68,0.12)",
            line=dict(color="rgba(0,0,0,0)"),
            name="Área de perda", hoverinfo="skip"
        ))
        fig1.update_layout(**LAY, title=f"Geração Prevista (API) vs Real (placa {potencia_cliente:.0f}W)", yaxis_title="W")
        st.plotly_chart(fig1, use_container_width=True)

        ca, cb = st.columns(2)

        with ca:
            st.subheader("Irradiância Solar")
            fig2 = go.Figure(go.Scatter(
                x=df["timestamp"], y=df["irradiancia"],
                fill="tozeroy", fillcolor="rgba(250,204,21,0.15)",
                line=dict(color="#facc15", width=2), name="Irradiância"
            ))
            fig2.update_layout(**LAY, title="Irradiância (W/m²)", yaxis_title="W/m²")
            st.plotly_chart(fig2, use_container_width=True)

        with cb:
            st.subheader("Temperatura e Nuvens")
            fig3 = go.Figure()
            fig3.add_trace(go.Scatter(
                x=df["timestamp"], y=df["temp_ambiente"],
                name="Temperatura (°C)", mode="lines",
                line=dict(color="#34d399", width=2)
            ))
            if "nuvens_pct" in df.columns:
                fig3.add_trace(go.Bar(
                    x=df["timestamp"], y=df["nuvens_pct"],
                    name="Nuvens (%)", opacity=0.4,
                    marker_color="#94a3b8", yaxis="y2"
                ))
            # FIX: monta o layout num dicionário único ao invés de passar
            # yaxis/yaxis2 junto com **LAY (que já tem "yaxis"), o que causava
            # "got multiple values for keyword argument 'yaxis'"
            layout_temp = {**LAY, "title": "Temperatura e Nuvens"}
            layout_temp["yaxis"] = dict(title="°C", gridcolor="#1e293b", linecolor="#334155")
            layout_temp["yaxis2"] = dict(title="%", overlaying="y", side="right", gridcolor="#1e293b", linecolor="#334155")
            fig3.update_layout(**layout_temp)
            st.plotly_chart(fig3, use_container_width=True)

        # Gráfico: Perda por Sujeira
        st.subheader("Perda Estimada por Sujeira")
        fig4 = go.Figure(go.Bar(
            x=df["timestamp"], y=an["perda_percentual"],
            marker_color=["#ef4444" if v > LIMIAR_SUJEIRA else "#22c55e" for v in an["perda_percentual"]]
        ))
        fig4.add_hline(
            y=LIMIAR_SUJEIRA, line_dash="dash", line_color="#facc15",
            annotation_text=f"Limiar ({LIMIAR_SUJEIRA}%)",
            annotation_position="top right", annotation_font_color="#facc15"
        )
        fig4.update_layout(**LAY, title="Perda por Sujeira (%)", yaxis_title="%")
        st.plotly_chart(fig4, use_container_width=True)

        st.markdown("---")

        # Análise econômica
        st.subheader("Análise Econômica do Período")
        perda_kwh = an["energia_perdida_kwh"].sum()   # energia perdida real (kWh), intervalo real
        perda_r   = an["perda_financeira"].sum()       # R$ perdidos no período
        perda_dia = ult_an["perda_diaria_est"]         # R$/dia médio
        e1, e2, e3, e4 = st.columns(4)
        with e1:
            card("Energia Perdida", f"{perda_kwh:.4f}", "kWh no período")
        with e2:
            card("Perda Total", f"R$ {perda_r:.3f}", "no período")
        with e3:
            card("Perda Média", f"R$ {perda_dia:.2f}", "por dia")
        with e4:
            decisao = "SIM" if ult_an["compensa_limpar"] else "NÃO"
            cor_dec = "#ef4444" if ult_an["compensa_limpar"] else "#22c55e"
            card("Compensa Limpar?", decisao, f"custo R$ {custo_limpeza_atual:.2f}", cor_dec)

        st.markdown("---")

        # Tabela de dados
        with st.expander("📋 Ver dados da planilha"):
            st.dataframe(df.sort_values("timestamp", ascending=False), use_container_width=True)

        st.caption("TCC Solar | Python + Streamlit + Google Sheets")


# ============================================================================
# 🚀 EXECUTAR
# ============================================================================

if __name__ == "__main__":
    main()
