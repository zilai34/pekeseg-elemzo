import streamlit as st
import pandas as pd
import plotly.express as px
from openai import OpenAI
import datetime

# --- 1. KONFIGURÁCIÓ ---
HIVATALOS_JELSZO = "Velencei670905" 
st.set_page_config(page_title="Pékség Dashboard 2025", layout="wide", page_icon="🥐")

# Automatikus API kulcs betöltése a Secrets-ből
# Ha nincs beállítva, None marad, és az AI funkció rejtve marad
try:
    openai_api_key = st.secrets["OPENAI_API_KEY"]
except:
    openai_api_key = None

st.markdown("""
    <style>
    @media print {
        .stButton, .stFileUploader, [data-testid="stSidebar"], .stDownloadButton { display: none !important; }
        .main { padding: 0 !important; }
    }
    div[data-testid="metric-container"] {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 10px;
        border: 1px solid #e0e0e0;
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
            temp_df = pd.read_csv(file, sep=';', decimal=',', encoding='latin-1')
            all_dfs.append(temp_df)
        except Exception as e:
            st.error(f"Hiba a(z) {file.name} fájl beolvasásakor: {e}")
    
    if not all_dfs:
        return None
    
    df = pd.concat(all_dfs, ignore_index=True)
    df['ST_CIKKSZAM'] = df['ST_CIKKSZAM'].astype(str).str.strip()
    df = df[df['ST_CIKKSZAM'] != '146'] 
    
    df['SF_TELJ'] = pd.to_datetime(df['SF_TELJ'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['SF_TELJ']) 
    
    df['Honap_Nev'] = df['SF_TELJ'].dt.strftime('%Y-%m')
    df['Kategória'] = df['ST_CIKKSZAM'].apply(lambda x: "Száraz áru" if x in SZARAZ_LISTA else "Friss áru")
    df['Cikkszam_Nev'] = df['ST_CIKKSZAM'] + " - " + df['ST_CIKKNEV'].astype(str)
    
    return df

# --- 4. OLDALSÁV ---
with st.sidebar:
    st.header("⚙️ Beállítások")
    uploaded_files = st.file_uploader("CSV fájlok feltöltése", type="csv", accept_multiple_files=True)
    
    # Ha nincs kulcs a secrets-ben, itt még mindig megadható kézzel (biztonsági tartalék)
    if not openai_api_key:
        openai_api_key = st.text_input("OpenAI API Key (Kézi megadás)", type="password")
    else:
        st.success("✅ OpenAI API kulcs betöltve")

    st.divider()
    if st.button("Kijelentkezés"):
        st.session_state["bejelentkezve"] = False
        st.rerun()

# --- 5. FŐOLDAL ÉS SZŰRŐK ---
if uploaded_files:
    df = load_data(uploaded_files)
    
    if df is not None:
        st.title("📊 Pékség Forgalmi Jelentés")
        st.subheader("🔍 Szűrési feltételek")
        
        c1, c2, c3 = st.columns(3)
        partnerek = ["Összes partner"] + sorted(df['SF_UGYFELNEV'].unique().tolist())
        v_partner = c1.selectbox("Partner választása:", partnerek)
        
        v_kat = c2.multiselect("Kategória:", ["Friss áru", "Száraz áru"], default=["Friss áru", "Száraz áru"])
        
        cikkszam_lista = sorted(df['Cikkszam_Nev'].unique().tolist())
        v_cikkszam_nev = c3.multiselect("Cikkszám és név szerinti szűrés:", cikkszam_lista)
        
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
        
        if isinstance(date_range, tuple) and len(date_range) == 2:
            start, end = date_range
            f_df = f_df[(f_df['SF_TELJ'].dt.date >= start) & (f_df['SF_TELJ'].dt.date <= end)]
        
        if v_kat:
            f_df = f_df[f_df['Kategória'].isin(v_kat)]
        
        if v_partner != "Összes partner":
            f_df = f_df[f_df['SF_UGYFELNEV'] == v_partner]
            
        if v_cikkszam_nev:
            f_df = f_df[f_df['Cikkszam_Nev'].isin(v_cikkszam_nev)]

        # --- 6. KPI ÉS MEGJELENÍTÉS ---
        if not f_df.empty:
            st.divider()
            m1, m2, m3 = st.columns(3)
            osszes_menny = f_df['ST_MENNY'].sum()
            osszes_netto = f_df['ST_NEFT'].sum()
            napok = f_df['SF_TELJ'].dt.date.nunique()
            
            m1.metric("Szűrt mennyiség", f"{osszes_menny:,.0f}".replace(",", " ") + " db")
            m2.metric("Nettó árbevétel", f"{osszes_netto:,.0f}".replace(",", " ") + " Ft")
            
            napi_avg = osszes_netto / napok if napok > 0 else 0
            m3.metric("Napi átlag bevétel", f"{napi_avg:,.0f}".replace(",", " ") + " Ft")

            st.subheader("📈 Forgalom alakulása")
            bontas = 'SF_TELJ' if napok < 45 else 'Honap_Nev'
            chart_data = f_df.groupby([bontas, 'Kategória'])['ST_MENNY'].sum().reset_index()
            fig = px.bar(chart_data, x=bontas, y='ST_MENNY', color='Kategória', 
                         barmode='group', color_discrete_map={"Friss áru": "#ef553b", "Száraz áru": "#636efa"})
            st.plotly_chart(fig, use_container_width=True)

            st.subheader("📋 Részletes adatok")
            st.dataframe(
                f_df[['SF_TELJ', 'SF_UGYFELNEV', 'ST_CIKKSZAM', 'ST_CIKKNEV', 'ST_MENNY', 'ST_NEFT']].sort_values('SF_TELJ'), 
                use_container_width=True,
                hide_index=True
            )
            
            # AI rész csak akkor jelenik meg, ha van kulcs
            if openai_api_key:
                with st.expander("💬 AI Adatelemző Asszisztens"):
                    user_q = st.text_input("Kérdezz az adatokról:")
                    if st.button("Küldés"):
                        try:
                            client = OpenAI(api_key=openai_api_key)
                            summary = f_df.groupby(['ST_CIKKNEV'])['ST_MENNY'].sum().sort_values(ascending=False).head(15).to_string()
                            res = client.chat.completions.create(
                                model="gpt-4o",
                                messages=[{"role": "system", "content": "Te egy pékségi üzleti elemző vagy. Válaszolj tömören."},
                                          {"role": "user", "content": f"Adatok:\n{summary}\n\nKérdés: {user_q}"}]
                            )
                            st.info(res.choices[0].message.content)
                        except Exception as e:
                            st.error(f"AI hiba: {e}")
        else:
            st.warning("Nincs adat a választott szűrőkkel.")
else:
    st.info("👋 Töltsd fel a CSV fájlokat a kezdéshez!")
