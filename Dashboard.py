import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials
import os

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Produtividade Inbound | CD2900", page_icon="📊", layout="wide")

# --- ESTILO CSS ---
st.markdown("""
<style>
    .stApp { background-color: #F4F7F6; }
    .kpi-card {
        background-color: #FFFFFF; border-radius: 12px; padding: 20px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05); border-left: 6px solid #0086FF;
    }
</style>
""", unsafe_allow_html=True)

def exibir_kpi(titulo, valor, subtitulo="", cor="#0086FF"):
    st.markdown(f"""
    <div class="kpi-card" style="border-left-color: {cor};">
        <p style="margin: 0; font-size: 13px; color: #7F8C8D; font-weight: 600;">{titulo.upper()}</p>
        <h2 style="margin: 5px 0; font-size: 30px; color: #2C3E50;">{valor}</h2>
        <p style="margin: 0; font-size: 12px; color: #95A5A6;">{subtitulo}</p>
    </div>
    """, unsafe_allow_html=True)

# --- CARREGAMENTO DE DADOS ---
@st.cache_data(ttl=300)
def carregar_dados_produtividade():
    try:
        diretorio_atual = os.path.dirname(os.path.abspath(__file__))
        caminho_credencial = os.path.join(diretorio_atual, 'credential_key.json')
        
        creds = Credentials.from_service_account_file(
            caminho_credencial, 
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        client = gspread.authorize(creds)
        
        sh = client.open_by_key('1F4Qs5xGPMjgWSO6giHSwFfDf5F-mlv1RuT4riEVU0I0')
        ws = sh.worksheet("ACOMPANHAMENTO GERAL")
        data = ws.get_all_values()
        
        df = pd.DataFrame(data[1:], columns=data[0])
        
        # --- TRATAMENTO DE COLUNAS ---
        df['QT_PRODUTO'] = pd.to_numeric(df['QT_PRODUTO'], errors='coerce').fillna(0)
        
        # Correção dos Formatos de Data
        df['DT_CONFERENCIA'] = pd.to_datetime(df['DT_CONFERENCIA'], errors='coerce') 
        df['DT_ARMAZENAGEM'] = pd.to_datetime(df['DT_ARMAZENAGEM'], dayfirst=True, errors='coerce')
        
        df['Hora_Conf'] = df['DT_CONFERENCIA'].dt.strftime('%H:00')
        df['Hora_Armz'] = df['DT_ARMAZENAGEM'].dt.strftime('%H:00')
        df['Data_Ref'] = df['DT_ARMAZENAGEM'].dt.date
        
        # SLA Doca
        df['Tempo_Espera_Minutos'] = (df['DT_ARMAZENAGEM'] - df['DT_CONFERENCIA']).dt.total_seconds() / 60.0
        
        # 🚀 NOVO: CLASSIFICAÇÃO DA ÁREA (Lendo a Coluna F)
        # O Pandas começa a contar do 0. Então: A=0, B=1, C=2, D=3, E=4, F=5.
        nome_coluna_f = df.columns[5]
        
        def mapear_area(endereco):
            end_str = str(endereco).strip().upper()
            if end_str.startswith('G'): return 'Blocado'
            elif end_str.startswith('P'): return 'Porta Pallet'
            elif end_str.startswith('M'): return 'Mezanino'
            elif end_str.startswith('C'): return 'Cofre'
            else: return 'Outros'
            
        df['Tipo_Area'] = df[nome_coluna_f].apply(mapear_area)
        
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados do Google Sheets: {e}")
        return pd.DataFrame()

df = carregar_dados_produtividade()
df = df.dropna(subset=['Data_Ref'])

if not df.empty:
    # --- FILTROS NA SIDEBAR ---
    st.sidebar.image("https://magalog.com.br/opengraph-image.jpg?fdd536e7d35ec9da", width=200)
    st.sidebar.title("Filtros")
    
    data_maxima = df['Data_Ref'].max()
    data_sel = st.sidebar.date_input("Data da Operação", value=data_maxima)
    
    opcoes_operadores = ["Todos"] + sorted(df['OPERADOR'].astype(str).unique().tolist())
    operador_sel = st.sidebar.selectbox("Selecionar Operador", opcoes_operadores)
    
    df_dia = df[df['Data_Ref'] == data_sel]
    
    if operador_sel != "Todos":
        df_final = df_dia[df_dia['OPERADOR'] == operador_sel]
    else:
        df_final = df_dia

    # --- KPIs ---
    st.title(f"🚀 Produtividade de Armazenagem - {data_sel.strftime('%d/%m/%Y')}")
    
    c1, c2, c3, c4, c5 = st.columns(5)
    
    total_etq = df_final['NU_ETIQUETA'].nunique()
    total_pcs = df_final['QT_PRODUTO'].sum()
    horas_ativas = df_final['Hora_Armz'].nunique()
    media_etq = total_etq / horas_ativas if horas_ativas > 0 else 0
    
    espera_valida = df_final['Tempo_Espera_Minutos'].dropna()
    espera_valida = espera_valida[espera_valida > 0]
    
    if not espera_valida.empty:
        media_espera_min = espera_valida.mean()
        texto_espera = f"{int(media_espera_min // 60)}h {int(media_espera_min % 60)}m"
    else:
        texto_espera = "Sem Dados"

    with c1: exibir_kpi("Etiquetas", total_etq, "Guardadas", "#3498DB")
    with c2: exibir_kpi("Peças", f"{total_pcs:,.0f}".replace(',','.'), "Volume Físico", "#9B59B6")
    with c3: exibir_kpi("SLA Doca", texto_espera, "Tempo médio aguardando", "#E74C3C")
    with c4: exibir_kpi("Média Etq/Hr", f"{media_etq:.1f}", "Velocidade", "#1ABC9C")
    with c5: exibir_kpi("Operador", operador_sel if operador_sel != "Todos" else "Equipe Total", "Filtro atual", "#F39C12")

    st.markdown("---")

    # --- GRÁFICOS LADO A LADO (META VS REAL E PIZZA DE ÁREAS) ---
    col_graf1, col_graf2 = st.columns([6, 4])
    
    with col_graf1:
        st.subheader("⏱️ Fluxo: Conferência (Meta) vs Armazenagem (Real)")
        
        df_meta_hora = df_dia.groupby('Hora_Conf')['NU_ETIQUETA'].nunique().reset_index()
        df_meta_hora.columns = ['Hora', 'Meta']
        
        df_real_hora = df_final.groupby('Hora_Armz')['NU_ETIQUETA'].nunique().reset_index()
        df_real_hora.columns = ['Hora', 'Realizado']
        
        df_grafico = pd.merge(df_meta_hora, df_real_hora, on='Hora', how='outer').fillna(0).sort_values('Hora')
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df_grafico['Hora'], y=df_grafico['Realizado'], name='Armazenado', marker_color='#3498DB',
            text=df_grafico['Realizado'], textposition='auto', textfont=dict(size=14, color='white', weight='bold')
        ))
        fig.add_trace(go.Scatter(
            x=df_grafico['Hora'], y=df_grafico['Meta'], name='Meta (Conferido)', 
            mode='lines+markers+text', text=df_grafico['Meta'], textposition='top center', 
            textfont=dict(size=14, color='#E74C3C', weight='bold'),
            line=dict(color='#E74C3C', width=3, dash='dot'), marker=dict(size=8)
        ))
        
        fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', legend=dict(orientation="h", y=1.15), margin=dict(t=50))
        st.plotly_chart(fig, use_container_width=True)

    with col_graf2:
        # 🚀 NOVO: Gráfico de Pizza por Tipo de Área
        st.subheader("📍 Armazenagem por Tipo de Área")
        
        df_pizza = df_final.groupby('Tipo_Area')['NU_ETIQUETA'].nunique().reset_index()
        df_pizza.columns = ['Tipo de Área', 'Etiquetas Guardadas']
        
        fig_pie = px.pie(
            df_pizza, 
            names='Tipo de Área', 
            values='Etiquetas Guardadas', 
            hole=0.45,
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig_pie.update_traces(
            textposition='inside', 
            textinfo='percent+label+value', 
            textfont=dict(size=14, weight='bold', color='white')
        )
        fig_pie.update_layout(plot_bgcolor='rgba(0,0,0,0)', showlegend=False, margin=dict(t=50, b=20))
        
        st.plotly_chart(fig_pie, use_container_width=True)

    # --- TABELA DE PRODUTIVIDADE E CORRIDA DE OPERADORES ---
    if operador_sel == "Todos":
        st.markdown("---")
        st.subheader("📈 Corrida Hora a Hora por Operador")
        
        df_ops_hora = df_dia.groupby(['Hora_Armz', 'OPERADOR'])['NU_ETIQUETA'].nunique().reset_index()
        df_ops_hora.columns = ['Hora', 'Operador', 'Etiquetas Guardadas']
        df_ops_hora = df_ops_hora.sort_values('Hora')
        
        if not df_ops_hora.empty:
            fig_linhas = px.line(
                df_ops_hora, x='Hora', y='Etiquetas Guardadas', color='Operador', markers=True
            )
            fig_linhas.update_layout(
                plot_bgcolor='rgba(0,0,0,0)', legend=dict(orientation="h", y=-0.2, title=""),
                xaxis_title="Horário", yaxis_title="Etiquetas Armazenadas"
            )
            fig_linhas.update_traces(line=dict(width=3), marker=dict(size=8))
            st.plotly_chart(fig_linhas, use_container_width=True)
        else:
            st.info("Não há dados suficientes para gerar o gráfico comparativo.")

        st.markdown("---")
        st.subheader("🏆 Ranking de Produtividade")
        
        ranking = df_dia.groupby('OPERADOR').agg({
            'NU_ETIQUETA': 'nunique',
            'QT_PRODUTO': 'sum',
            'Hora_Armz': 'nunique',
            'Tempo_Espera_Minutos': lambda x: x[x > 0].mean()
        }).reset_index()
        
        ranking.columns = ['Operador', 'Etiquetas', 'Peças', 'Horas Ativas', 'SLA Médio (Minutos)']
        
        ranking['SLA Médio (Minutos)'] = ranking['SLA Médio (Minutos)'].fillna(0).round(0)
        ranking['Etq/Hora'] = (ranking['Etiquetas'] / ranking['Horas Ativas']).round(1)
        ranking['Peças/Etiqueta'] = (ranking['Peças'] / ranking['Etiquetas']).round(1)
        
        ranking = ranking[['Operador', 'Etiquetas', 'Peças', 'Peças/Etiqueta', 'Horas Ativas', 'Etq/Hora', 'SLA Médio (Minutos)']]
        
        st.dataframe(ranking.sort_values('Etiquetas', ascending=False), use_container_width=True, hide_index=True)

else:
    st.error("Não há dados formatados corretamente. Verifique se a planilha tem datas válidas.")