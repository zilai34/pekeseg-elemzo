import streamlit as st
import pandas as pd
import plotly.express as px
from openai import OpenAI

# --- ALAPBEÁLLÍTÁSOK ---
HIVATALOS_JELSZO = "Velencei670905"
SZARAZ_LISTA = ['509496007', '509500001', '509502005', '524145003', '524149001']
RAKLAP_KOD = '146'

st.set_page_config(page_title="Pékség Vezetői Dashboard", layout="wide")

# --- JELSZAVAS BELÉPÉS ---
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

# --- NYOMTATÁSI STÍLUS (A4 OPTIMALIZÁLÁS) ---
st.markdown("""
    <style>
    @media print {
        .stButton, .stFileUploader, [data-testid="stSidebar"], .stDownloadButton, .stCheckbox {
            display: none !important;
        }
        .main { padding: 0 !important; }
    }
    </style>
""", unsafe_allow_html=True)

# --- SIDEBAR (BEÁLLÍTÁSOK) ---
with st.sidebar:
    st.header("⚙️ Beállítások")
    openai_api_key = st.text_input("OpenAI API Key", type="password", help="Másold be az API kulcsodat")
    uploaded_file = st.file_uploader("Töltsd fel az SQL1 (1).csv fájlt", type="csv")
    nyomtatas_mod = st.checkbox("🖨️ Nyomtatási nézet bekapcsolása")

# --- ADATFELDOLGOZÁS ---
if uploaded_file:
    try:
        # Beolvasás (latin-1 az ékezetek miatt)
        df = pd.read_csv(uploaded_file, sep=';', decimal=',', encoding='latin-1')
        
        # 1. Raklap kiszűrése
        df = df[df['ST_CIKKSZAM'].astype(str).str.strip() != RAKLAP_KOD]
        
        # 2. Dátumok kezelése
        df['SF_TELJ'] = pd.to_datetime(df['SF_TELJ'])
        df['Honap'] = df['SF_TELJ'].dt.strftime('%Y-%m')
        
        # 3. Kategorizálás (Friss / Száraz)
        df['Kategória'] = df['ST_CIKKSZAM'].apply(lambda x: "Száraz áru" if str(x).strip() in SZARAZ_LISTA else "Friss áru")

        # --- FŐOLDAL MEGJELENÍTÉSE ---
        st.title("📊 Pékség Forgalmi Elemző")
        st.write(f"Jelentés dátuma: {pd.Timestamp.now().strftime('%Y-%m-%d')}")

        # SZŰRŐK (Csak ha nem nyomtatunk)
        if not nyomtatas_mod:
            col1, col2 = st.columns(2)
            partnerek = ["Összes partner"] + sorted(df['SF_UGYFELNEV'].unique().tolist())
            v_partner = col1.selectbox("Válassz partnert:", partnerek)
            v_kat = col2.multiselect("Kategória választás:", ["Friss áru", "Száraz áru"], default=["Friss áru", "Száraz áru"])
        else:
            v_partner = "Összes partner"
            v_kat = ["Friss áru", "Száraz áru"]

        # Adatok szűrése a választás alapján
        f_df = df[df['Kategória'].isin(v_kat)]
        if v_partner != "Összes partner":
            f_df = f_df[f_df['SF_UGYFELNEV'] == v_partner]

        # --- KPI MUTATÓK ---
        st.divider()
        m1, m2, m3 = st.columns(3)
        total_menny = f_df['ST_MENNY'].sum()
        total_ertek = f_df['ST_NEFT'].sum()
        m1.metric("Összes mennyiség", f"{total_menny:,.0f} db".replace(",", " "))
        m2.metric("Nettó árbevétel", f"{total_ertek:,.0f} Ft".replace(",", " "))
        
        # Havi trend számítása
        havi_statisztika = f_df.groupby('Honap')['ST_MENNY'].sum()
        if len(havi_statisztika) > 1:
            trend = ((havi_statisztika.iloc[-1] / havi_statisztika.iloc[-2]) - 1) * 100
            m3.metric("Forgalmi trend", f"{trend:+.1f}%")

        # --- ALAP GRAFIKON ---
        st.subheader("Havi eloszlás (Friss vs Száraz)")
        chart_data = f_df.groupby(['Honap', 'Kategória'])['ST_MENNY'].sum().reset_index()
        fig = px.bar(chart_data, x='Honap', y='ST_MENNY', color='Kategória', barmode='group', height=400)
        st.plotly_chart(fig, use_container_width=True)

        # --- AI KÉRDÉSEK ÉS DINAMIKUS GRAFIKON ---
        if not nyomtatas_mod:
            st.divider()
            st.subheader("💬 Okos AI Elemző")
            st.write("Kérdezz bármit az adatokról (pl. 'Melyik 3 cég vitte a legtöbb árut?')")
            user_question = st.text_input("Írd ide a kérdésed:")

            if st.button("Kérdés küldése"):
                if not openai_api_key:
                    st.error("Kérlek, add meg az OpenAI API kulcsot a bal oldalon!")
                elif user_question:
                    client = OpenAI(api_key=openai_api_key)
                    with st.spinner("Az AI elemzi az adatokat..."):
                        # Adat összefoglaló az AI-nak
                        ai_data = f_df.groupby(['SF_UGYFELNEV', 'Kategória'])['ST_MENNY'].sum().reset_index()
                        prompt = f"Adatok:\n{ai_data.to_string()}\n\nKérdés: {user_question}\n\nVálaszolj magyarul."
                        
                        response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
                        st.info(response.choices[0].message.content)

                        # DINAMIKUS GRAFIKON A VÁLASZ MELLÉ
                        st.write("### 📈 Vizualizáció a kérdéshez")
                        top_10 = f_df.groupby('SF_UGYFELNEV')['ST_MENNY'].sum().sort_values(ascending=False).head(10).reset_index()
                        fig_ai = px.pie(top_10, values='ST_MENNY', names='SF_UGYFELNEV', title="Top 10 Partner megoszlása (db)")
                        st.plotly_chart(fig_ai, use_container_width=True)

        # --- ADATTÁBLA ---
        st.subheader("Részletes forgalmi lista")
        st.dataframe(f_df[['SF_TELJ', 'SF_UGYFELNEV', 'ST_CIKKNEV', 'Kategória', 'ST_MENNY', 'ST_NEFT']], use_container_width=True)
        
        # Letöltés gomb
        csv = f_df.to_csv(index=False, sep=';').encode('latin-1')
        st.download_button("📥 Adatok letöltése (CSV)", csv, "pekség_riport.csv", "text/csv")

    except Exception as e:
        st.error(f"Hiba történt a feldolgozás során: {e}")
else:
    st.info("Üdvözöllek! Töltsd fel a CSV fájlt a bal oldali menüben a kezdéshez.")
