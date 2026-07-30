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
CUSTO_LIMPEZA = 5.00
LIMIAR_SUJEIRA = 10.0
EMAIL_ALERTA_PADRAO = "bittoleoguio@gmail.com"  # usado só se a planilha ainda não tiver e-mail salvo

# --- ThingSpeak (Minha Placa ao Vivo) ---
THINGSPEAK_CHANNEL_ID = "3337625"
THINGSPEAK_READ_API_KEY = "I7LHJFAFLIN4J5HJ"
THINGSPEAK_FIELD_IRRADIANCIA = 7  # Field 7 = Irradiação

# ============================================================================
# 🎨 ESTILOS CSS
# ============================================================================

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&display=swap');

html, body, [class*="css"], .stMarkdown, p, span, label { font-family:'Inter',sans-serif; }

/* 🌇 Fundo: céu ao entardecer com um brilho de sol no canto — o painel "olha" pro céu */
.stApp{
    background:
        radial-gradient(ellipse 900px 520px at 88% -6%, rgba(250,204,21,0.20), transparent 60%),
        linear-gradient(180deg,#071B2E 0%,#0B3D5C 32%,#0E4C6E 58%,#071B2E 100%);
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

def gravar_email_alerta(email):
    """Grava o e-mail de alerta na planilha do Google Sheets (célula I2), para persistir entre sessões."""
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
        ws.update("I2", [[email]])
        return True
    except Exception as e:
        st.error(f"Erro ao gravar e-mail na planilha: {e}")
        return False

@st.cache_data(ttl=30)
def carregar_email_alerta():
    """Lê o e-mail de alerta salvo na planilha (célula I2). Retorna string vazia se não houver."""
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
        return valor.strip() if valor else EMAIL_ALERTA_PADRAO
    except Exception:
        return ""

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

def agora_brasil():
    """Retorna o datetime atual no horário de Brasília (UTC-3), não importa o fuso do servidor."""
    return datetime.utcnow() - pd.Timedelta(hours=3)

@st.cache_data(ttl=60)
def buscar_historico_thingspeak(data_inicio, data_fim):
    """
    Busca o histórico do ThingSpeak entre duas datas (inclusive), já no horário de
    Brasília (UTC-3). O ThingSpeak grava tudo em UTC, então:
      1) convertemos o período pedido (horário local) para UTC antes de consultar a API;
      2) convertemos cada timestamp recebido de volta para horário local antes de devolver.
    Sem isso, uma leitura feita às 22h de um dia no Brasil chega marcada como
    01h do dia seguinte em UTC — e "hoje" na tela virava "amanhã".
    Pagina automaticamente porque o ThingSpeak limita 8000 registros por chamada.
    """
    url = f"https://api.thingspeak.com/channels/{THINGSPEAK_CHANNEL_ID}/feeds.json"
    todos_registros = []

    # Período pedido é local (Brasil) -> converte para UTC para consultar a API
    inicio_utc = datetime.combine(data_inicio, datetime.min.time()) + pd.Timedelta(hours=3)
    fim_utc = datetime.combine(data_fim, datetime.max.time()) + pd.Timedelta(hours=3)
    inicio_atual = inicio_utc

    while inicio_atual <= fim_utc:
        params = {
            "api_key": THINGSPEAK_READ_API_KEY,
            "start": inicio_atual.strftime("%Y-%m-%d %H:%M:%S"),
            "end": fim_utc.strftime("%Y-%m-%d %H:%M:%S"),
            "results": 8000,
        }
        try:
            resp = requests.get(url, params=params, timeout=20)
            resp.raise_for_status()
            feeds = resp.json().get("feeds", [])
        except Exception as e:
            st.error(f"Erro ao buscar histórico do ThingSpeak: {e}")
            break

        if not feeds:
            break

        for f in feeds:
            ts_utc = pd.to_datetime(f.get("created_at"), utc=True)
            ts_local = ts_utc.tz_convert(None) - pd.Timedelta(hours=3) if pd.notna(ts_utc) else pd.NaT
            registro = {"timestamp": ts_local}
            for campo in THINGSPEAK_CAMPOS:
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

def analisar(df, potencia_w):
    """Analisa os dados e calcula se compensa limpar"""
    rows = []
    for _, row in df.iterrows():
        irrad = row.get("irradiancia", 0)
        ger_est = row.get("geracao_estimada", 0)
        ger_prev = ger_est
        ger_real = round((irrad / IRRADIANCIA_STC) * potencia_w * EFICIENCIA, 3)

        # Calcular perda percentual
        perda = max(0, round((ger_prev - ger_real) / ger_prev * 100, 2) if ger_prev > 0 else 0)
        ind = perda > LIMIAR_SUJEIRA

        # Perda financeira
        p_fin = round((ger_prev - ger_real) * 0.25 / 1000 * TARIFA_KWH, 4)
        p_dia = p_fin * 48
        comp = ind and (p_dia > CUSTO_LIMPEZA)

        # Mensagem de status
        if not ind:
            msg = "✅ Placa OK. Limpeza não necessária."
        elif comp:
            msg = f"🚨 Sujeira! Perda {perda:.1f}%. Perda diária R${p_dia:.2f}. COMPENSA LIMPAR."
        else:
            msg = f"⚠️ Sujeira ({perda:.1f}%). Perda R${p_dia:.2f} menor que limpeza R${CUSTO_LIMPEZA:.2f}. Aguardar."

        rows.append({
            "geracao_prevista": ger_prev,
            "geracao_real": round(ger_real, 3),
            "perda_percentual": perda,
            "indicativo_sujeira": ind,
            "perda_financeira": p_fin,
            "custo_limpeza": CUSTO_LIMPEZA,
            "compensa_limpar": comp,
            "mensagem_status": msg
        })

    return pd.DataFrame(rows)

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

def enviar_email_gmail(remetente: str, senha_app: str, destinatario: str, assunto: str, mensagem: str):
    """Envia e-mail via Gmail SMTP. Retorna (sucesso: bool, detalhe: str)."""
    try:
        msg = MIMEText(mensagem)
        msg["Subject"] = assunto
        msg["From"] = remetente
        msg["To"] = destinatario

        with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as servidor:
            servidor.starttls()
            servidor.login(remetente, senha_app)
            servidor.sendmail(remetente, [destinatario], msg.as_string())
        return True, "OK"
    except smtplib.SMTPAuthenticationError:
        return False, "Falha de autenticação — confira o e-mail e a Senha de app do Gmail (configurados em secrets.toml)."
    except Exception as e:
        return False, f"Falha ao enviar: {e}"

def render_aba_email():
    """
    Aba onde o cliente final só digita o e-mail dele (sem nenhum cadastro).
    O e-mail é salvo na planilha do Google Sheets (persiste entre sessões e
    reinicializações do app). A partir daí, o app envia automaticamente um
    alerta por e-mail sempre que detectar que compensa limpar a placa.
    """
    st.subheader("📧 Alertas por e-mail")
    st.caption(
        "Digite seu e-mail abaixo. Sempre que o sistema detectar que a limpeza da "
        "placa compensa financeiramente, você recebe um alerta automático — não é "
        "preciso nenhum cadastro."
    )

    if "email_alerta" not in st.session_state:
        st.session_state["email_alerta"] = carregar_email_alerta()
    if "ultimo_alerta_enviado" not in st.session_state:
        st.session_state["ultimo_alerta_enviado"] = False

    email_cliente = st.text_input(
        "Seu e-mail",
        value=st.session_state["email_alerta"],
        placeholder="seuemail@exemplo.com",
    )

    if email_cliente and not email_valido(email_cliente):
        st.error("Informe um e-mail válido.")
    elif email_cliente and email_cliente != st.session_state["email_alerta"]:
        st.session_state["email_alerta"] = email_cliente
        if gravar_email_alerta(email_cliente):
            st.cache_data.clear()
            st.success("E-mail salvo! Você receberá um alerta automático quando compensar limpar a placa.")
    elif email_cliente:
        st.success("E-mail salvo. Você receberá um alerta automático quando compensar limpar a placa.")

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
        if not email_cliente or not email_valido(email_cliente):
            st.error("Digite um e-mail válido no campo acima antes de testar.")
        elif not remetente or not senha_app:
            st.error("Não é possível testar: credenciais do Gmail não configuradas nos Secrets.")
        else:
            with st.spinner("Enviando e-mail de teste..."):
                sucesso, detalhe = enviar_email_gmail(
                    remetente, senha_app, email_cliente,
                    "TCC Solar - Teste de notificação",
                    "Esta é uma mensagem de teste enviada manualmente pela aba de e-mail do TCC Solar.",
                )
            if sucesso:
                st.success("✅ E-mail de teste enviado! Confira a caixa de entrada (e o Spam) em alguns segundos.")
            else:
                st.error(f"❌ Falha ao enviar: {detalhe}")

def verificar_e_enviar_alerta_email(compensa_limpar: bool, mensagem_alerta: str):
    """
    Chamada a cada carregamento da página: se 'compensa_limpar' for True e houver um
    e-mail salvo na sessão, envia o alerta automaticamente (uma vez só por ocorrência,
    evitando reenviar a cada atualização da página).
    """
    email_cliente = st.session_state.get("email_alerta", "")
    if not email_cliente:
        email_cliente = carregar_email_alerta()
        st.session_state["email_alerta"] = email_cliente
    if not email_cliente or not email_valido(email_cliente):
        return

    remetente = st.secrets.get("gmail_remetente", "") if hasattr(st, "secrets") else ""
    senha_app = st.secrets.get("gmail_senha_app", "") if hasattr(st, "secrets") else ""
    if not remetente or not senha_app:
        return  # credenciais não configuradas em secrets.toml — nada a fazer

    if compensa_limpar and not st.session_state.get("ultimo_alerta_enviado", False):
        sucesso, _ = enviar_email_gmail(
            remetente, senha_app, email_cliente,
            "TCC Solar - Limpeza da placa recomendada",
            mensagem_alerta,
        )
        st.session_state["ultimo_alerta_enviado"] = True
        if sucesso:
            st.toast("📧 Alerta enviado por e-mail!")
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
# 🎯 FUNÇÃO PRINCIPAL
# ============================================================================

def main():
    # Cabeçalho
    st.markdown('<h1 style="margin:0">☀️ Monitor de Placas Fotovoltaicas</h1>', unsafe_allow_html=True)
    st.markdown("**Sistema inteligente de detecção de sujeira e análise de viabilidade econômica**")
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

    tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "☀️ Minha Placa ao Vivo", "📧 E-mail"])

    with tab2:
        render_placa_ao_vivo()

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

        # Análise
        an = analisar(df, potencia_cliente)
        ultima = df.iloc[-1]
        ult_an = an.iloc[-1]

        # ============================================================================
        # 🔔 VERIFICAR SE COMPENSA LIMPAR E MOSTRAR NOTIFICAÇÃO
        # ============================================================================

        if ult_an["compensa_limpar"]:
            perda = ult_an["perda_percentual"]
            perda_diaria = ult_an["perda_financeira"] * 48
            msg_alerta = f"🚨 LIMPEZA NECESSÁRIA!\n\nPerda detectada: {perda}%. Perda diária: R${perda_diaria:.2f}. COMPENSA LIMPAR!"
            st.error(msg_alerta)
            verificar_e_enviar_alerta_email(True, msg_alerta)
        else:
            verificar_e_enviar_alerta_email(False, "")

        # Info box
        st.info(f"Calculando para uma placa de {potencia_cliente:.0f}W — Geração máxima esperada: {potencia_cliente * EFICIENCIA:.1f}W em condições ideais")

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
            card("Perda Diária", f"R$ {ult_an['perda_financeira']*48:.2f}", "estimada", "#fb923c")
        with c9:
            card("Custo Limpeza", f"R$ {CUSTO_LIMPEZA:.2f}", "", "#a78bfa")
        with c10:
            card("Registros", f"{len(df)}", "no período", "#67e8f9")

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
        perda_kwh = ((an["geracao_prevista"] - an["geracao_real"]) * 0.25 / 1000).sum()
        perda_r = an["perda_financeira"].sum()
        e1, e2, e3, e4 = st.columns(4)
        with e1:
            card("Energia Perdida", f"{perda_kwh:.4f}", "kWh")
        with e2:
            card("Perda Total", f"R$ {perda_r:.3f}", "no período")
        with e3:
            card("Alertas Sujeira", f"{int(an['indicativo_sujeira'].sum())}", "leituras")
        with e4:
            card("Limpezas Recom.", f"{int(an['compensa_limpar'].sum())}", "ocorrências")

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
