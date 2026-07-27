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
# ✅ CONFIGURAÇÃO DA PÁGINA
# ============================================================================

st.set_page_config(
    page_title="TCC Solar - Monitoramento",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# ⚙️ CONSTANTES
# ============================================================================

SHEET_ID = "19jK526ZMo0BPvZ6sW3U5O0faVK16rsejEkpyYMBZ7Ec"
CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSuKaaNCw3461krN9wiYOhL01NISccPj1VMKRx6s3NdeK1G7Lj7G7tYs7C3Tr_oLcOwMCsLhsgTHrOc/pub?output=csv"
EFICIENCIA = 0.85
IRRADIANCIA_STC = 1000.0
TARIFA_KWH = 0.75
CUSTO_LIMPEZA = 5.00
LIMIAR_SUJEIRA = 10.0
EMAIL_PADRAO = "bittoleoguio@gmail.com"

# THINGSPEAK
THINGSPEAK_WRITE_API_KEY = "YOUR_API_KEY"  # ← PREENCHER COM A CHAVE DO AMIGO

# ============================================================================
# 🎨 ESTILOS CSS
# ============================================================================

st.markdown("""<style>
.stApp{background-color:#0a0f1e}
h1{color:#facc15!important}
h2,h3{color:#e2e8f0!important}
.card{background:linear-gradient(135deg,#1e293b,#0f172a);border:1px solid #334155;border-radius:14px;padding:18px 14px;text-align:center;margin-bottom:10px}
.card-title{font-size:11px;color:#94a3b8;margin-bottom:4px;text-transform:uppercase}
.card-value{font-size:28px;font-weight:700;color:#f1f5f9}
.card-unit{font-size:11px;color:#475569;margin-top:2px}
.decision-box{border-radius:14px;padding:22px 28px;font-size:17px;font-weight:600;text-align:center;margin:8px 0 16px 0}
.ok{background:#14532d;border:2px solid #22c55e;color:#bbf7d0}
.alert{background:#7f1d1d;border:2px solid #ef4444;color:#fecaca}
.warn{background:#713f12;border:2px solid #f59e0b;color:#fef3c7}
</style>""", unsafe_allow_html=True)

# ============================================================================
# 📡 FUNÇÕES
# ============================================================================

def gravar_potencia(potencia):
    """Grava potência na planilha"""
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        if "gcp_service_account" in st.secrets:
            creds = Credentials.from_service_account_info(
                dict(st.secrets["gcp_service_account"]), scopes=scopes)
        else:
            creds = Credentials.from_service_account_file("credenciais.json", scopes=scopes)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(SHEET_ID)
        ws = sh.sheet1
        ws.update("H2", [[potencia]])
        return True
    except:
        return False

def gravar_email(email):
    """Grava e-mail na planilha (célula I2)"""
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        if "gcp_service_account" in st.secrets:
            creds = Credentials.from_service_account_info(
                dict(st.secrets["gcp_service_account"]), scopes=scopes)
        else:
            creds = Credentials.from_service_account_file("credenciais.json", scopes=scopes)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(SHEET_ID)
        ws = sh.sheet1
        ws.update("I2", [[email]])
        return True
    except:
        return False

@st.cache_data(ttl=30)
def carregar_email():
    """Lê e-mail salvo da planilha"""
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        if "gcp_service_account" in st.secrets:
            creds = Credentials.from_service_account_info(
                dict(st.secrets["gcp_service_account"]), scopes=scopes)
        else:
            creds = Credentials.from_service_account_file("credenciais.json", scopes=scopes)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(SHEET_ID)
        ws = sh.sheet1
        valor = ws.acell("I2").value
        return valor.strip() if valor else EMAIL_PADRAO
    except:
        return ""

@st.cache_data(ttl=60)
def carregar_sheets():
    """Carrega dados da planilha"""
    try:
        df = pd.read_csv(CSV_URL)
        df.columns = [c.strip() for c in df.columns]

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
            elif "comando" in cl and "limpeza" in cl:
                rename[col] = "comando_limpeza"

        df = df.rename(columns=rename)

        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
            df = df.dropna(subset=["timestamp"]).sort_values("timestamp")

        for col in ["nuvens_pct", "temp_ambiente", "irradiancia", "geracao_estimada"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", "."), errors="coerce").fillna(0)

        return df
    except:
        return pd.DataFrame()

def analisar(df, potencia_w):
    """Analisa dados"""
    rows = []
    for _, row in df.iterrows():
        irrad = row.get("irradiancia", 0)
        ger_est = row.get("geracao_estimada", 0)
        ger_prev = ger_est
        ger_real = round((irrad / IRRADIANCIA_STC) * potencia_w * EFICIENCIA, 3)

        perda = max(0, round((ger_prev - ger_real) / ger_prev * 100, 2) if ger_prev > 0 else 0)
        ind = perda > LIMIAR_SUJEIRA

        p_fin = round((ger_prev - ger_real) * 0.25 / 1000 * TARIFA_KWH, 4)
        p_dia = p_fin * 48
        comp = ind and (p_dia > CUSTO_LIMPEZA)

        if not ind:
            msg = "✅ Placa OK. Limpeza não necessária."
        elif comp:
            msg = f"🚨 Sujeira! Perda {perda:.1f}%. Perda diária R${p_dia:.2f}. COMPENSA LIMPAR."
        else:
            msg = f"⚠️ Sujeira ({perda:.1f}%). Perda R${p_dia:.2f} menor que limpeza R${CUSTO_LIMPEZA:.2f}."

        rows.append({
            "geracao_prevista": ger_prev,
            "geracao_real": round(ger_real, 3),
            "perda_percentual": perda,
            "indicativo_sujeira": ind,
            "perda_financeira": p_fin,
            "compensa_limpar": comp,
            "mensagem_status": msg
        })

    return pd.DataFrame(rows)

def card(titulo, valor, unidade="", cor="#f1f5f9"):
    """Card de métrica"""
    st.markdown(
        f'<div class="card"><div class="card-title">{titulo}</div><div class="card-value" style="color:{cor}">{valor}</div><div class="card-unit">{unidade}</div></div>',
        unsafe_allow_html=True
    )

def enviar_para_thingspeak(comando):
    """Envia sinal para Thingspeak"""
    try:
        url = "https://api.thingspeak.com/update"
        params = {"api_key": THINGSPEAK_WRITE_API_KEY, "field1": comando}
        requests.get(url, params=params, timeout=5)
        return True
    except:
        return False

def email_valido(email):
    """Valida e-mail"""
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) is not None

def enviar_email_gmail(remetente, senha, destinatario, assunto, mensagem):
    """Envia e-mail"""
    try:
        msg = MIMEText(mensagem)
        msg["Subject"] = assunto
        msg["From"] = remetente
        msg["To"] = destinatario

        with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as servidor:
            servidor.starttls()
            servidor.login(remetente, senha)
            servidor.sendmail(remetente, [destinatario], msg.as_string())
        return True
    except:
        return False

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
# 🎯 MAIN
# ============================================================================

def main():
    st.markdown('<h1 style="margin:0">☀️ Monitor de Placas Fotovoltaicas</h1>', unsafe_allow_html=True)
    st.markdown("**Sistema inteligente de detecção de sujeira e análise de viabilidade econômica**")
    st.markdown("---")

    df = carregar_sheets()

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
                st.success(f"✅ Potência {potencia_cliente:.0f}W salva!")
                st.cache_data.clear()
                st.rerun()

        st.markdown("---")

        if not df.empty and "timestamp" in df.columns:
            st.subheader("📅 Período")
            dmin = df["timestamp"].min().date()
            dmax = df["timestamp"].max().date()
            d1 = st.date_input("De:", value=dmin, min_value=dmin, max_value=dmax)
            d2 = st.date_input("Até:", value=dmax, min_value=dmin, max_value=dmax)

        st.markdown("---")

        if st.button("🔄 Atualizar dados", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        st.caption(f"Atualizado: {datetime.now().strftime('%H:%M:%S')}")

    tab1, tab2 = st.tabs(["📊 Dashboard", "📧 E-mail"])

    with tab2:
        st.subheader("📧 Alertas por e-mail")
        st.caption("Digite seu e-mail abaixo. Você receberá um alerta automático quando a limpeza compensar.")

        if "email_alerta" not in st.session_state:
            st.session_state["email_alerta"] = carregar_email()
        if "ultimo_alerta" not in st.session_state:
            st.session_state["ultimo_alerta"] = False

        email_cliente = st.text_input(
            "Seu e-mail",
            value=st.session_state["email_alerta"],
            placeholder="seuemail@exemplo.com"
        )

        if email_cliente and not email_valido(email_cliente):
            st.error("E-mail inválido.")
        elif email_cliente and email_cliente != st.session_state["email_alerta"]:
            st.session_state["email_alerta"] = email_cliente
            if gravar_email(email_cliente):
                st.cache_data.clear()
                st.success("E-mail salvo!")
        elif email_cliente:
            st.success("E-mail salvo.")

    with tab1:
        if df.empty:
            st.warning("⚠️ Sem dados da planilha.")
            st.stop()

        mask = (df["timestamp"].dt.date >= d1) & (df["timestamp"].dt.date <= d2)
        df = df[mask].copy()

        if df.empty:
            st.warning("Nenhum dado para o período selecionado.")
            st.stop()

        an = analisar(df, potencia_cliente)
        ultima = df.iloc[-1]
        ult_an = an.iloc[-1]

        # ============================================================================
        # 🔔 COMANDO LIMPEZA + THINGSPEAK
        # ============================================================================

        try:
            comando_col = None
            for col in df.columns:
                if "comando" in col.lower() and "limpeza" in col.lower():
                    comando_col = col
                    break

            if comando_col and not df.empty:
                ultimo_comando = str(df.iloc[-1].get(comando_col, "")).upper().strip()

                if ultimo_comando == "SIM":
                    perda = ult_an["perda_percentual"]
                    perda_diaria = ult_an["perda_financeira"] * 48
                    msg_alerta = f"🚨 LIMPEZA NECESSÁRIA!\n\n**Comando Manual Ativado**\n\nPerda: {perda}%. Perda diária: R${perda_diaria:.2f}."
                    st.error(msg_alerta)
                    enviar_para_thingspeak("SIM")

                    email_cliente = st.session_state.get("email_alerta", "")
                    if email_cliente and email_valido(email_cliente):
                        remetente = st.secrets.get("gmail_remetente", "") if hasattr(st, "secrets") else ""
                        senha = st.secrets.get("gmail_senha_app", "") if hasattr(st, "secrets") else ""
                        if remetente and senha and not st.session_state.get("ultimo_alerta", False):
                            enviar_email_gmail(remetente, senha, email_cliente, "TCC Solar - Limpeza recomendada", msg_alerta)
                            st.session_state["ultimo_alerta"] = True

                elif ultimo_comando == "NÃO":
                    st.success("✅ Placa OK. Limpeza não necessária.")
                    enviar_para_thingspeak("NÃO")
                    st.session_state["ultimo_alerta"] = False
                else:
                    if ult_an["compensa_limpar"]:
                        perda = ult_an["perda_percentual"]
                        perda_diaria = ult_an["perda_financeira"] * 48
                        msg_alerta = f"🚨 LIMPEZA NECESSÁRIA!\n\nPerda: {perda}%. Perda diária: R${perda_diaria:.2f}."
                        st.error(msg_alerta)
                        enviar_para_thingspeak("SIM")

                        email_cliente = st.session_state.get("email_alerta", "")
                        if email_cliente and email_valido(email_cliente):
                            remetente = st.secrets.get("gmail_remetente", "") if hasattr(st, "secrets") else ""
                            senha = st.secrets.get("gmail_senha_app", "") if hasattr(st, "secrets") else ""
                            if remetente and senha and not st.session_state.get("ultimo_alerta", False):
                                enviar_email_gmail(remetente, senha, email_cliente, "TCC Solar - Limpeza recomendada", msg_alerta)
                                st.session_state["ultimo_alerta"] = True
                    else:
                        st.success("✅ Placa OK. Limpeza não necessária.")
                        enviar_para_thingspeak("NÃO")
                        st.session_state["ultimo_alerta"] = False
            else:
                if ult_an["compensa_limpar"]:
                    perda = ult_an["perda_percentual"]
                    perda_diaria = ult_an["perda_financeira"] * 48
                    msg_alerta = f"🚨 LIMPEZA NECESSÁRIA!\n\nPerda: {perda}%. Perda diária: R${perda_diaria:.2f}."
                    st.error(msg_alerta)
                    enviar_para_thingspeak("SIM")
                else:
                    st.success("✅ Placa OK. Limpeza não necessária.")
                    enviar_para_thingspeak("NÃO")
        except:
            if ult_an["compensa_limpar"]:
                st.error(f"🚨 LIMPEZA NECESSÁRIA!")
                enviar_para_thingspeak("SIM")
            else:
                st.success("✅ Placa OK.")
                enviar_para_thingspeak("NÃO")

        st.info(f"Calculando para placa de {potencia_cliente:.0f}W")

        st.subheader("Diagnóstico Atual")
        cls = "alert" if ult_an["compensa_limpar"] else ("warn" if ult_an["indicativo_sujeira"] else "ok")
        st.markdown(f'<div class="decision-box {cls}">{ult_an["mensagem_status"]}</div>', unsafe_allow_html=True)

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

        st.markdown("---")

        st.subheader("Geração Prevista vs Real")
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(x=df["timestamp"], y=an["geracao_prevista"], name="Prevista", line=dict(color="#60a5fa", width=2, dash="dash")))
        fig1.add_trace(go.Scatter(x=df["timestamp"], y=an["geracao_real"], name="Real", line=dict(color="#f59e0b", width=2)))
        fig1.update_layout(**LAY, title="Geração (W)", yaxis_title="W")
        st.plotly_chart(fig1, use_container_width=True)

        st.subheader("Perda por Sujeira")
        fig4 = go.Figure(go.Bar(x=df["timestamp"], y=an["perda_percentual"], marker_color=["#ef4444" if v > LIMIAR_SUJEIRA else "#22c55e" for v in an["perda_percentual"]]))
        fig4.update_layout(**LAY, title="Perda por Sujeira (%)", yaxis_title="%")
        st.plotly_chart(fig4, use_container_width=True)

        st.markdown("---")

        with st.expander("📋 Ver dados da planilha"):
            st.dataframe(df.sort_values("timestamp", ascending=False), use_container_width=True)

        st.caption("TCC Solar | Python + Streamlit + Google Sheets + Thingspeak")

if __name__ == "__main__":
    main()
