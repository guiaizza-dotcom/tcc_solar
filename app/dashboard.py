# ============================================================================
# 🌞 TCC SOLAR - DETECÇÃO DE SUJEIRA EM PLACAS FOTOVOLTAICAS
# ============================================================================

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

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
<meta name="theme-color" content="#FFA500">
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
# 🔔 FUNÇÃO DE NOTIFICAÇÃO
# ============================================================================

def enviar_notificacao_limpeza(perda, perda_diaria):
    """Envia notificação de limpeza necessária via JavaScript"""
    notification_html = f"""
    <script>
    // Verificar se o navegador suporta notificações
    if ("Notification" in window) {{
        // Se o usuário já deu permissão, enviar notificação
        if (Notification.permission === "granted") {{
            new Notification("🚨 LIMPEZA NECESSÁRIA!", {{
                body: "Perda detectada: {perda}%. Perda diária: R${perda_diaria:.2f}. COMPENSA LIMPAR!",
                icon: "https://raw.githubusercontent.com/guiaizza-dotcom/tcc_solar/main/app/icon.png",
                badge: "https://raw.githubusercontent.com/guiaizza-dotcom/tcc_solar/main/app/icon.png",
                tag: "limpeza-necessaria"
            }});
        }} else if (Notification.permission !== "denied") {{
            // Caso contrário, pedir permissão
            Notification.requestPermission().then(permission => {{
                if (permission === "granted") {{
                    new Notification("🚨 LIMPEZA NECESSÁRIA!", {{
                        body: "Perda detectada: {perda}%. Perda diária: R${perda_diaria:.2f}. COMPENSA LIMPAR!",
                        icon: "https://raw.githubusercontent.com/guiaizza-dotcom/tcc_solar/main/app/icon.png",
                        badge: "https://raw.githubusercontent.com/guiaizza-dotcom/tcc_solar/main/app/icon.png",
                        tag: "limpeza-necessaria"
                    }});
                }}
            }});
        }}
    }}
    </script>
    """
    st.markdown(notification_html, unsafe_allow_html=True)

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
    # 🔔 VERIFICAR SE COMPENSA LIMPAR E ENVIAR NOTIFICAÇÃO
    # ============================================================================
    
    if ult_an["compensa_limpar"]:
        perda = ult_an["perda_percentual"]
        perda_diaria = ult_an["perda_financeira"] * 48
        enviar_notificacao_limpeza(perda, perda_diaria)

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
        fig3.update_layout(
            **LAY, title="Temperatura e Nuvens",
            yaxis=dict(title="°C", gridcolor="#1e293b", linecolor="#334155"),
            yaxis2=dict(title="%", overlaying="y", side="right", gridcolor="#1e293b", linecolor="#334155")
        )
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
