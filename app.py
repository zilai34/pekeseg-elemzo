import streamlit as st
import pandas as pd
import plotly.express as px
from openai import OpenAI

# --- JELSZÓ ---
HIVATALOS_JELSZO = "Velencei670905" 

st.set_page_config(page_title="Pékség Dashboard", layout="wide")

# --- BELÉPÉS ---
if "bejelentkezve" not in st.session_state:
    st.session_state["bejelentkezve"] = False

if not st.session_state["bejelentkezve"]:
    st.title("🔐 Bejelentkezés")
    jelszo_input = st.text_input("Jelszó:", type="password")
    if st.button("Belépés"):
        if jelszo_input == HIVATALOS_JELSZO:
            st.session_state["bejelentkezve"] = True
            st.rerun()
        else:
            st.error("Hibás jelszó!")
    st.stop()

# --- NYOMTATÁSI STÍLUS BEÁLLÍTÁSA ---
st.markdown("""
    <style>
    @media print {
        .stButton, .stFileUploader, [data-testid="stSidebar"], .stDownloadButton {
            display: none !important;
        }
        .main {
            padding: 0 !important;
        }
    }
    </style>
""", unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Beállítások")
    openai_api_key = st.text_input("OpenAI API Key", type="password")
    uploaded_file = st.file_uploader("CSV feltöltése", type="csv")
    nyomtatas_mod = st.checkbox("Nyomtatási nézet (gombok elrejtése)")

# --- FIX ADATOK ---
SZARAZ_LISTA = ['509496007', '509500001', '509502005', '524145003', '524149001']
RAKLAP_KOD = '146'

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file, sep=';', decimal=',', encoding='latin-1')
        df = df[df['ST_CIKKSZAM'].astype(str).str.strip() != RAKLAP_KOD]
        df['SF_TELJ'] = pd.to_datetime(df['SF_TELJ'])
        df['Honap'] = df['SF_TELJ'].dt.strftime('%Y-%m')
        df['Kategória'] = df['ST_CIKKSZAM'].apply(lambda x: "Száraz áru" if str(x).strip() in SZARAZ_LISTA else "Friss áru")

        # Cím a nyomtatáshoz
        st.title("📊 Havi Forgalmi Jelentés")
        st.write(f"Készült: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}")

        # SZŰRŐK (Csak ha nincs nyomtatási módban)
        if not nyomtatas_mod:
            col1, col2 = st.columns(2)
            partnerek = ["Összes partner"] + sorted(df['SF_UGYFELNEV'].unique().tolist())
            v_partner = col1.selectbox("Partner:", partnerek)
            v_kat = col2.multiselect("Válogatás:", ["Friss áru", "Száraz áru"], default=["Friss áru", "Száraz áru"])
        else:
            v_partner = "Összes partner"
            v_kat = ["Friss áru", "Száraz áru"]

        # Adat szűrése
        f_df = df[df['Kategória'].isin(v_kat)]
        if v_partner != "Összes partner":
            f_df = f_df[f_df['SF_UGYFELNEV'] == v_partner]

        # KPI - Nyomtatásnál fontos az elrendezés
        m1, m2, m3 = st.columns(3)
        m1.metric("Mennyiség (db)", f"{f_df['ST_MENNY'].sum():,.0f}".replace(",", " "))
        m2.metric("Nettó (Ft)", f"{f_df['ST_NEFT'].sum():,.0f}".replace(",", " "))
        
        # Trend
        havi_osszesito = f_df.groupby('Honap')['ST_MENNY'].sum()
        if len(havi_osszesito) > 1:
            valtozas = ((havi_osszesito.iloc[-1] / havi_osszesito.iloc[-2]) - 1) * 100
            m3.metric("Trend", f"{valtozas:+.1f}%")

        # GRAFIKONOK - A4 szélességre igazítva
        st.subheader("Forgalmi statisztika")
        chart_data = f_df.groupby(['Honap', 'Kategória'])['ST_MENNY'].sum().reset_index()
        fig = px.bar(chart_data, x='Honap', y='ST_MENNY', color='Kategória', barmode='group', height=400)
        st.plotly_chart(fig, use_container_width=True)

        # AI KÉRDÉSEK (Csak ha nincs nyomtatási módban)
        if not nyomtatas_mod:
            st.divider()
            st.subheader("💬 Kérdezz az AI-tól")
            user_question = st.text_input("Kérdésed az adatokról:")
            if st.button("Kérdés küldése"):
                if openai_api_key:
                    client = OpenAI(api_key=openai_api_key)
                    adat_summary = f_df.groupby(['Honap', 'SF_UGYFELNEV', 'Kategória'])['ST_MENNY'].sum().reset_index().to_string()
                    res = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": f"Adatok: {adat_summary}\nKérdés: {user_question}"}])
                    st.info(res.choices[0].message.content)
                else:
                    st.error("Add meg az API kulcsot!")

        # ADATTÁBLA - Nyomtatásnál a lényeges oszlopok
        st.subheader("Részletes forgalmi adatok")
        st.dataframe(f_df[['SF_TELJ', 'SF_UGYFELNEV', 'ST_CIKKNEV', 'Kategória', 'ST_MENNY', 'ST_NEFT']], use_container_width=True)

        if nyomtatas_mod:
            st.write("---")
            st.write("© 2025 Pékség Management System - Hivatalos riport")

    except Exception as e:
        st.error(f"Hiba: {e}")
