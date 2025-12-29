import streamlit as st
import pandas as pd
import plotly.express as px
from openai import OpenAI
import datetime

# --- 1. KONFIGURÁCIÓ ÉS STÍLUS ---
HIVATALOS_JELSZO = "Velencei670905" 
st.set_page_config(page_title="Pékség Dashboard 2025", layout="wide", page_icon="🥐")

# Nyomtatási stílus és UI finomítás
st.markdown("""
    <style>
    @media print {
        .stButton, .stFileUploader, [data-testid="stSidebar"], .stDownloadButton { display: none !important; }
        .main { padding: 0 !important; }
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. BELÉPÉS ---
if "bejelentkezve" not in st.session_state:
    st.session_state["bejelentkezve"] = False

if not st.session_state["bejelentkezve"]:
    st.title("🔐 Bejelentkezés")
    with st.form("login"):
        jelszo = st.text_input("Jelszó:", type="password")
        if st.form_submit_button("Belépés"):
            if jelszo == HIVATALOS_JELSZO:
                st.session_state["bejelentkezve"] = True
                st.rerun()
            else: st.error("Hibás jelszó!")
    st.stop()

# --- 3. ADATKEZELÉS ---
SZARAZ_LISTA = ['509496007', '509500001', '509502005', '524145003', '524149001']

@st.cache_data
def load_data(file):
    # Betöltés latin-1 kódolással az ékezetek miatt
    df = pd.read_csv(file, sep=';', decimal=',', encoding='latin-1')
    # Cikkszám tisztítás (szóközök eltávolítása)
    df['ST_CIKKSZAM'] = df['ST_CIKKSZAM'].astype(str).str.strip()
    # Raklapok kiszűrése (146-os kód)
    df = df[df['ST_CIKKSZAM'] != '146']
    # Dátumok konvertálása
    df['SF_TELJ'] = pd.to_datetime(df['SF_TELJ'])
    df['Honap_Nev'] = df['SF_TELJ'].dt.strftime('%Y-%m')
    # Kategorizálás a fix lista alapján
    df['Kategória'] = df['ST_CIKKSZAM'].apply(lambda x: "Száraz áru" if x in SZARAZ_LISTA else "Friss áru")
    return df

# --- 4. OLDALSÁV (SIDEBAR) ---
with st.sidebar:
    st.header("⚙️ Beállítások")
    uploaded_file = st.file_uploader("CSV fájl feltöltése", type="csv")
    api_key = st.text_input("OpenAI API Key (opcionális)", type="password")
    st.divider()
    if st.button("Kijelentkezés"):
        st.session_state["bejelentkezve"] = False
        st.rerun()

# --- 5. FŐOLDAL ÉS SZŰRŐK ---
if uploaded_file:
    df = load_data(uploaded_file)
    
    st.title("📊 Pékség Forgalmi Jelentés")
    st.subheader("🔍 Szűrési feltételek")
    
    # Szűrő sor 1: Partner, Kategória, Cikkszám
    c1, c2, c3 = st.columns(3)
    
    partnerek = ["Összes partner"] + sorted(df['SF_UGYFELNEV'].unique().tolist())
    v_partner = c1.selectbox("Partner választása:", partnerek, index=0)
    
    v_kat = c2.multiselect("Kategória:", ["Friss áru", "Száraz áru"], default=["Friss áru", "Száraz áru"])
    
    cikkszamok = sorted(df['ST_CIKKSZAM'].unique().tolist())
    v_cikkszam = c3.multiselect("Cikkszám szerinti szűrés:", cikkszamok)
    
    # Szűrő sor 2: Naptári intervallum
    min_date = df['SF_TELJ'].min().to_pydatetime()
    max_date = df['SF_TELJ'].max().to_pydatetime()
    
    st.write("📅 **Időszak kiválasztása (Tól - Ig):**")
    date_range = st.date_input(
        "Intervallum:",
        value=(datetime.date(2025, 1, 1), datetime.date.today()),
        min_value=min_date,
        max_value=max_date,
        label_visibility="collapsed"
    )

    # --- ADATOK SZŰRÉSE ---
    # Dátum szűrés
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        f_df = df[(df['SF_TELJ'].dt.date >= start_date) & (df['SF_TELJ'].dt.date <= end_date)]
    else:
        f_df = df

    # Kategória szűrés
    f_df = f_df[f_df['Kategória'].isin(v_kat)]
    
    # Partner szűrés
    if v_partner != "Összes partner":
        f_df = f_df[f_df['SF_UGYFELNEV'] == v_partner]
        
    # Cikkszám szűrés
    if v_cikkszam:
        f_df = f_df[f_df['ST_CIKKSZAM'].isin(v_cikkszam)]

    # --- 6. KPI MUTATÓK ---
    st.divider()
    m1, m2, m3 = st.columns(3)
    m1.metric("Szűrt mennyiség", f"{f_df['ST_MENNY'].sum():,.0f}".replace(",", " ") + " db")
    m2.metric("Nettó árbevétel", f"{f_df['ST_NEFT'].sum():,.0f}".replace(",", " ") + " Ft")
    
    napok_szama = f_df['SF_TELJ'].dt.date.nunique()
    if napok_szama > 0:
        napi_atlag = f_df['ST_NEFT'].sum() / napok_szama
        m3.metric("Napi átlag bevétel", f"{napi_atlag:,.0f}".replace(",", " ") + " Ft")
    else:
        m3.metric("Napi átlag", "0 Ft")

    # --- 7. VIZUALIZÁCIÓ ---
    st.subheader("📈 Forgalom alakulása")
    if not f_df.empty:
        # Ha 45 napnál kevesebb, akkor napi, különben havi bontás
        bontas = 'SF_TELJ' if napok_szama < 45 else 'Honap_Nev'
        chart_data = f_df.groupby([bontas, 'Kategória'])['ST_MENNY'].sum().reset_index()
        fig = px.bar(chart_data, x=bontas, y='ST_MENNY', color='Kategória', 
                     barmode='group', color_discrete_map={"Friss áru": "#ef553b", "Száraz áru": "#636efa"})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Nincs adat a választott szűrőkkel.")

    # --- 8. ADATTÁBLA ---
    st.subheader("📋 Részletes adatok")
    st.dataframe(f_df[['SF_TELJ', 'SF_UGYFELNEV', 'ST_CIKKSZAM', 'ST_CIKKNEV', 'ST_MENNY', 'ST_NEFT']].sort_values('SF_TELJ'), use_container_width=True)

    # --- 9. AI (OPCIONÁLIS) ---
    if api_key and not f_df.empty:
        with st.expander("💬 AI Elemzés"):
            user_q = st.text_input("Kérdés az AI-hoz:")
            if st.button("Küldés"):
                client = OpenAI(api_key=api_key)
                summary = f_df.groupby('ST_CIKKNEV')['ST_MENNY'].sum().head(10).to_string()
                res = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": f"Adatok: {summary}\nKérdés: {user_q}"}]
                )
                st.info(res.choices[0].message.content)

else:
    st.info("👋 Kérlek, töltsd fel a CSV fájlt a bal oldali menüben!")
