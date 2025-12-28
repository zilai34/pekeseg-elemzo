import streamlit as st
import pandas as pd
import plotly.express as px
from openai import OpenAI

# --- OLDAL BEÁLLÍTÁSA ---
st.set_page_config(page_title="Pékség Dashboard", layout="wide")

# --- SIDEBAR: KULCS ÉS FÁJL ---
st.sidebar.header("Beállítások")
# Itt adod meg a weboldalon az OpenAI kulcsot
openai_api_key = st.sidebar.text_input("OpenAI API Key", type="password", help="Másold be ide az OpenAI API kulcsodat")

uploaded_file = st.sidebar.file_uploader("Töltsd fel a CSV fájlt", type="csv")

# --- FIX SZABÁLYOK ---
SZARAZ_LISTA = ['509496007', '509500001', '509502005', '524145003', '524149001']
RAKLAP_KOD = '146'

if uploaded_file:
    try:
        # Beolvasás latin-1 kódolással a Unicode hiba ellen
        df = pd.read_csv(uploaded_file, sep=';', decimal=',', encoding='latin-1')
        
        # 1. Raklap (146) azonnali törlése
        df = df[df['ST_CIKKSZAM'].astype(str).str.strip() != RAKLAP_KOD]
        
        # 2. Dátum és Hónap kezelése
        df['SF_TELJ'] = pd.to_datetime(df['SF_TELJ'])
        df['Honap'] = df['SF_TELJ'].dt.strftime('%Y-%m')
        
        # 3. Kategorizálás (Friss/Száraz)
        def kategoria_szuro(c):
            if str(c).strip() in SZARAZ_LISTA:
                return "Száraz áru"
            return "Friss áru"
        
        df['Kategória'] = df['ST_CIKKSZAM'].apply(kategoria_szuro)

        st.title("📊 Éves és Havi Áruforgalmi Elemző")

        # --- SZŰRŐK A FELÜLETEN ---
        col1, col2 = st.columns(2)
        with col1:
            partnerek = ["Összes partner"] + sorted(df['SF_UGYFELNEV'].unique().tolist())
            valasztott_partner = st.selectbox("Válassz partnert:", partnerek)
        with col2:
            kategoriak = st.multiselect("Kategória:", ["Friss áru", "Száraz áru"], default=["Friss áru", "Száraz áru"])

        # Szűrt táblázat létrehozása
        f_df = df[df['Kategória'].isin(kategoriak)]
        if valasztott_partner != "Összes partner":
            f_df = f_df[f_df['SF_UGYFELNEV'] == valasztott_partner]

        # --- KPI MUTATÓK ---
        m1, m2, m3 = st.columns(3)
        m1.metric("Összes mennyiség", f"{f_df['ST_MENNY'].sum():,.0f} db".replace(",", " "))
        m2.metric("Nettó érték", f"{f_df['ST_NEFT'].sum():,.0f} Ft".replace(",", " "))
        
        # Trend számítás
        havi_osszesito = f_df.groupby('Honap')['ST_MENNY'].sum()
        if len(havi_osszesito) > 1:
            valtozas = ((havi_osszesito.iloc[-1] / havi_osszesito.iloc[-2]) - 1) * 100
            m3.metric("Trend (utolsó hónap)", f"{valtozas:+.1f}%")

        # --- GRAFIKON ---
        st.subheader("Havi forgalom alakulása")
        chart_data = f_df.groupby(['Honap', 'Kategória'])['ST_MENNY'].sum().reset_index()
        fig = px.bar(chart_data, x='Honap', y='ST_MENNY', color='Kategória', barmode='group')
        st.plotly_chart(fig, use_container_width=True)

        # --- OPENAI ELEMZÉS ---
        st.divider()
        if st.button("🤖 AI Elemzés indítása"):
            if not openai_api_key:
                st.error("Kérlek, add meg az OpenAI API kulcsot a bal oldalon!")
            else:
                client = OpenAI(api_key=openai_api_key)
                with st.spinner("Az AI elemzi az adatokat..."):
                    adat_szoveg = havi_osszesito.to_string()
                    prompt = f"Elemezd a következő pékségi havi eladási adatokat (db): {adat_szoveg}. Milyen trendet látsz? Adj üzleti tanácsot magyarul."
                    response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
                    st.info(response.choices[0].message.content)

        # --- ADATTÁBLA ÉS LETÖLTÉS ---
        st.subheader("Részletes adatok")
        st.dataframe(f_df[['SF_TELJ', 'SF_UGYFELNEV', 'ST_CIKKNEV', 'Kategória', 'ST_MENNY', 'ST_NEFT']])
        
        csv = f_df.to_csv(index=False, sep=';').encode('latin-1')
        st.download_button("Kategorizált CSV letöltése", csv, "elemzes.csv", "text/csv")

    except Exception as e:
        st.error(f"Hiba történt a fájl feldolgozásakor: {e}")

else:
    st.info("Töltsd fel a CSV fájlt a kezdéshez!")
