import streamlit as st
import pandas as pd
import plotly.express as px
from openai import OpenAI

# --- BEÁLLÍTÁSOK ---
# Ez a jelszó, amit kérni fog az oldal
HIVATALOS_JELSZO = "Velencei670905" 
SZARAZ_LISTA = ['509496007', '509500001', '509502005', '524145003', '524149001']
RAKLAP_KOD = '146'

st.set_page_config(page_title="Pékség Vezetői Dashboard", layout="wide")

# --- JELSZAVAS BELÉPÉS ---
if "bejelentkezve" not in st.session_state:
    st.session_state["bejelentkezve"] = False

if not st.session_state["bejelentkezve"]:
    st.title("🔐 Bejelentkezés")
    jelszo_input = st.text_input("Add meg a jelszót a belépéshez:", type="password")
    if st.button("Belépés"):
        if jelszo_input == HIVATALOS_JELSZO:
            st.session_state["bejelentkezve"] = True
            st.rerun()
        else:
            st.error("Hibás jelszó!")
    st.stop()

# --- NYOMTATÁSI STÍLUS (A4-HEZ) ---
st.markdown("""
    <style>
    @media print {
        .stButton, .stFileUploader, [data-testid="stSidebar"], .stDownloadButton, .stCheckbox, .stTextInput {
            display: none !important;
        }
        .main { padding: 0 !important; }
    }
    </style>
""", unsafe_allow_html=True)

# --- OLDALSÁV (SIDEBAR) ---
with st.sidebar:
    st.header("⚙️ Beállítások")
    openai_api_key = st.text_input("OpenAI API Key", type="password")
    uploaded_file = st.file_uploader("Töltsd fel a CSV fájlt", type="csv")
    nyomtatas_mod = st.checkbox("🖨️ Nyomtatási nézet (A4)")

# --- ADATFELDOLGOZÁS ---
if uploaded_file:
    try:
        # Beolvasás latin-1 kódolással az ékezetek miatt
        df = pd.read_csv(uploaded_file, sep=';', decimal=',', encoding='latin-1')
        
        # Oszlopnév javítás: ha 'ST_NE' van benne, átnevezzük 'ST_NEFT'-re az egységesség kedvéért
        if 'ST_NE' in df.columns and 'ST_NEFT' not in df.columns:
            df = df.rename(columns={'ST_NE': 'ST_NEFT'})
        
        # Raklap (146) törlése
        df = df[df['ST_CIKKSZAM'].astype(str).str.strip() != RAKLAP_KOD]
        
        # Dátumok kezelése
        df['SF_TELJ'] = pd.to_datetime(df['SF_TELJ'], errors='coerce')
        df = df.dropna(subset=['SF_TELJ'])
        df['Honap'] = df['SF_TELJ'].dt.strftime('%Y-%m')
        
        # Kategorizálás
        df['Kategória'] = df['ST_CIKKSZAM'].apply(lambda x: "Száraz áru" if str(x).strip() in SZARAZ_LISTA else "Friss áru")

        st.title("📊 Pékség Forgalmi Elemző")
        st.write(f"Jelentés dátuma: {pd.Timestamp.now().strftime('%Y-%m-%d')}")

        # Szűrők
        if not nyomtatas_mod:
            col1, col2 = st.columns(2)
            partnerek = ["Összes partner"] + sorted(df['SF_UGYFELNEV'].unique().tolist())
            v_partner = col1.selectbox("Válassz partnert:", partnerek)
            v_kat = col2.multiselect("Kategória választás:", ["Friss áru", "Száraz áru"], default=["Friss áru", "Száraz áru"])
        else:
            v_partner = "Összes partner"
            v_kat = ["Friss áru", "Száraz áru"]

        # Adatok szűrése
        f_df = df[df['Kategória'].isin(v_kat)]
        if v_partner != "Összes partner":
            f_df = f_df[f_df['SF_UGYFELNEV'] == v_partner]

        # Fő mutatók (KPI)
        st.divider()
        m1, m2, m3 = st.columns(3)
        total_menny = f_df['ST_MENNY'].sum()
        total_ertek = f_df['ST_NEFT'].sum()
        m1.metric("Összes mennyiség", f"{total_menny:,.0f} db".replace(",", " "))
        m2.metric("Nettó árbevétel", f"{total_ertek:,.0f} Ft".replace(",", " "))
        
        # Havi trend
        havi_osszesito = f_df.groupby('Honap')['ST_MENNY'].sum()
        if len(havi_osszesito) > 1:
            trend = ((havi_osszesito.iloc[-1] / havi_osszesito.iloc[-2]) - 1) * 100
            m3.metric("Forgalmi trend", f"{trend:+.1f}%")

        # Alap grafikon
        st.subheader("Havi forgalom megoszlása")
        chart_data = f_df.groupby(['Honap', 'Kategória'])['ST_MENNY'].sum().reset_index()
        fig = px.bar(chart_data, x='Honap', y='ST_MENNY', color='Kategória', barmode='group')
        st.plotly_chart(fig, use_container_width=True)

        # AI Chat rész
        if not nyomtatas_mod:
            st.divider()
            st.subheader("💬 Okos AI Elemző")
            user_question = st.text_input("Kérdezz az adatokról (pl. Ki a legnagyobb partnerünk?):")

            if st.button("Kérdés küldése"):
                if not openai_api_key:
                    st.error("Kérlek, add meg az OpenAI API kulcsot a bal oldali sávban!")
                elif user_question:
                    client = OpenAI(api_key=openai_api_key)
                    with st.spinner("Az AI elemzi az adatokat..."):
                        ai_data = f_df.groupby(['SF_UGYFELNEV', 'Kategória'])['ST_MENNY'].sum().reset_index()
                        prompt = f"Adatok:\n{ai_data.to_string()}\n\nKérdés: {user_question}\nVálaszolj magyarul, üzleti szemmel."
                        
                        response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
                        st.info(response.choices[0].message.content)

                        # Tortadiagram a válasz mellé
                        st.write("### 📈 Top 10 Partner megoszlása")
                        top_10 = f_df.groupby('SF_UGYFELNEV')['ST_MENNY'].sum().sort_values(ascending=False).head(10).reset_index()
                        st.plotly_chart(px.pie(top_10, values='ST_MENNY', names='SF_UGYFELNEV'), use_container_width=True)

        # Adattábla
        st.subheader("Részletes adatok")
        st.dataframe(f_df[['SF_TELJ', 'SF_UGYFELNEV', 'ST_CIKKNEV', 'Kategória', 'ST_MENNY', 'ST_NEFT']], use_container_width=True)
        
        # Letöltés
        csv = f_df.to_csv(index=False, sep=';').encode('latin-1')
        st.download_button("📥 Adatok letöltése (CSV)", csv, "riport.csv", "text/csv")

    except Exception as e:
        st.error(f"Hiba történt a feldolgozás során: {e}")
else:
    st.info("Kérlek, töltsd fel a CSV fájlt a bal oldali menüben!")
