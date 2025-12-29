import streamlit as st
import pandas as pd
import plotly.express as px
from openai import OpenAI
import datetime

# --- 1. KONFIGURÁCIÓ ---
HIVATALOS_JELSZO = "Velencei670905" 
st.set_page_config(page_title="Pékség Dashboard 2025", layout="wide", page_icon="🥐")

# Nyomtatási stílus és UI finomítás
st.markdown("""
    <style>
    @media print {
        .stButton, .stFileUploader, [data-testid="stSidebar"], .stDownloadButton { display: none !important; }
        .main { padding: 0 !important; }
    }
    /* Kártyák stílusa */
    div[data-testid="metric-container"] {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 10px;
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
def load_data(uploaded_files):
    all_dfs = []
    for file in uploaded_files:
        try:
            # Beolvasás latin-1 kódolással és pontos elválasztókkal
            temp_df = pd.read_csv(file, sep=';', decimal=',', encoding='latin-1')
            all_dfs.append(temp_df)
        except Exception as e:
            st.error(f"Hiba a(z) {file.name} fájl beolvasásakor: {e}")
    
    if not all_dfs:
        return None
    
    # Több fájl összefűzése
    df = pd.concat(all_dfs, ignore_index=True)
    
    # Adattisztítás
    df['ST_CIKKSZAM'] = df['ST_CIKKSZAM'].astype(str).str.strip()
    df = df[df['ST_CIKKSZAM'] != '146'] # Raklap szűrés
    
    # Dátumok felismerése (többféle formátumot is kezel)
    df['SF_TELJ'] = pd.to_datetime(df['SF_TELJ'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['SF_TELJ']) # Hibás dátumok törlése
    
    df['Honap_Nev'] = df['SF_TELJ'].dt.strftime('%Y-%m')
    df['Kategória'] = df['ST_CIKKSZAM'].apply(lambda x: "Száraz áru" if x in SZARAZ_LISTA else "Friss áru")
    return df

# --- 4. OLDALSÁV ---
with st.sidebar:
    st.header("⚙️ Beállítások")
    # Több fájl kijelölése engedélyezve
    uploaded_files = st.file_uploader("CSV fájlok feltöltése", type="csv", accept_multiple_files=True)
    api_key = st.text_input("OpenAI API Key (opcionális)", type="password")
    st.divider()
    if st.button("Kijelentkezés"):
        st.session_state["bejelentkezve"] = False
        st.rerun()

# --- 5. FŐOLDAL ---
if uploaded_files:
    df = load_data(uploaded_files)
    
    if df is not None:
        st.title("📊 Pékség Forgalmi Jelentés")
        
        # --- SZŰRŐK ---
        st.subheader("🔍 Szűrési feltételek")
        
        # 1. sor: Partner, Kategória, Cikkszám
        c1, c2, c3 = st.columns(3)
        partnerek = ["Összes partner"] + sorted(df['SF_UGYFELNEV'].unique().tolist())
        v_partner = c1.selectbox("Partner választása:", partnerek)
        
        v_kat = c2.multiselect("Kategória:", ["Friss áru", "Száraz áru"], default=["Friss áru", "Száraz áru"])
        
        cikkszamok = sorted(df['ST_CIKKSZAM'].unique().tolist())
        v_cikkszam = c3.multiselect("Cikkszám szerinti szűrés:", cikkszamok)
        
        # 2. sor: Naptári intervallum
        min_d = df['SF_TELJ'].min().date()
        max_d = df['SF_TELJ'].max().date()
        
        st.write("📅 **Időszak kiválasztása (Tól - Ig):**")
        date_range = st.date_input(
            "Válassz intervallumot:",
            value=(min_d, max_d),
            min_value=min_d,
            max_value=max_d,
            label_visibility="collapsed"
        )

        # --- SZŰRÉS VÉGREHAJTÁSA ---
        f_df = df.copy()
        
        # Dátum szűrés (biztonságos kezelés ha csak egy dátum van kijelölve)
        if isinstance(date_range, tuple) and len(date_range) == 2:
            start, end = date_range
            f_df = f_df[(f_df['SF_TELJ'].dt.date >= start) & (f_df['SF_TELJ'].dt.date <= end)]
        
        # Kategória szűrés
        if v_kat:
            f_df = f_df[f_df['Kategória'].isin(v_kat)]
        
        # Partner szűrés
        if v_partner != "Összes partner":
            f_df = f_df[f_df['SF_UGYFELNEV'] == v_partner]
            
        # Cikkszám szűrés
        if v_cikkszam:
            f_df = f_df[f_df['ST_CIKKSZAM'].isin(v_cikkszam)]

        # --- 6. KPI MUTATÓK ---
        if not f_df.empty:
            st.divider()
            m1, m2, m3 = st.columns(3)
            osszes_menny = f_df['ST_MENNY'].sum()
            osszes_netto = f_df['ST_NEFT'].sum()
            napok = f_df['SF_TELJ'].dt.date.nunique()
            
            m1.metric("Összes mennyiség", f"{osszes_menny:,.0f}".replace(",", " ") + " db")
            m2.metric("Nettó árbevétel", f"{osszes_netto:,.0f}".replace(",", " ") + " Ft")
            
            napi_avg = osszes_netto / napok if napok > 0 else 0
            m3.metric("Napi átlag bevétel", f"{napi_avg:,.0f}".replace(",", " ") + " Ft")

            # --- 7. VIZUALIZÁCIÓ ---
            st.subheader("📈 Forgalom alakulása")
            # Dinamikus bontás: kevés nap esetén napi, egyébként havi
            bontas = 'SF_TELJ' if napok < 45 else 'Honap_Nev'
            
            chart_data = f_df.groupby([bontas, 'Kategória'])['ST_MENNY'].sum().reset_index()
            fig = px.bar(chart_data, x=bontas, y='ST_MENNY', color='Kategória', 
                         barmode='group', color_discrete_map={"Friss áru": "#ef553b", "Száraz áru": "#636efa"})
            st.plotly_chart(fig, use_container_width=True)

            # --- 8. ADATTÁBLA ---
            st.subheader("📋 Részletes adatok listája")
            st.dataframe(
                f_df[['SF_TELJ', 'SF_UGYFELNEV', 'ST_CIKKSZAM', 'ST_CIKKNEV', 'ST_MENNY', 'ST_NEFT']].sort_values('SF_TELJ'), 
                use_container_width=True,
                hide_index=True
            )
            
            # --- 9. AI ELEMZÉS ---
            if api_key:
                with st.expander("💬 AI Adatelemző Asszisztens"):
                    user_q = st.text_input("Kérdezz az adatokról (pl. Melyik partner vette a legtöbb kiflit?):")
                    if st.button("Elemzés futtatása"):
                        client = OpenAI(api_key=api_key)
                        # Aggregált adatok küldése a tokentakarékosság miatt
                        summary = f_df.groupby(['ST_CIKKNEV'])['ST_MENNY'].sum().sort_values(ascending=False).head(15).to_string()
                        res = client.chat.completions.create(
                            model="gpt-4o",
                            messages=[{"role": "system", "content": "Te egy pékségi üzleti elemző vagy. Válaszolj tömören."},
                                      {"role": "user", "content": f"Adatok:\n{summary}\n\nKérdés: {user_q}"}]
                        )
                        st.info(res.choices[0].message.content)
        else:
            st.warning("⚠️ Nincs megjeleníthető adat a választott szűrőkkel. Kérlek módosítsd a feltételeket!")

else:
    st.info("👋 Üdvözöllek! Kérlek, töltsd fel a CSV fájlokat (akár többet is egyszerre) a bal oldali sávban a kezdéshez.")
