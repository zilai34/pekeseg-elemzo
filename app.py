import streamlit as st
import pandas as pd
import plotly.express as px
from openai import OpenAI

# --- ALAPBEÁLLÍTÁSOK ---
HIVATALOS_JELSZO = "Velencei670905"
SZARAZ_LISTA = ['509496007', '509500001', '509502005', '524145003', '524149001']
RAKLAP_KOD = '146'

st.set_page_config(page_title="Pékség Éves és Havi Dashboard", layout="wide")

# --- JELSZAVAS BELÉPÉS ---
if "bejelentkezve" not in st.session_state:
    st.session_state["bejelentkezve"] = False

if not st.session_state["bejelentkezve"]:
    st.title("🔐 Bejelentkezés")
    jelszo_input = st.text_input("Add meg a jelszót:", type="password")
    if st.button("Belépés"):
        if jelszo_input == HIVATALOS_JELSZO:
            st.session_state["bejelentkezve"] = True
            st.rerun()
        else:
            st.error("Hibás jelszó!")
    st.stop()

# --- NYOMTATÁSI STÍLUS ---
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

# --- SIDEBAR (BEÁLLÍTÁSOK) ---
with st.sidebar:
    st.header("⚙️ Beállítások")
    openai_api_key = st.text_input("OpenAI API Key", type="password")
    # TÖMEGES FELTÖLTÉS ENGEDÉLYEZÉSE
    uploaded_files = st.file_uploader("Töltsd fel a CSV fájlokat (akár többet is!)", type="csv", accept_multiple_files=True)
    nyomtatas_mod = st.checkbox("🖨️ Nyomtatási nézet (A4)")

# --- ADATFELDOLGOZÁS ---
if uploaded_files:
    try:
        data_list = []
        for file in uploaded_files:
            temp_df = pd.read_csv(file, sep=';', decimal=',', encoding='latin-1')
            data_list.append(temp_df)
        
        # Fájlok összefűzése
        df = pd.concat(data_list, ignore_index=True)
        # Duplikációk szűrése (ha véletlenül ugyanaz a sor többször szerepel)
        df = df.drop_duplicates()
        
        # Oszlopnév javítás (ST_NE -> ST_NEFT)
        if 'ST_NE' in df.columns and 'ST_NEFT' not in df.columns:
            df = df.rename(columns={'ST_NE': 'ST_NEFT'})
        
        # Raklap törlése
        df = df[df['ST_CIKKSZAM'].astype(str).str.strip() != RAKLAP_KOD]
        
        # Időkezelés
        df['SF_TELJ'] = pd.to_datetime(df['SF_TELJ'], errors='coerce')
        df = df.dropna(subset=['SF_TELJ'])
        df['Ev'] = df['SF_TELJ'].dt.year.astype(str)
        df['Honap'] = df['SF_TELJ'].dt.strftime('%Y-%m')
        
        # Kategorizálás
        df['Kategória'] = df['ST_CIKKSZAM'].apply(lambda x: "Száraz áru" if str(x).strip() in SZARAZ_LISTA else "Friss áru")

        st.title("📊 Pékség Éves és Havi Forgalmi Elemző")

        # SZŰRŐK
        if not nyomtatas_mod:
            c1, c2, c3 = st.columns(3)
            v_ev = c1.multiselect("Év kiválasztása:", sorted(df['Ev'].unique()), default=sorted(df['Ev'].unique()))
            v_partner = c2.selectbox("Partner választása:", ["Összes partner"] + sorted(df['SF_UGYFELNEV'].unique().tolist()))
            v_kat = c3.multiselect("Kategória:", ["Friss áru", "Száraz áru"], default=["Friss áru", "Száraz áru"])
        else:
            v_ev, v_partner, v_kat = sorted(df['Ev'].unique()), "Összes partner", ["Friss áru", "Száraz áru"]

        # Adatok szűrése
        f_df = df[(df['Kategória'].isin(v_kat)) & (df['Ev'].isin(v_ev))]
        if v_partner != "Összes partner":
            f_df = f_df[f_df['SF_UGYFELNEV'] == v_partner]

        # --- KPI MUTATÓK ---
        st.divider()
        m1, m2, m3 = st.columns(3)
        m1.metric("Időszaki mennyiség", f"{f_df['ST_MENNY'].sum():,.0f} db".replace(",", " "))
        m2.metric("Nettó forgalom", f"{f_df['ST_NEFT'].sum():,.0f} Ft".replace(",", " "))
        
        # Éves és havi bontású grafikon
        st.subheader("Forgalom alakulása időrendben (Havi bontás)")
        chart_data = f_df.groupby(['Honap', 'Kategória'])['ST_MENNY'].sum().reset_index()
        fig = px.bar(chart_data, x='Honap', y='ST_MENNY', color='Kategória', barmode='group')
        st.plotly_chart(fig, use_container_width=True)

        # --- ÉVES ÖSSZESÍTŐ TÁBLA ---
        st.subheader("Éves összesítés kategóriánként")
        eves_osszesito = f_df.groupby(['Ev', 'Kategória'])[['ST_MENNY', 'ST_NEFT']].sum().reset_index()
        st.table(eves_osszesito)

        # --- AI CHAT (ÉVES ELEMZÉSSEL) ---
        if not nyomtatas_mod:
            st.divider()
            st.subheader("💬 AI Üzleti Tanácsadó (Éves és Havi)")
            user_question = st.text_input("Kérdezz bármit az éves trendekről:")

            if st.button("Elemzés indítása"):
                if not openai_api_key:
                    st.error("Add meg az OpenAI API kulcsot!")
                elif user_question:
                    client = OpenAI(api_key=openai_api_key)
                    with st.spinner("Az AI átnézi a teljes időszakot..."):
                        # Az AI-nak most már az éves adatokat is elküldjük
                        summary = f_df.groupby(['Ev', 'Honap', 'Kategória'])['ST_MENNY'].sum().reset_index().to_string()
                        prompt = f"Pékség adatai:\n{summary}\n\nKérdés: {user_question}\n\nVálaszolj magyarul, elemezd az éves változásokat is."
                        
                        response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
                        st.info(response.choices[0].message.content)

                        # Éves tortadiagram
                        st.write("### 📈 Partneri megoszlás a teljes időszakban")
                        partner_share = f_df.groupby('SF_UGYFELNEV')['ST_MENNY'].sum().sort_values(ascending=False).head(10).reset_index()
                        st.plotly_chart(px.pie(partner_share, values='ST_MENNY', names='SF_UGYFELNEV'), use_container_width=True)

        # Részletes adatok táblázat
        st.subheader("Nyers adatok")
        st.dataframe(f_df[['SF_TELJ', 'SF_UGYFELNEV', 'ST_CIKKNEV', 'Kategória', 'ST_MENNY', 'ST_NEFT']], use_container_width=True)

    except Exception as e:
        st.error(f"Hiba történt: {e}")
else:
    st.info("👋 Üdvözöllek! Húzd be a CSV fájlokat (akár többet is) a bal oldali sávba!")
