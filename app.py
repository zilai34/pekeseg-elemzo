import streamlit as st
import pandas as pd
import plotly.express as px

# 1. KONFIGURÁCIÓ
HIVATALOS_JELSZO = "Velencei670905"
RAKLAP_KOD = '146'

st.set_page_config(page_title="Pékség Dashboard", layout="wide")

# Belépés
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
        # Kényszerített latin-1 kódolás a magyar karakterek miatt
        data = pd.read_csv(f, sep=';', decimal=',', encoding='latin-1')
        temp_list.append(data)
    
    df = pd.concat(temp_list, ignore_index=True).drop_duplicates()
    
    # Oszlopnevek és szűrések
    if 'ST_NE' in df.columns: df = df.rename(columns={'ST_NE': 'ST_NEFT'})
    df = df[df['ST_CIKKSZAM'].astype(str).str.strip() != RAKLAP_KOD]
    df['SF_TELJ'] = pd.to_datetime(df['SF_TELJ'], errors='coerce')
    df = df.dropna(subset=['SF_TELJ'])
    df['Ev'] = df['SF_TELJ'].dt.year
    df['Honap'] = df['SF_TELJ'].dt.strftime('%m')

    # Szűrő
    partnerek = ["Összes"] + sorted(df['SF_UGYFELNEV'].unique().tolist())
    v_partner = st.selectbox("Partner választása:", partnerek)

    f_df = df.copy()
    if v_partner != "Összes":
        f_df = f_df[f_df['SF_UGYFELNEV'] == v_partner]

    st.subheader(f"Árbevétel alakulása: {v_partner}")
    
    # Adatok összesítése
    stats = f_df.groupby(['Honap', 'Ev'])['ST_NEFT'].sum().unstack().fillna(0).astype(int)
    
    # --- A VÉGSŐ JAVÍTÁS ---
    # Ha a st.dataframe és a st.table is hiba, akkor HTML-ként íratjuk ki
    # Ez megkerüli az összes Streamlit-specifikus táblázatkezelési hibát
    st.write("### Havi adatok (Ft)")
    st.write(stats.to_html(escape=False), unsafe_allow_html=True)
    
    st.divider()

    # Grafikon - Remélhetőleg a Plotly nem dob hibát (más könyvtár)
    fig = px.bar(f_df.groupby(['Honap', 'Ev'])['ST_NEFT'].sum().reset_index(), 
                 x='Honap', y='ST_NEFT', color='Ev', barmode='group',
                 labels={'ST_NEFT': 'Nettó árbevétel'})
    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("Kérlek, töltsd fel a CSV fájlokat a bal oldalon.")
