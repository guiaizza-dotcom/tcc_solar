import sqlite3
import os
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'dados', 'solar.db')

st.set_page_config(
    page_title="Monitor Solar — TCC",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stApp { background-color: #0f172a; }
    h1 { color: #facc15 !important; }
    h2, h3 { color: #e2e8f0 !important; }
    .card {
        background: linear-gradient(135deg, #1e293b, #0f172a);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        margin-bottom: 10px;
    }
    .card-title { font-size: 13px; color: #94a3b8; margin-bottom: 6px; }
    .card-value { font-size: 28px; font-weight: bold; color: #f1f5f9; }
    .card-unit  { font-size: 13px; color: #64748b; }
    .decision-box {
        border-radius: 14px;
        padding: 24px 28px;
        font-size: 18px;
        font-weight: bold;
        text-align: center;
        margin: 10px 0;
    }
    .decision-ok    { background: #14532d; border: 2px solid #22c55e; color: #bbf7d0; }
    .decision-alert { background: #7f1d1d; border: 2px solid #ef4444; color: #fecaca; }
    .decision-warn  { background: #713f12; border: 2px solid #f59e0b; color: #fef3c7; }
</style>
""", unsafe_allow_html=True)

CORES = {
    'limpa':    '#22c55e',
    'suja':     '#f59e0b',
    'prevista': '#60a5fa',
    'perda':    '#ef4444',
    'irrad':    '#facc15',
}

LAYOUT_BASE = dict(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(color='#e2e8f0', size=12),
    legend=dict(bgcolor='rgba(0,0,0,0)', bordercolor='#334155', borderwidth=1),
    margin=dict(l=20, r=20, t=40, b=20),
    xaxis=dict(gridcolor='#1e293b', linecolor='#334155'),
    yaxis=dict(gridcolor='#1e293b', linecolor='#334155'),
)

@st.cache_data(ttl=30)
def carregar_medicoes():
    try:
        conn = sqlite3.connect(DB_PATH)
        df   = pd.read_sql_query("SELECT * FROM medicoes ORDER BY timestamp DESC", conn)
        conn.close()
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    except Exception as e:
        st.error(f"Erro ao carregar medições: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=30)
def carregar_analises():
    try:
        conn = sqlite3.connect(DB_PATH)
        df   = pd.read_sql_query("SELECT * FROM analise_limpeza ORDER BY timestamp DESC", conn)
        conn.close()
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    except Exception as e:
        st.error(f"Erro ao carregar análises: {e}")
        return pd.DataFrame()

def card(titulo, valor, unidade=''):
    st.markdown(f"""
    <div class="card">
        <div class="card-title">{titulo}</div>
        <div class="card-value">{valor}</div>
        <div class="card-unit">{unidade}</div>
    </div>
    """, unsafe_allow_html=True)

def caixa_decisao(mensagem, compensa, indicativo):
    if not indicativo:
        classe = "decision-ok"
    elif compensa:
        classe = "decision-alert"
    else:
        classe = "decision-warn"
    st.markdown(f'<div class="decision-box {classe}">{mensagem}</div>', unsafe_allow_html=True)

def grafico_potencia(df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['potencia_limpa'],
        name='Placa Limpa', mode='lines', line=dict(color=CORES['limpa'], width=2)))
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['potencia_suja'],
        name='Placa Suja', mode='lines', line=dict(color=CORES['suja'], width=2)))
    fig.update_layout(**LAYOUT_BASE, title='Potência Gerada — Placa Limpa vs Suja (W)',
        yaxis_title='Potência (W)', xaxis_title='Data/Hora', hovermode='x unified')
    return fig

def grafico_geracao(df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['geracao_prevista'],
        name='Prevista', mode='lines', line=dict(color=CORES['prevista'], width=2, dash='dash')))
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['geracao_real'],
        name='Real', mode='lines', line=dict(color=CORES['suja'], width=2)))
    fig.add_trace(go.Scatter(
        x=pd.concat([df['timestamp'], df['timestamp'][::-1]]),
        y=pd.concat([df['geracao_prevista'], df['geracao_real'][::-1]]),
        fill='toself', fillcolor='rgba(239,68,68,0.15)',
        line=dict(color='rgba(0,0,0,0)'), name='Área de Perda', hoverinfo='skip'))
    fig.update_layout(**LAYOUT_BASE, title='Geração Prevista vs Real (W)',
        yaxis_title='Potência (W)', xaxis_title='Data/Hora', hovermode='x unified')
    return fig

def grafico_perda(df):
    cores = [CORES['perda'] if v > 10 else CORES['limpa'] for v in df['perda_percentual']]
    fig   = go.Figure(go.Bar(x=df['timestamp'], y=df['perda_percentual'],
        marker_color=cores, name='Perda (%)'))
    fig.add_hline(y=10, line_dash='dash', line_color='#facc15',
        annotation_text='Limiar de sujeira (10%)', annotation_position='top right',
        annotation_font_color='#facc15')
    fig.update_layout(**LAYOUT_BASE, title='Perda Percentual por Sujeira (%)',
        yaxis_title='Perda (%)', xaxis_title='Data/Hora')
    return fig

def grafico_irradiancia(df):
    fig = go.Figure(go.Scatter(x=df['timestamp'], y=df['irradiancia'],
        fill='tozeroy', fillcolor='rgba(250,204,21,0.2)',
        line=dict(color=CORES['irrad'], width=2), name='Irradiância'))
    fig.update_layout(**LAYOUT_BASE, title='Irradiância Solar (W/m²)',
        yaxis_title='W/m²', xaxis_title='Data/Hora')
    return fig

def grafico_temperatura(df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['temp_ambiente'],
        name='Ambiente', mode='lines', line=dict(color='#94a3b8', width=1, dash='dot')))
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['temp_placa_limpa'],
        name='Placa Limpa', mode='lines', line=dict(color=CORES['limpa'], width=2)))
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['temp_placa_suja'],
        name='Placa Suja', mode='lines', line=dict(color=CORES['suja'], width=2)))
    fig.update_layout(**LAYOUT_BASE, title='Temperatura (°C)',
        yaxis_title='Temperatura (°C)', xaxis_title='Data/Hora', hovermode='x unified')
    return fig

def main():
    st.title("☀️ Monitor de Placas Fotovoltaicas")
    st.markdown("**Sistema inteligente de detecção de sujeira e análise de viabilidade econômica**")
    st.markdown("---")

    df_med = carregar_medicoes()
    df_ana = carregar_analises()

    with st.sidebar:
        st.title("⚙️ Configurações")
        st.markdown("---")
        st.subheader("📅 Filtrar Período")

        if not df_med.empty:
            data_min = df_med['timestamp'].min().date()
            data_max = df_med['timestamp'].max().date()
            data_ini = st.date_input("De:", value=data_min, min_value=data_min, max_value=data_max)
            data_fim = st.date_input("Até:", value=data_max, min_value=data_min, max_value=data_max)

        st.markdown("---")
        st.subheader("ℹ️ Sobre o Projeto")
        st.markdown("""
        **TCC — Detecção de Sujeira em Placas Fotovoltaicas**
        - 2 Placas de 20W
        - Monitoramento contínuo
        - Análise econômica automática
        """)
        st.markdown("---")
        if st.button("🔄 Atualizar Dados", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        st.caption(f"Última atualização: {datetime.now().strftime('%H:%M:%S')}")

    if df_med.empty or df_ana.empty:
        st.warning("Banco de dados vazio. Execute inserir_dados_teste.py primeiro.")
        st.stop()

    mask_med = (df_med['timestamp'].dt.date >= data_ini) & (df_med['timestamp'].dt.date <= data_fim)
    mask_ana = (df_ana['timestamp'].dt.date >= data_ini) & (df_ana['timestamp'].dt.date <= data_fim)
    df_med_f = df_med[mask_med].copy()
    df_ana_f = df_ana[mask_ana].copy()

    if df_med_f.empty:
        st.warning("Nenhum dado para o período selecionado.")
        st.stop()

    ultima_med = df_med_f.iloc[0]
    ultima_ana = df_ana_f.iloc[0]

    st.subheader("🧠 Diagnóstico Atual")
    caixa_decisao(ultima_ana['mensagem_status'], int(ultima_ana['compensa_limpar']), int(ultima_ana['indicativo_sujeira']))
    st.markdown("---")

    st.subheader("📊 Indicadores em Tempo Real")
    col1, col2, col3, col4 = st.columns(4)
    with col1: card("⚡ Potência — Placa Limpa", f"{ultima_med['potencia_limpa']:.2f}", "W")
    with col2: card("⚡ Potência — Placa Suja",  f"{ultima_med['potencia_suja']:.2f}",  "W")
    with col3: card("📉 Perda por Sujeira",       f"{ultima_ana['perda_percentual']:.1f}", "%")
    with col4: card("☀️ Irradiância",             f"{ultima_med['irradiancia']:.0f}", "W/m²")

    st.markdown("")
    col5, col6, col7, col8 = st.columns(4)
    with col5: card("🌡️ Temp. Ambiente",     f"{ultima_med['temp_ambiente']:.1f}",    "°C")
    with col6: card("🌡️ Temp. Placa Limpa", f"{ultima_med['temp_placa_limpa']:.1f}", "°C")
    with col7: card("🌡️ Temp. Placa Suja",  f"{ultima_med['temp_placa_suja']:.1f}",  "°C")
    with col8: card("💰 Perda Diária Est.", f"R$ {ultima_ana['perda_financeira']*48:.2f}", "estimada")

    st.markdown("---")

    df_med_graf = df_med_f.sort_values('timestamp')
    df_ana_graf = df_ana_f.sort_values('timestamp')

    st.subheader("📈 Comparação de Potência")
    st.plotly_chart(grafico_potencia(df_med_graf), use_container_width=True)

    st.subheader("🎯 Geração Prevista vs Real")
    st.caption("A área vermelha representa a energia perdida por sujeira.")
    st.plotly_chart(grafico_geracao(df_ana_graf), use_container_width=True)

    st.subheader("📉 Evolução da Perda por Sujeira")
    st.plotly_chart(grafico_perda(df_ana_graf), use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("🌞 Irradiância Solar")
        st.plotly_chart(grafico_irradiancia(df_med_graf), use_container_width=True)
    with col_b:
        st.subheader("🌡️ Temperatura")
        st.plotly_chart(grafico_temperatura(df_med_graf), use_container_width=True)

    st.markdown("---")
    st.subheader("💰 Análise Econômica do Período")
    perda_total_kwh = (df_ana_graf['geracao_prevista'] - df_ana_graf['geracao_real']).sum() * 0.25 / 1000
    perda_total_r   = df_ana_graf['perda_financeira'].sum()
    custo_limpeza   = df_ana_graf['custo_limpeza'].iloc[0]
    qtd_alertas     = df_ana_graf['indicativo_sujeira'].sum()
    qtd_limpezas    = df_ana_graf['compensa_limpar'].sum()

    col_e1, col_e2, col_e3, col_e4 = st.columns(4)
    with col_e1: card("🔋 Energia Perdida",        f"{perda_total_kwh:.4f}", "kWh")
    with col_e2: card("💸 Perda Financeira Total", f"R$ {perda_total_r:.2f}", "no período")
    with col_e3: card("⚠️ Alertas de Sujeira",     f"{int(qtd_alertas)}", "leituras")
    with col_e4: card("🧹 Limpezas Recomendadas",  f"{int(qtd_limpezas)}", "ocorrências")

    st.markdown("---")
    with st.expander("📋 Ver Dados Brutos — Medições"):
        st.dataframe(df_med_f.sort_values('timestamp', ascending=False).head(100), use_container_width=True)
    with st.expander("📋 Ver Dados Brutos — Análise de Limpeza"):
        st.dataframe(df_ana_f.sort_values('timestamp', ascending=False).head(100), use_container_width=True)

    st.markdown("---")
    st.caption("🎓 TCC — Sistema Inteligente de Detecção de Sujeira em Placas Fotovoltaicas | Python + Streamlit + SQLite")

if __name__ == '__main__':
    main()