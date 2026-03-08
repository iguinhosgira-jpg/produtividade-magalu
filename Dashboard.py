import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials
import json

# =========================================================================
# 1. CONFIGURAÇÕES INICIAIS E CSS (AAA+)
# =========================================================================
st.set_page_config(page_title="Torre de Controle | Armazenagem", page_icon="⚡️", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #F8F9FA; }
    
    /* Cartões de KPI Modernos */
    .kpi-card {
        background-color: #FFFFFF; border-radius: 12px; padding: 20px;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.04); border-left: 5px solid #0086FF;
        transition: transform 0.2s; margin-bottom: 20px;
    }
    .kpi-card:hover { transform: translateY(-3px); box-shadow: 0 6px 15px rgba(0, 0, 0, 0.08); }
    .kpi-title { margin: 0; font-size: 12px; color: #6C757D; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }
    .kpi-value { margin: 5px 0; font-size: 32px; color: #212529; font-weight: 900; }
    .kpi-subtitle { margin: 0; font-size: 12px; color: #ADB5BD; font-weight: 500; }
    
    /* Títulos de Blocos */
    .bloco-header { color: #2C3E50; font-weight: 800; font-size: 22px; margin-top: 30px; margin-bottom: 10px; border-bottom: 2px solid #E9ECEF; padding-bottom: 5px;}
    
    /* Abas */
    .stTabs [data-baseweb="tab-list"] { gap: 20px; }
    .stTabs [data-baseweb="tab"] { font-weight: bold; font-size: 16px; padding: 15px 20px; }
    .stTabs [aria-selected="true"] { color: #0086FF !important; border-bottom: 3px solid #0086FF !important; }
</style>
""", unsafe_allow_html=True)

def exibir_kpi(titulo, valor, subtitulo="", cor="#0086FF"):
    st.markdown(f"""
    <div class="kpi-card" style="border-left-color: {cor};">
        <p class="kpi-title">{titulo}</p>
        <p class="kpi-value">{valor}</p>
        <p class="kpi-subtitle">{subtitulo}</p>
    </div>
    """, unsafe_allow_html=True)

# =========================================================================
# 2. MOTOR DE DADOS
# =========================================================================
@st.cache_data(ttl=300)
def carregar_dados():
    try:
        cred_dict = json.loads(st.secrets["google_json"])
        creds = Credentials.from_service_account_info(cred_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"])
        client = gspread.authorize(creds)
        
        sh = client.open_by_key('1F4Qs5xGPMjgWSO6giHSwFfDf5F-mlv1RuT4riEVU0I0')
        ws = sh.worksheet("ACOMPANHAMENTO GERAL")
        data = ws.get_all_values()
        
        df = pd.DataFrame(data[1:], columns=data[0])
        
        # Tratamento Básico
        df['QT_PRODUTO'] = pd.to_numeric(df['QT_PRODUTO'], errors='coerce').fillna(0)
        df['DT_CONFERENCIA'] = pd.to_datetime(df['DT_CONFERENCIA'], errors='coerce') 
        df['DT_ARMAZENAGEM'] = pd.to_datetime(df['DT_ARMAZENAGEM'], dayfirst=True, errors='coerce')
        
        df['AGENDA'] = df.iloc[:, 3].astype(str).str.strip().str.upper()
        df['FORNECEDOR'] = df.iloc[:, 9].astype(str).str.strip().str.upper()
        
        # Horas e Datas
        df['Data_Ref'] = df['DT_ARMAZENAGEM'].dt.date
        df['Hora_Conf'] = df['DT_CONFERENCIA'].dt.strftime('%H:00')
        df['Hora_Armz'] = df['DT_ARMAZENAGEM'].dt.strftime('%H:00')
        
        # SLA em Minutos (Conferência até Armazenagem)
        df['Tempo_Espera_Minutos'] = (df['DT_ARMAZENAGEM'] - df['DT_CONFERENCIA']).dt.total_seconds() / 60.0
        
        return df.dropna(subset=['Data_Ref'])
    except Exception as e:
        st.error(f"Erro na conexão com Banco de Dados: {e}")
        return pd.DataFrame()

df_bruto = carregar_dados()

if not df_bruto.empty:
    # =========================================================================
    # SIDEBAR: FILTROS
    # =========================================================================
    st.sidebar.image("https://magalog.com.br/opengraph-image.jpg?fdd536e7d35ec9da", width=250)
    st.sidebar.markdown("<br>", unsafe_allow_html=True)
    st.sidebar.markdown("### 🎛️ Filtros Globais")
    
    data_max = df_bruto['Data_Ref'].max()
    data_sel = st.sidebar.date_input("🗓️ Data da Operação", data_max)
    
    df_dia = df_bruto[df_bruto['Data_Ref'] == data_sel]
    
    opcoes_ops = ["Equipe Total"] + sorted(df_dia['OPERADOR'].dropna().astype(str).unique().tolist())
    op_sel = st.sidebar.selectbox("👤 Filtrar Operador", opcoes_ops)
    
    df = df_dia if op_sel == "Equipe Total" else df_dia[df_dia['OPERADOR'] == op_sel]

    # =========================================================================
    # CABEÇALHO DO DASHBOARD
    # =========================================================================
    st.title(f"🚀 Visão de Produtividade | {data_sel.strftime('%d/%m/%Y')}")
    st.caption("Acompanhamento de fluxo de doca, SLA e performance hora a hora.")
    
    # -------------------------------------------------------------------------
    # BLOCO 1: VISÃO EXECUTIVA (KPIs Rápidos)
    # -------------------------------------------------------------------------
    c1, c2, c3, c4 = st.columns(4)
    
    qtd_etiquetas = df['NU_ETIQUETA'].nunique()
    qtd_pecas = df['QT_PRODUTO'].sum()
    
    espera_valida = df[df['Tempo_Espera_Minutos'] > 0]['Tempo_Espera_Minutos']
    sla_medio = espera_valida.mean() if not espera_valida.empty else 0
    txt_sla = f"{int(sla_medio // 60)}h {int(sla_medio % 60)}m"
    
    horas_trabalhadas = df['Hora_Armz'].nunique()
    media_etq_hora = qtd_etiquetas / horas_trabalhadas if horas_trabalhadas > 0 else 0

    with c1: exibir_kpi("Etiquetas Guardadas", f"{qtd_etiquetas:,.0f}".replace(',','.'), "Total de pallets/volumes", "#0086FF")
    with c2: exibir_kpi("Peças Físicas", f"{qtd_pecas:,.0f}".replace(',','.'), "Volume interno", "#9B59B6")
    with c3: exibir_kpi("SLA Médio Doca", txt_sla, "Tempo médio esperando", "#F44336" if sla_medio > 120 else "#4CAF50")
    with c4: exibir_kpi("Cadência (Etq/Hora)", f"{media_etq_hora:.0f}", "Média de produtividade", "#FF9800")

    # -------------------------------------------------------------------------
    # BLOCO 2: VISÃO DO FLUXO (META VS REAL VS BACKLOG)
    # -------------------------------------------------------------------------
    st.markdown("<div class='bloco-header'>🌊 Fluxo Operacional da Doca (Backlog)</div>", unsafe_allow_html=True)
    
    # Preparando dados para ver Entrada (Conferência) e Saída (Armazenagem)
    df_in = df_dia.groupby('Hora_Conf')['NU_ETIQUETA'].nunique().reset_index(name='Liberado (Entrada)')
    df_in.rename(columns={'Hora_Conf': 'Hora'}, inplace=True)
    
    df_out = df.groupby('Hora_Armz')['NU_ETIQUETA'].nunique().reset_index(name='Guardado (Saída)')
    df_out.rename(columns={'Hora_Armz': 'Hora'}, inplace=True)
    
    # Mesclando as horas e preenchendo vazios
    df_fluxo = pd.merge(df_in, df_out, on='Hora', how='outer').fillna(0).sort_values('Hora')
    
    # Calculando o Backlog (O que entrou acumulado - O que saiu acumulado)
    df_fluxo['Acumulo_Entrada'] = df_fluxo['Liberado (Entrada)'].cumsum()
    df_fluxo['Acumulo_Saida'] = df_fluxo['Guardado (Saída)'].cumsum()
    df_fluxo['Backlog (Fila)'] = df_fluxo['Acumulo_Entrada'] - df_fluxo['Acumulo_Saida']
    # Evita backlog negativo (erro de dado retroativo)
    df_fluxo['Backlog (Fila)'] = df_fluxo['Backlog (Fila)'].apply(lambda x: x if x > 0 else 0)

    # Construindo Gráfico Misto
    fig_fluxo = go.Figure()
    # Barra Azul: O que a equipe guardou na hora
    fig_fluxo.add_trace(go.Bar(x=df_fluxo['Hora'], y=df_fluxo['Guardado (Saída)'], name='Guardado/Hora (Esforço)', marker_color='#0086FF'))
    # Barra Cinza Claro: O que a conferência liberou na hora
    fig_fluxo.add_trace(go.Bar(x=df_fluxo['Hora'], y=df_fluxo['Liberado (Entrada)'], name='Liberado/Hora (Demanda)', marker_color='#E9ECEF'))
    # Linha Vermelha: O Backlog (A Fila)
    fig_fluxo.add_trace(go.Scatter(x=df_fluxo['Hora'], y=df_fluxo['Backlog (Fila)'], name='Backlog (Fila Parada)', mode='lines+markers', line=dict(color='#E74C3C', width=3), yaxis='y2'))
    
    fig_fluxo.update_layout(
        plot_bgcolor='rgba(0,0,0,0)', 
        barmode='group',
        legend=dict(orientation="h", y=1.15, x=0.5, xanchor='center'),
        yaxis=dict(title="Volume de Etiquetas", gridcolor='#F1F3F5'),
        yaxis2=dict(title="Fila Acumulada", overlaying='y', side='right', showgrid=False),
        hovermode="x unified"
    )
    st.plotly_chart(fig_fluxo, use_container_width=True)

    # -------------------------------------------------------------------------
    # BLOCO 3: VISÃO CHÃO DE FÁBRICA (OPERADORES)
    # Só faz sentido se for "Equipe Total"
    # -------------------------------------------------------------------------
    if op_sel == "Equipe Total":
        st.markdown("<div class='bloco-header'>👥 Desempenho do Time de Armazenagem</div>", unsafe_allow_html=True)
        
        col_rank, col_heat = st.columns([4, 6])
        
        # --- TABELA DE RANKING (A corrida real) ---
        with col_rank:
            st.markdown("##### 🏆 Tabela de Líderes")
            rank_op = df.groupby('OPERADOR').agg({
                'NU_ETIQUETA': 'nunique',
                'QT_PRODUTO': 'sum',
                'Hora_Armz': 'nunique'
            }).reset_index()
            
            rank_op.columns = ['Operador', 'Etiquetas', 'Peças Físicas', 'Horas Ativas']
            rank_op['Etq/Hora'] = (rank_op['Etiquetas'] / rank_op['Horas Ativas']).round(1)
            
            # Ordenar e formatar para exibição bonita
            rank_op = rank_op.sort_values('Etiquetas', ascending=False)
            st.dataframe(rank_op[['Operador', 'Etiquetas', 'Etq/Hora']], use_container_width=True, hide_index=True, height=350)
        
        # --- HEATMAP DE PRODUTIVIDADE ---
        with col_heat:
            st.markdown("##### 🔥 Mapa de Calor: Ritmo Hora a Hora")
            
            # Agrupar dados
            df_heat = df.groupby(['OPERADOR', 'Hora_Armz'])['NU_ETIQUETA'].nunique().reset_index()
            
            # Criando o Heatmap
            fig_heat = px.density_heatmap(
                df_heat, x="Hora_Armz", y="OPERADOR", z="NU_ETIQUETA",
                color_continuous_scale="Blues", # Do branco pro azul escuro
                text_auto=True # Mostra o número dentro do quadradinho
            )
            
            # Ordenando o eixo Y para o melhor operador ficar no topo
            ordem_ops = rank_op['Operador'].tolist()[::-1]
            
            fig_heat.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                yaxis=dict(title="", categoryorder='array', categoryarray=ordem_ops),
                xaxis=dict(title="Hora da Armazenagem"),
                coloraxis_showscale=False, # Oculta a barra de cor do lado pra ficar limpo
                margin=dict(l=0, r=0, t=10, b=0)
            )
            st.plotly_chart(fig_heat, use_container_width=True)

else:
    st.error("⚠️ Não foi possível carregar os dados ou a planilha está vazia.")
