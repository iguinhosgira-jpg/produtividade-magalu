import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials
import json

# =========================================================================
# 1. CONFIGURAÇÕES INICIAIS E CSS
# =========================================================================
st.set_page_config(page_title="Torre de Controle | Armazenagem", page_icon="⚡️", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #F8F9FA; }
    .kpi-card {
        background-color: #FFFFFF; border-radius: 12px; padding: 20px;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.04); border-left: 5px solid #0086FF;
        transition: transform 0.2s; margin-bottom: 20px;
    }
    .kpi-card:hover { transform: translateY(-3px); box-shadow: 0 6px 15px rgba(0, 0, 0, 0.08); }
    .kpi-title { margin: 0; font-size: 12px; color: #6C757D; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }
    .kpi-value { margin: 5px 0; font-size: 32px; color: #212529; font-weight: 900; }
    .kpi-subtitle { margin: 0; font-size: 12px; color: #ADB5BD; font-weight: 500; }
    .bloco-header { color: #2C3E50; font-weight: 800; font-size: 22px; margin-top: 30px; margin-bottom: 10px; border-bottom: 2px solid #E9ECEF; padding-bottom: 5px;}
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
# FUNÇÃO DO POP-UP (RAIO-X DA HORA)
# =========================================================================
@st.dialog("🔍 RAIO-X DA HORA: DETALHAMENTO DA OPERAÇÃO", width="large")
def popup_detalhe_hora(hora, df_base, data_sel):
    # Filtra tudo que aconteceu nesta hora (seja entrada de conferência ou saída de armazenagem)
    df_hora = df_base[
        ((df_base['Hora_Conf'] == hora) & (df_base['Data_Conf'] == data_sel)) | 
        ((df_base['Hora_Armz'] == hora) & (df_base['Data_Armz'] == data_sel) & (df_base['SITUACAO'] == '25'))
    ].copy()
    
    if df_hora.empty:
        st.warning(f"Nenhuma movimentação registrada às {hora}.")
        return
        
    st.markdown(f"### ⏱️ Resumo Operacional das **{hora}**")
    
    qtd_conf = df_hora[(df_hora['Hora_Conf'] == hora) & (df_hora['Data_Conf'] == data_sel)]['NU_ETIQUETA'].nunique()
    qtd_armz = df_hora[(df_hora['Hora_Armz'] == hora) & (df_hora['Data_Armz'] == data_sel) & (df_hora['SITUACAO'] == '25')]['NU_ETIQUETA'].nunique()
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Etiquetas Conferidas", qtd_conf)
    c2.metric("Etiquetas Armazenadas", qtd_armz)
    c3.metric("Peças Movimentadas", f"{df_hora['QT_PRODUTO'].sum():,.0f}".replace(',','.'))
    c4.metric("Agendas Processadas", df_hora['AGENDA'].nunique())
    
    st.markdown("#### 📋 Relatório Geral de Movimentações")
    
    # Preparando a tabela para exibição
    df_exibicao = df_hora[['NU_ETIQUETA', 'SITUACAO', 'PRODUTO', 'AGENDA', 'CONFERENTE', 'OPERADOR', 'Hora_Conf', 'Hora_Armz']].copy()
    df_exibicao['SITUACAO'] = df_exibicao['SITUACAO'].map({'23': '23 - Pendente', '25': '25 - Armazenado'})
    df_exibicao.columns = ['Etiqueta', 'Status Atual', 'Produto', 'Agenda', 'Conferente', 'Operador', 'H. Conferência', 'H. Armazenagem']
    
    st.dataframe(df_exibicao, use_container_width=True, hide_index=True)

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
        df.columns = df.columns.str.strip().str.upper() 
        
        # Mapeamento pelas colunas exatas
        df['NU_ETIQUETA'] = df['NU_ETIQUETA'].astype(str).str.strip()
        df['AGENDA'] = df['AGENDA'].astype(str).str.strip().str.upper()
        df['PRODUTO'] = df['PRODUTO'].astype(str).str.strip()
        df['QT_PRODUTO'] = pd.to_numeric(df['QT_PRODUTO'], errors='coerce').fillna(0)
        df['SITUACAO'] = df['SITUACAO'].astype(str).str.strip()
        df['OPERADOR'] = df['OPERADOR'].astype(str).str.strip().str.upper()
        df['CONFERENTE'] = df['CONFERENTE'].astype(str).str.strip().str.upper()
        
        # Processando Datas e Horas
        df['Data_Ref'] = pd.to_datetime(df['DATA'], format='%d/%m/%Y', errors='coerce').dt.date
        df['DT_CONFERENCIA_CALC'] = pd.to_datetime(df['DT_CONFERENCIA'], errors='coerce') 
        df['DT_ARMAZENAGEM_CALC'] = pd.to_datetime(df['DT_ARMAZENAGEM'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
        
        df['Data_Conf'] = df['DT_CONFERENCIA_CALC'].dt.date
        df['Data_Armz'] = df['Data_Ref'] 
        
        def formata_hora(h):
            if pd.isna(h) or str(h).strip() in ['', 'NAN', 'NULL', 'NONE']: return None
            try: return f"{int(float(h)):02d}:00"
            except: return None
                
        df['Hora_Conf'] = df['HORA CONF'].apply(formata_hora)
        df['Hora_Armz'] = df['HORA ARMZ'].apply(formata_hora)
        df['Tempo_Espera_Minutos'] = (df['DT_ARMAZENAGEM_CALC'] - df['DT_CONFERENCIA_CALC']).dt.total_seconds() / 60.0
        
        return df.dropna(subset=['Data_Ref'])
    except Exception as e:
        st.error(f"Erro na conexão: {e}")
        return pd.DataFrame()

df_bruto = carregar_dados()

if not df_bruto.empty:
    # Regra de Ouro: Remove tudo que não seja a fila da doca (23) ou o guardado (25)
    df_bruto = df_bruto[df_bruto['SITUACAO'].isin(['23', '25'])]

    # =========================================================================
    # PAINEL LATERAL (COM FILTRO DE CONFERENTE E OPERADOR)
    # =========================================================================
    st.sidebar.image("https://magalog.com.br/opengraph-image.jpg?fdd536e7d35ec9da", width=250)
    st.sidebar.markdown("### 🎛️ Controles da Operação")
    
    data_max = df_bruto['Data_Conf'].dropna().max()
    data_sel = st.sidebar.date_input("🗓️ Data de Análise", data_max)
    
    modo_visao = st.sidebar.radio(
        "🔎 Modo de Análise",
        ["Líquida (Apenas do Dia)", "Global (Incluir Herança)"],
        help="Líquida: Foca estritamente no que entrou hoje. Global: Puxa o backlog que sobrou de ontem."
    )
    
    # Prepara a base do dia
    df_hoje_conf = df_bruto[df_bruto['Data_Conf'] == data_sel]
    df_hoje_armz = df_bruto[df_bruto['Data_Armz'] == data_sel]
    
    if modo_visao == "Líquida (Apenas do Dia)":
        df_base = df_hoje_conf.copy()
    else:
        df_base = pd.concat([df_hoje_conf, df_hoje_armz]).drop_duplicates(subset=['NU_ETIQUETA'])

    fantasmas = ['', 'NAN', 'NONE', 'NULL']

    # --- FILTRO 1: CONFERENTES ---
    conferentes_validos = sorted([c for c in df_base['CONFERENTE'].unique() if pd.notna(c) and c not in fantasmas])
    conf_sel = st.sidebar.multiselect("📋 Filtrar Conferente (Remova intrusos):", options=conferentes_validos, default=conferentes_validos)
    
    # Aplica filtro de Conferente na base geral
    df_base = df_base[df_base['CONFERENTE'].isin(conf_sel)]

    # --- FILTRO 2: OPERADORES ---
    operadores_validos = sorted([op for op in df_base['OPERADOR'].unique() if pd.notna(op) and op not in fantasmas])
    op_sel = st.sidebar.multiselect("👥 Filtrar Operador (Armazenagem):", options=operadores_validos, default=operadores_validos)
    
    # =========================================================================
    # LÓGICA DE DADOS E CABEÇALHO
    # =========================================================================
    # df_producao_equipe: apenas o que foi ARMAZENADO (Sit 25) hoje pela EQUIPE SELECIONADA
    df_producao_equipe = df_base[(df_base['Data_Armz'] == data_sel) & (df_base['SITUACAO'] == '25') & (df_base['OPERADOR'].isin(op_sel))]

    st.title(f"🚀 Torre de Controle | {data_sel.strftime('%d/%m/%Y')}")
    st.caption(f"Visualizando: **{modo_visao}** (Conferentes Fantasmas Ignorados)")
    
    # BLOCO 1: KPIs
    c1, c2, c3, c4 = st.columns(4)
    
    qtd_etiquetas_armz = df_producao_equipe['NU_ETIQUETA'].nunique()
    qtd_pecas_armz = df_producao_equipe['QT_PRODUTO'].sum()
    
    # Total de Pendências Reais da Doca
    qtd_pendentes_doca = df_base[df_base['SITUACAO'] == '23']['NU_ETIQUETA'].nunique()
    if modo_visao == "Global (Incluir Herança)":
        # Soma o que ficou do passado E pertence aos conferentes selecionados
        heranca = df_bruto[(df_bruto['Data_Conf'] < data_sel) & (df_bruto['SITUACAO'] == '23') & (df_bruto['CONFERENTE'].isin(conf_sel))]
        qtd_pendentes_doca += heranca['NU_ETIQUETA'].nunique()
        saldo_inicial = heranca['NU_ETIQUETA'].nunique()
    else:
        saldo_inicial = 0
    
    espera_valida = df_producao_equipe[df_producao_equipe['Tempo_Espera_Minutos'] > 0]['Tempo_Espera_Minutos']
    sla_medio = espera_valida.mean() if not espera_valida.empty else 0
    txt_sla = f"{int(sla_medio // 60)}h {int(sla_medio % 60)}m"
    
    with c1: exibir_kpi("Armazenados (Sit. 25)", f"{qtd_etiquetas_armz:,.0f}".replace(',','.'), "Equipe selecionada", "#0086FF")
    with c2: exibir_kpi("Pendências (Sit. 23)", f"{qtd_pendentes_doca:,.0f}".replace(',','.'), "Fila total da Doca", "#E74C3C")
    with c3: exibir_kpi("SLA Médio Doca", txt_sla, "Tempo em espera", "#F44336" if sla_medio > 120 else "#4CAF50")
    
    texto_op_kpi = "Equipe Total" if len(op_sel) == len(operadores_validos) else (op_sel[0] if len(op_sel) == 1 else f"{len(op_sel)} Operadores")
    with c4: exibir_kpi("Filtro Ativo", texto_op_kpi, "Armazenagem analisada", "#FF9800")

    # =========================================================================
    # BLOCO 2: FLUXO E PENDÊNCIAS (INTERATIVO)
    # =========================================================================
    col_tit, col_sel = st.columns([7, 3])
    with col_tit:
        st.markdown("<div class='bloco-header'>🌊 Fluxo de Trabalho e Fila da Doca</div>", unsafe_allow_html=True)
    
    horas_conf = df_base[df_base['Data_Conf'] == data_sel]['Hora_Conf'].dropna().unique()
    horas_armz = df_producao_equipe['Hora_Armz'].dropna().unique()
    todas_horas = sorted(list(set(list(horas_conf) + list(horas_armz))))
    
    with col_sel:
        st.markdown("<br>", unsafe_allow_html=True) # Espaçamento para alinhar
        hora_manual = st.selectbox("🖱️ Abrir Raio-X da Hora:", ["Selecione..."] + todas_horas, help="Escolha uma hora ou clique direto em uma barra do gráfico abaixo!")

    dados_grafico = []
    
    for hora in todas_horas:
        # A. CONFERIDOS NA HORA (Demanda dos Conferentes Filtrados)
        conf_hora = df_base[(df_base['Data_Conf'] == data_sel) & (df_base['Hora_Conf'] == hora)]['NU_ETIQUETA'].nunique()
        
        # B. ARMAZENADOS NA HORA (Produção da Equipe Filtrada)
        armz_hora = df_producao_equipe[df_producao_equipe['Hora_Armz'] == hora]['NU_ETIQUETA'].nunique()
        
        # C. PENDÊNCIAS NA DOCA (Reconstruindo a Fila exata)
        if modo_visao == "Líquida (Apenas do Dia)":
            entrou_hoje_ate_agora = df_base[(df_base['Data_Conf'] == data_sel) & (df_base['Hora_Conf'] <= hora)]['NU_ETIQUETA'].nunique()
            saiu_hoje_ate_agora = df_base[(df_base['Data_Conf'] == data_sel) & (df_base['SITUACAO'] == '25') & (df_base['Data_Armz'] == data_sel) & (df_base['Hora_Armz'] <= hora)]['NU_ETIQUETA'].nunique()
            pendencias = entrou_hoje_ate_agora - saiu_hoje_ate_agora
        else: # Visão Global
            entrou_historico = df_bruto[(df_bruto['CONFERENTE'].isin(conf_sel)) & ((df_bruto['Data_Conf'] < data_sel) | ((df_bruto['Data_Conf'] == data_sel) & (df_bruto['Hora_Conf'] <= hora)))]['NU_ETIQUETA'].nunique()
            saiu_historico = df_bruto[(df_bruto['CONFERENTE'].isin(conf_sel)) & (df_bruto['SITUACAO'] == '25') & ((df_bruto['Data_Armz'] < data_sel) | ((df_bruto['Data_Armz'] == data_sel) & (df_bruto['Hora_Armz'] <= hora)))]['NU_ETIQUETA'].nunique()
            pendencias = entrou_historico - saiu_historico
            
        pendencias = max(0, pendencias)
        
        dados_grafico.append({
            'Hora': hora,
            'Armazenados': armz_hora,
            'Conferidos': conf_hora,
            'Pendências': pendencias
        })
        
    df_fluxo = pd.DataFrame(dados_grafico)

    if not df_fluxo.empty:
        max_y = df_fluxo[['Armazenados', 'Conferidos']].max().max() if not df_fluxo.empty else 10
        teto_grafico = max_y * 1.2 if max_y > 0 else 10

        fig_fluxo = go.Figure()
        
        fig_fluxo.add_trace(go.Bar(x=df_fluxo['Hora'], y=df_fluxo['Armazenados'], name='Armazenados (Sua Equipe)', marker_color='#0086FF', text=df_fluxo['Armazenados'], textposition='auto', textfont=dict(color='white')))
        fig_fluxo.add_trace(go.Bar(x=df_fluxo['Hora'], y=df_fluxo['Conferidos'], name='Conferidos (Nova Demanda)', marker_color='#9d26ff', text=df_fluxo['Conferidos'], textposition='outside', textfont=dict(color='#9d26ff')))
        fig_fluxo.add_trace(go.Scatter(x=df_fluxo['Hora'], y=df_fluxo['Pendências'], name='Pendências Reais da Doca', mode='lines+markers+text', line=dict(color='#E74C3C', width=3), yaxis='y2', text=df_fluxo['Pendências'], textposition='top center', textfont=dict(color='#E74C3C', weight='bold')))
        
        fig_fluxo.update_layout(
            plot_bgcolor='rgba(0,0,0,0)', barmode='group',
            legend=dict(orientation="h", y=1.15, x=0.5, xanchor='center'),
            yaxis=dict(title="Qtd Etiquetas", showgrid=True, gridcolor='#F1F3F5', range=[0, teto_grafico]), 
            yaxis2=dict(title="Fila Acumulada", overlaying='y', side='right', showgrid=False),
            hovermode="x unified"
        )
        
        # Gráfico que captura o clique
        evento_grafico = st.plotly_chart(fig_fluxo, use_container_width=True, on_select="rerun")
        
        # Gatilho do Pop-up
        if hora_manual != "Selecione...":
            popup_detalhe_hora(hora_manual, df_base, data_sel)
        elif isinstance(evento_grafico, dict) and "selection" in evento_grafico:
            pontos = evento_grafico["selection"].get("points", [])
            if pontos:
                hora_clicada = pontos[0].get("x")
                if hora_clicada:
                    popup_detalhe_hora(hora_clicada, df_base, data_sel)
    else:
        st.info("Nenhuma movimentação identificada nas horas processadas.")

    # =========================================================================
    # BLOCO 3: OPERADORES
    # =========================================================================
    if len(op_sel) > 0:
        st.markdown("<div class='bloco-header'>👥 Performance da Equipe Selecionada (Apenas Sit. 25)</div>", unsafe_allow_html=True)
        col_rank, col_heat = st.columns([4, 6])
        
        with col_rank:
            st.markdown("##### 🏆 Ranking de Armazenagem")
            rank_op = df_producao_equipe.groupby('OPERADOR').agg({'NU_ETIQUETA': 'nunique', 'Hora_Armz': 'nunique'}).reset_index()
            rank_op.columns = ['Operador', 'Etiquetas', 'Horas']
            rank_op['Etq/Hora'] = (rank_op['Etiquetas'] / rank_op['Horas']).round(1)
            st.dataframe(rank_op.sort_values('Etiquetas', ascending=False)[['Operador', 'Etiquetas', 'Etq/Hora']], use_container_width=True, hide_index=True, height=350)
        
        with col_heat:
            st.markdown("##### 🔥 Calor de Produtividade (Armazenados/Hora)")
            df_heat = df_producao_equipe.groupby(['OPERADOR', 'Hora_Armz'])['NU_ETIQUETA'].nunique().reset_index()
            fig_heat = px.density_heatmap(df_heat, x="Hora_Armz", y="OPERADOR", z="NU_ETIQUETA", color_continuous_scale="Blues", text_auto=True)
            fig_heat.update_layout(plot_bgcolor='rgba(0,0,0,0)', yaxis=dict(title=""), xaxis_title="Hora", coloraxis_showscale=False)
            st.plotly_chart(fig_heat, use_container_width=True)
    else:
        st.warning("⚠️ Selecione ao menos um operador na barra lateral para ver os dados da equipe.")

else:
    st.error("⚠️ Dados não encontrados para a data selecionada.")
