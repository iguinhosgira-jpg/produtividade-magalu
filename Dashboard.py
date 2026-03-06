import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials
import os
import json

# --- CONFIGURAÇÃO DA PÁGINA (CLASSE AAA+) ---
st.set_page_config(page_title="Torre de Controle Inbound | Magalu", page_icon="🗼", layout="wide", initial_sidebar_state="expanded")

# --- ESTILIZAÇÃO PREMIUM CSS ---
st.markdown("""
<style>
    .stApp { background-color: #F8F9FA; }
    .kpi-card {
        background-color: #FFFFFF; border-radius: 10px; padding: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05); border-left: 5px solid #0086FF;
        transition: transform 0.2s;
        margin-bottom: 20px;
    }
    .kpi-card:hover { transform: translateY(-3px); box-shadow: 0 6px 12px rgba(0, 0, 0, 0.1); }
    .kpi-title { margin: 0; font-size: 13px; color: #6C757D; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }
    .kpi-value { margin: 5px 0; font-size: 32px; color: #212529; font-weight: 900; }
    .kpi-subtitle { margin: 0; font-size: 12px; color: #ADB5BD; font-weight: 500; }
    .header-title { color: #0086FF; font-weight: 900; font-size: 28px; margin-bottom: 0px;}
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

# --- POP-UP DETALHADO (O SEGREDO AAA+) ---
@st.dialog("🔍 RAIO-X DA HORA: DETALHAMENTO DE ARMAZENAGEM", width="large")
def popup_detalhe_hora(hora, df_filtrado):
    df_hora = df_filtrado[df_filtrado['Hora_Armz'] == hora]
    
    if df_hora.empty:
        st.warning(f"Nenhuma movimentação de armazenagem registrada às {hora}.")
        return
        
    st.markdown(f"### ⏱️ Resumo Operacional das **{hora}**")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Etiquetas Guardadas", df_hora['NU_ETIQUETA'].nunique())
    c2.metric("Peças Físicas", f"{df_hora['QT_PRODUTO'].sum():,.0f}".replace(',','.'))
    c3.metric("Maior Operador (MVP)", df_hora['OPERADOR'].value_counts().index[0])
    c4.metric("Agendas Processadas", df_hora['AGENDA'].nunique())
    
    st.markdown("---")
    
    colA, colB = st.columns(2)
    with colA:
        st.markdown("#### 🏆 TOP operadores Hora")
        top_ops = df_hora.groupby('OPERADOR')['NU_ETIQUETA'].nunique().reset_index().sort_values('NU_ETIQUETA', ascending=False)
        top_ops.columns = ['Operador', 'Etiquetas']
        st.dataframe(top_ops, use_container_width=True, hide_index=True)
        
    with colB:
        st.markdown("#### 🏭 Fornecedores Armazenados na Hora")
        top_forn = df_hora.groupby('FORNECEDOR')['NU_ETIQUETA'].nunique().reset_index().sort_values('NU_ETIQUETA', ascending=False)
        top_forn.columns = ['Fornecedor', 'Etiquetas']
        st.dataframe(top_forn, use_container_width=True, hide_index=True)
        
    st.markdown("#### 📋 Relatório Geral - Detalhado")
    df_lista = df_hora[['AGENDA', 'FORNECEDOR', 'NU_ETIQUETA', 'QT_PRODUTO', 'OPERADOR', 'Tipo_Area', 'Tempo_Espera_Minutos']].copy()
    df_lista['Tempo_Espera_Minutos'] = df_lista['Tempo_Espera_Minutos'].apply(lambda x: f"{int(x//60)}h {int(x%60)}m" if x > 0 else "0m")
    df_lista.columns = ['Agenda', 'Fornecedor', 'Etiqueta', 'Qtd Peças', 'Operador', 'Área Destino', 'SLA Doca']
    st.dataframe(df_lista, use_container_width=True, hide_index=True)


# --- MOTOR DE EXTRAÇÃO DE DADOS ---
@st.cache_data(ttl=300)
def carregar_dados_torre_controle():
    try:
        cred_dict = json.loads(st.secrets["google_json"])
        creds = Credentials.from_service_account_info(cred_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"])
        client = gspread.authorize(creds)
        
        sh = client.open_by_key('1F4Qs5xGPMjgWSO6giHSwFfDf5F-mlv1RuT4riEVU0I0')
        ws = sh.worksheet("ACOMPANHAMENTO GERAL")
        data = ws.get_all_values()
        
        df = pd.DataFrame(data[1:], columns=data[0])
        
        df['QT_PRODUTO'] = pd.to_numeric(df['QT_PRODUTO'], errors='coerce').fillna(0)
        df['DT_CONFERENCIA'] = pd.to_datetime(df['DT_CONFERENCIA'], errors='coerce') 
        df['DT_ARMAZENAGEM'] = pd.to_datetime(df['DT_ARMAZENAGEM'], dayfirst=True, errors='coerce')
        
        df['AGENDA'] = df.iloc[:, 3].astype(str).str.strip().str.upper()
        df['FORNECEDOR'] = df.iloc[:, 9].astype(str).str.strip().str.upper()
        
        cols = df.columns.str.upper()
        if 'CONFERENTE' in cols: df['CONFERENTE'] = df['CONFERENTE']
        elif 'USUARIO_CONFERENCIA' in cols: df['CONFERENTE'] = df['USUARIO_CONFERENCIA']
        else: df['CONFERENTE'] = "N/D"

        df['Data_Ref'] = df['DT_ARMAZENAGEM'].dt.date
        df['Hora_Conf'] = df['DT_CONFERENCIA'].dt.strftime('%H:00')
        df['Hora_Armz'] = df['DT_ARMAZENAGEM'].dt.strftime('%H:00')
        df['Tempo_Espera_Minutos'] = (df['DT_ARMAZENAGEM'] - df['DT_CONFERENCIA']).dt.total_seconds() / 60.0
        
        def definir_turno(hora):
            if pd.isna(hora): return 'Indefinido'
            h = hora.hour
            if 6 <= h < 14: return '1º Turno'
            elif 14 <= h < 22: return '2º Turno'
            else: return '3º Turno'
        df['Turno'] = df['DT_ARMAZENAGEM'].apply(definir_turno)
        
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
        st.error(f"Erro na Torre de Controle: {e}")
        return pd.DataFrame()

df_bruto = carregar_dados_torre_controle()
df_bruto = df_bruto.dropna(subset=['Data_Ref'])

if not df_bruto.empty:
    # =========================================================================
    # PAINEL DE FILTROS SUPERIORES (SIDEBAR)
    # =========================================================================
    st.sidebar.image("https://magalog.com.br/opengraph-image.jpg?fdd536e7d35ec9da", width=220)
    st.sidebar.markdown("<h2 style='color: #0086FF;'>🎛️ Filtros Globais</h2>", unsafe_allow_html=True)
    
    data_min = df_bruto['Data_Ref'].min()
    data_max = df_bruto['Data_Ref'].max()
    datas_sel = st.sidebar.date_input("🗓️ Período de Análise", [data_max, data_max], min_value=data_min, max_value=data_max)
    
    if len(datas_sel) == 2:
        df = df_bruto[(df_bruto['Data_Ref'] >= datas_sel[0]) & (df_bruto['Data_Ref'] <= datas_sel[1])]
    else:
        df = df_bruto[df_bruto['Data_Ref'] == datas_sel[0]]

    turno_sel = st.sidebar.multiselect("⏱️ Turno", df['Turno'].unique(), default=df['Turno'].unique())
    df = df[df['Turno'].isin(turno_sel)]

    st.markdown("<p class='header-title'>🗼 TORRE DE CONTROLE INBOUND (WMS)</p>", unsafe_allow_html=True)
    st.caption("Acompanhamento de Produtividade | Conferência e Armazenagem")
    st.markdown("---")

    # =========================================================================
    # CONSTRUÇÃO DAS ABAS (TABS)
    # =========================================================================
    tab1, tab2 = st.tabs(["📦 RECEBIMENTO (Conferentes)", "🚜 ARMAZENAGEM (Operadores)"])

    # -------------------------------------------------------------------------
    # ABA 1: RECEBIMENTO (CONFERENTES E FORNECEDORES)
    # -------------------------------------------------------------------------
    with tab1:
        st.subheader("🔎 Produtividade de Conferência (Agendas e Fornecedores)")
        
        df_agendas = df.groupby('AGENDA').agg(
            Inicio_Conf=('DT_CONFERENCIA', 'min'),
            Fim_Conf=('DT_CONFERENCIA', 'max'),
            Fornecedor=('FORNECEDOR', 'first'),
            Conferente=('CONFERENTE', 'first'),
            Total_Pecas=('QT_PRODUTO', 'sum'),
            Total_Etiquetas=('NU_ETIQUETA', 'nunique')
        ).reset_index()
        
        df_agendas['Tempo_Gasto_Minutos'] = (df_agendas['Fim_Conf'] - df_agendas['Inicio_Conf']).dt.total_seconds() / 60.0
        df_agendas['Tempo_Gasto_Minutos'] = df_agendas['Tempo_Gasto_Minutos'].apply(lambda x: x if x > 1 else 1.0)
        
        media_tempo_agenda = df_agendas['Tempo_Gasto_Minutos'].mean()
        txt_media_agenda = f"{int(media_tempo_agenda // 60)}h {int(media_tempo_agenda % 60)}m" if not pd.isna(media_tempo_agenda) else "0h 0m"
        
        c1, c2, c3 = st.columns(3)
        with c1: exibir_kpi("Tempo Médio p/ Agenda", txt_media_agenda, "Descarga e Conferência", "#0086FF")
        with c2: exibir_kpi("Maior Carga Recebida", f"{df_agendas['Total_Pecas'].max():,.0f}".replace(',','.'), "Peças em uma única agenda", "#FF4B4B")
        with c3: exibir_kpi("Fornecedores Atendidos", df['FORNECEDOR'].nunique(), "No período selecionado", "#4CAF50")

        st.markdown("---")
        colF1, colF2 = st.columns(2)
        
        with colF1:
            df_forn = df_agendas.groupby('Fornecedor').agg({'Tempo_Gasto_Minutos':'mean', 'Total_Etiquetas':'sum'}).reset_index()
            df_forn = df_forn[df_forn['Fornecedor'] != 'NAN'].sort_values('Tempo_Gasto_Minutos', ascending=False).head(10)
            fig_forn = px.bar(df_forn, x='Tempo_Gasto_Minutos', y='Fornecedor', orientation='h', title="🏭 TOP 10 Fornecedores Mais Demorados (Média Minutos/Agenda)", color='Tempo_Gasto_Minutos', color_continuous_scale='Reds', text_auto='.0f')
            fig_forn.update_layout(yaxis={'categoryorder':'total ascending'}, plot_bgcolor='rgba(0,0,0,0)', yaxis_title="", xaxis_title="Minutos Médios")
            st.plotly_chart(fig_forn, use_container_width=True)
            
        with colF2:
            df_conf = df_agendas.groupby('Conferente').agg({'AGENDA':'count', 'Tempo_Gasto_Minutos':'mean', 'Total_Pecas':'sum'}).reset_index()
            df_conf = df_conf[df_conf['Conferente'] != 'N/D']
            fig_scatter_conf = px.scatter(df_conf, x='Tempo_Gasto_Minutos', y='AGENDA', size='Total_Pecas', color='Conferente', title="⚡ Eficiência do Conferente (Volume vs Tempo)", hover_data=['Total_Pecas'])
            fig_scatter_conf.update_layout(plot_bgcolor='rgba(0,0,0,0)', xaxis_title="Tempo Médio por Agenda (Minutos)", yaxis_title="Qtd Agendas Finalizadas")
            st.plotly_chart(fig_scatter_conf, use_container_width=True)

        st.subheader("🏆 Ranking de Conferentes")
        df_conf_rank = df_conf.copy()
        df_conf_rank.columns = ['Conferente', 'Agendas Finalizadas', 'Tempo Médio (Min)', 'Total Peças Conferidas']
        df_conf_rank['Tempo Médio (Min)'] = df_conf_rank['Tempo Médio (Min)'].round(1)
        st.dataframe(df_conf_rank.sort_values('Agendas Finalizadas', ascending=False), use_container_width=True, hide_index=True)

    # -------------------------------------------------------------------------
    # ABA 2: ARMAZENAGEM (OPERADORES DE EMPILHADEIRA/CHÃO)
    # -------------------------------------------------------------------------
    with tab2:
        opcoes_ops = ["Equipe Total"] + sorted(df['OPERADOR'].astype(str).unique().tolist())
        col_filtro, _ = st.columns([3, 7])
        with col_filtro:
            op_sel = st.selectbox("👤 Filtrar Operador Específico:", opcoes_ops)
        
        df_op = df if op_sel == "Equipe Total" else df[df['OPERADOR'] == op_sel]
        
        # --- KPIs DE PRODUTIVIDADE DO OPERADOR ---
        c1, c2, c3, c4 = st.columns(4)
        
        qtd_agendas_op = df_op['AGENDA'].nunique()
        qtd_etiquetas_op = df_op['NU_ETIQUETA'].nunique()
        qtd_pecas_op = df_op['QT_PRODUTO'].sum()
        
        espera_valida_op = df_op[df_op['Tempo_Espera_Minutos'] > 0]['Tempo_Espera_Minutos']
        sla_doca_op = espera_valida_op.mean() if not espera_valida_op.empty else 0
        txt_sla_op = f"{int(sla_doca_op // 60)}h {int(sla_doca_op % 60)}m"

        with c1: exibir_kpi("Agendas Armazenadas", qtd_agendas_op, "Cargas movimentadas", "#0086FF")
        with c2: exibir_kpi("Etiquetas Guardadas", f"{qtd_etiquetas_op:,.0f}".replace(',','.'), "Pallets armazenados", "#9B59B6")
        with c3: exibir_kpi("Peças Físicas", f"{qtd_pecas_op:,.0f}".replace(',','.'), "Volume total", "#4CAF50")
        with c4: exibir_kpi("SLA Médio Doca", txt_sla_op, "Tempo médio esperando", "#F44336")

        st.markdown("---")

        col_graf1, col_graf2 = st.columns([7, 3])
        
        with col_graf1:
            col_titulo, col_manual = st.columns([7, 3])
            with col_titulo:
                st.subheader("⏱️ Gargalo: Conferência vs Armazenagem (Hora a Hora)")
            with col_manual:
                horas_disp = ["Selecione..."] + sorted(df_op['Hora_Armz'].dropna().unique().tolist())
                hora_manual = st.selectbox("Abrir Raio-X da Hora:", horas_disp, help="Ou apenas clique direto na barra do gráfico!")
            
            df_meta = df_op.groupby('Hora_Conf')['NU_ETIQUETA'].nunique().reset_index()
            df_meta.columns = ['Hora', 'Liberado_Doca']
            df_real = df_op.groupby('Hora_Armz')['NU_ETIQUETA'].nunique().reset_index()
            df_real.columns = ['Hora', 'Guardado_Rua']
            df_fluxo = pd.merge(df_meta, df_real, on='Hora', how='outer').fillna(0).sort_values('Hora')
            
            fig_fluxo = go.Figure()
            fig_fluxo.add_trace(go.Bar(x=df_fluxo['Hora'], y=df_fluxo['Guardado_Rua'], name='Guardado (Operador)', marker_color='#3498DB', text=df_fluxo['Guardado_Rua'], textposition='auto', textfont=dict(color='white', weight='bold')))
            fig_fluxo.add_trace(go.Scatter(x=df_fluxo['Hora'], y=df_fluxo['Liberado_Doca'], name='Liberado (Conferente)', mode='lines+markers+text', text=df_fluxo['Liberado_Doca'], textposition='top center', line=dict(color='#E74C3C', width=3, dash='dot'), textfont=dict(color='#E74C3C', weight='bold')))
            fig_fluxo.update_layout(plot_bgcolor='rgba(0,0,0,0)', legend=dict(orientation="h", y=1.15), clickmode='event+select')
            
            # Gráfico com o sensor de cliques ativado
            evento_grafico = st.plotly_chart(fig_fluxo, use_container_width=True, on_select="rerun")
            
            # Lógica de Captura do Clique ou do Selectbox
            if hora_manual != "Selecione...":
                popup_detalhe_hora(hora_manual, df_op)
            elif isinstance(evento_grafico, dict) and "selection" in evento_grafico:
                pontos = evento_grafico["selection"].get("points", [])
                if pontos:
                    hora_clicada = pontos[0].get("x")
                    if hora_clicada:
                        popup_detalhe_hora(hora_clicada, df_op)

        with col_graf2:
            st.subheader("📍 Áreas Armazenadas")
            df_pizza = df_op.groupby('Tipo_Area')['NU_ETIQUETA'].nunique().reset_index()
            df_pizza.columns = ['Tipo de Área', 'Etiquetas Guardadas']
            
            fig_pie = px.pie(df_pizza, names='Tipo de Área', values='Etiquetas Guardadas', hole=0.45, color_discrete_sequence=px.colors.qualitative.Pastel)
            fig_pie.update_traces(textposition='inside', textinfo='percent+label+value', textfont=dict(size=14, weight='bold', color='white'))
            fig_pie.update_layout(plot_bgcolor='rgba(0,0,0,0)', showlegend=False, margin=dict(t=10, b=20))
            st.plotly_chart(fig_pie, use_container_width=True)

        if op_sel == "Equipe Total":
            st.markdown("---")
            st.subheader("🏆 Ranking de Operadores (Armazenagem)")
            rank_op = df.groupby('OPERADOR').agg({
                'NU_ETIQUETA': 'nunique',
                'QT_PRODUTO': 'sum',
                'Hora_Armz': 'nunique',
                'Tempo_Espera_Minutos': lambda x: x[x > 0].mean()
            }).reset_index()
            rank_op.columns = ['Operador', 'Etiquetas Guardadas', 'Peças Físicas', 'Horas Trabalhadas', 'SLA Médio de Doca (Min)']
            rank_op['Etq/Hora'] = (rank_op['Etiquetas Guardadas'] / rank_op['Horas Trabalhadas']).round(1)
            rank_op['Peças/Etq'] = (rank_op['Peças Físicas'] / rank_op['Etiquetas Guardadas']).round(1)
            rank_op['SLA Médio de Doca (Min)'] = rank_op['SLA Médio de Doca (Min)'].fillna(0).round(0)
            
            rank_op = rank_op[['Operador', 'Etiquetas Guardadas', 'Peças Físicas', 'Peças/Etq', 'Horas Trabalhadas', 'Etq/Hora', 'SLA Médio de Doca (Min)']]
            st.dataframe(rank_op.sort_values('Etiquetas Guardadas', ascending=False), use_container_width=True, hide_index=True)

else:
    st.error("⚠️ Não foi possível carregar os dados. Verifique a conexão com o Google Sheets.")

