import streamlit as st
import pandas as pd
import plotly.express as px

# 1. KONFIGURÁCIÓ
HIVATALOS_JELSZO = "Velencei670905"
RAKLAP_KOD = '146'

st.set_page_config(page_title="Pékség Dashboard", layout="wide")

if "bejelentkezve" not in st.session_state:
    st.session_state["bejelentkezve"] = False

if not st.session_state["bejelentkezve"]:
    st.title("🔐 Pékség Belépés")
    jelszo_input = st.text_input("Jelszó:", type="password")
    if st.button("Belépés"):
        if jelszo_input == HIVATALOS_JELSZO:
            st.session_state["bejelentkezve"] = True
            st.rerun()
    st.stop()

st.title("📊 Pékség Adat-Elemző")

with st.sidebar:
    st.header("📁 Adatfeltöltés")
    uploaded_files = st.file_uploader("CSV fájlok", type="csv", accept_multiple_files=True)

if uploaded_files:
    temp_list = []
    for f in uploaded_files:
        data = pd.read_csv(f, sep=';', decimal=',', encoding='latin-1')
        temp_list.append(data)
    
    df = pd.concat(temp_list, ignore_index=True).drop_duplicates()
    
    if 'ST_NE' in df.columns: df = df.rename(columns={'ST_NE': 'ST_NEFT'})
    df = df[df['ST_CIKKSZAM'].astype(str).str.strip() != RAKLAP_KOD]
    df['SF_TELJ'] = pd.to_datetime(df['SF_TELJ'], errors='coerce')
    df = df.dropna(subset=['SF_TELJ'])
    df['Ev'] = df['SF_TELJ'].dt.year.astype(str) # Év szövegként a jobb szűréshez
    df['Honap'] = df['SF_TELJ'].dt.strftime('%m')

    v_partner = st.selectbox("Partner:", ["Összes"] + sorted(df['SF_UGYFELNEV'].unique().tolist()))

    f_df = df.copy()
    if v_partner != "Összes": f_df = f_df[f_df['SF_UGYFELNEV'] == v_partner]

    # TÁBLÁZAT (HTML módban a stabilitásért)
    st.subheader(f"Adatok: {v_partner}")
    stats = f_df.groupby(['Honap', 'Ev'])['ST_NEFT'].sum().unstack().fillna(0).astype(int)
    st.write(stats.to_html(), unsafe_allow_html=True)
    
    st.divider()

    # GRAFIKON (Javított, egyedi oszlopnevekkel)
    chart_data = f_df.groupby(['Honap', 'Ev'])['ST_NEFT'].sum().reset_index()
    chart_data.columns = ['Honap', 'Ev', 'Bevetel']
    
    fig = px.bar(chart_data, x='Honap', y='Bevetel', color='Ev', 
                 barmode='group', title="Havi árbevétel összehasonlítása")
    fig.update_xaxes(type='category')
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Tölts fel CSV-ket!")
