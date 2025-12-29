import streamlit as st
import pandas as pd
import plotly.express as px
from openai import OpenAI
import json
import datetime

# --- 1. KONFIGURÁCIÓ ÉS TITKOK ---
HIVATALOS_JELSZO = "Velencei670905" 
st.set_page_config(page_title="Pékség Dashboard AI Pro", layout="wide", page_icon="🥐")

# OpenAI kulcs betöltése
openai_api_key = st.secrets.get("OPENAI_API_KEY")

st.markdown("""
    <style>
    @media print {
        .stButton, .stFileUploader, [data-testid="stSidebar"], .stDownloadButton { display: none !important; }
        .main { padding: 0 !important; }
    }
    div[data-testid="metric-container"] {
        background-color: #f0f2f6;
        padding: 15px;
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
    
    if not all_dfs: return None
    
    df = pd.concat(all_dfs, ignore_index=True)
    df['ST_CIKKSZAM'] = df['ST_CIKKSZAM'].astype(str).str.strip()
    df = df[df['ST_CIKKSZAM'] != '146'] 
    
    df['SF_TELJ'] = pd.to_datetime(df['SF_TELJ'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['SF_TELJ']) 
    
    df['Év'] = df['SF_TELJ'].dt.year
    df['Hónap'] = df['SF_TELJ'].dt.month
    df['Honap_Nev'] = df['SF_TELJ'].dt.strftime('%Y-%m')
    df['Kategória'] = df['ST_CIKKSZAM'].apply(lambda x: "Száraz áru" if x in SZARAZ_LISTA else "Friss áru")
    df['Cikkszam_Nev'] = df['ST_CIKKSZAM'] + " - " + df['ST_CIKKNEV'].astype(str)
    
    return df

# --- 4. OLDALSÁV ---
with st.sidebar:
    st.header("⚙️ Beállítások")
    uploaded_files = st.file_uploader("CSV fájlok feltöltése", type="csv", accept_multiple_files=True)
    
    if openai_api_key:
        st.success("🤖 AI Modul aktív")
    else:
        st.info("ℹ️ AI modul inaktív")

    st.divider()
    if st.button("Kijelentkezés"):
        st.session_state["bejelentkezve"] = False
        st.rerun()

# --- 5. FŐOLDAL ÉS SZŰRŐK ---
if uploaded_files:
    df = load_data(uploaded_files)
    
    if df is not None:
        st.title("📊 Pékség Üzleti Dashboard & AI Műhely")
        
        with st.expander("🔍 Szűrési feltételek", expanded=True):
            c1, c2, c3 = st.columns(3)
            partnerek = ["Összes partner"] + sorted(df['SF_UGYFELNEV'].unique().tolist())
            v_partner = c1.selectbox("Partner választása:", partnerek)
            v_kat = c2.multiselect("Kategória:", ["Friss áru", "Száraz áru"], default=["Friss áru", "Száraz áru"])
            v_cikkszam_nev = c3.multiselect("Termék szerinti szűrés:", sorted(df['Cikkszam_Nev'].unique().tolist()))
            
            min_d, max_d = df['SF_TELJ'].min().date(), df['SF_TELJ'].max().date()
            date_range = st.date_input("Dátum tartomány:", value=(min_d, max_d), min_value=min_d, max_value=max_d)

        f_df = df.copy()
        if isinstance(date_range, tuple) and len(date_range) == 2:
            f_df = f_df[(f_df['SF_TELJ'].dt.date >= date_range[0]) & (f_df['SF_TELJ'].dt.date <= date_range[1])]
        if v_kat: f_df = f_df[f_df['Kategória'].isin(v_kat)]
        if v_partner != "Összes partner": f_df = f_df[f_df['SF_UGYFELNEV'] == v_partner]
        if v_cikkszam_nev: f_df = f_df[f_df['Cikkszam_Nev'].isin(v_cikkszam_nev)]

        if not f_df.empty:
            st.divider()
            m1, m2, m3 = st.columns(3)
            m1.metric("Mennyiség", f"{f_df['ST_MENNY'].sum():,.0f}".replace(",", " ") + " db")
            m2.metric("Nettó árbevétel", f"{f_df['ST_NEFT'].sum():,.0f}".replace(",", " ") + " Ft")
            m3.metric("Aktív napok", f"{f_df['SF_TELJ'].dt.date.nunique()} nap")

            tab_dash, tab_ai = st.tabs(["📈 Trendek & Összehasonlítás", "🤖 AI Stratégiai Műhely"])

            with tab_dash:
                st.subheader("📅 Éves összehasonlítás (YoY)")
                y_val = st.radio("Mértékegység:", ['ST_NEFT', 'ST_MENNY'], format_func=lambda x: "Ft" if x=='ST_NEFT' else "db", horizontal=True)

                yoy_data = f_df.groupby(['Év', 'Hónap'])[y_val].sum().unstack(level=0)
                if len(yoy_data.columns) >= 2:
                    y_cols = sorted(yoy_data.columns)
                    y_prev, y_curr = y_cols[-2], y_cols[-1]
                    yoy_data['Eltérés %'] = ((yoy_data[y_curr] / yoy_data[y_prev]) - 1) * 100
                    st.dataframe(yoy_data.style.format("{:,.0f}").background_gradient(subset=['Eltérés %'], cmap='RdYlGn'), use_container_width=True)
                else:
                    st.dataframe(yoy_data, use_container_width=True)

                fig_trend = px.line(f_df.groupby('SF_TELJ')[y_val].sum().reset_index(), x='SF_TELJ', y=y_val, title="Forgalmi trend")
                st.plotly_chart(fig_trend, use_container_width=True)

            with tab_ai:
                st.header("🤖 AI Üzleti Asszisztens")
                user_input = st.text_area("Kérdezz az adatokról vagy kérj grafikont:", placeholder="Pl.: Melyik termék nőtt a legjobban tavalyhoz képest? Csinálj róla grafikont!")
                
                if st.button("Elemzés Indítása ✨") and openai_api_key:
                    with st.spinner("AI elemzés folyamatban..."):
                        client = OpenAI(api_key=openai_api_key)
                        
                        context = {
                            "trend": f_df.groupby(['Év', 'Hónap'])['ST_NEFT'].sum().to_dict(),
                            "top_termekek": f_df.groupby('ST_CIKKNEV')['ST_NEFT'].sum().sort_values(ascending=False).head(15).to_dict(),
                            "top_partnerek": f_df.groupby('SF_UGYFELNEV')['ST_NEFT'].sum().sort_values(ascending=False).head(10).to_dict()
                        }

                        # Itt a javítás: {{ }} használata a JSON példánál
                        prompt = f"""
                        Pékségi elemző vagy. Adatok: {context}
                        
                        Válaszolj magyarul. Ha grafikont kérnek, a válasz végére tedd be ezt:
                        ---CHART---
                        [ {{"label": "Példa1", "value": 100}}, {{"label": "Példa2", "value": 200}} ]
                        ---END---
                        """

                        res = client.chat.completions.create(
                            model="gpt-4o",
                            messages=[{"role": "system", "content": "Profi elemző vagy."}, {"role": "user", "content": f"{prompt}\n\nKérdés: {user_input}"}]
                        )
                        
                        full_res = res.choices[0].message.content
                        
                        if "---CHART---" in full_res:
                            parts = full_res.split("---CHART---")
                            st.markdown(parts[0])
                            try:
                                json_str = parts[1].split("---END---")[0].strip()
                                data = json.loads(json_str)
                                st.plotly_chart(px.bar(pd.DataFrame(data), x='label', y='value', color='label', text_auto='.2s'))
                            except:
                                st.warning("A grafikon adatait nem tudtam feldolgozni.")
                        else:
                            st.markdown(full_res)
        else:
            st.warning("Nincs adat a szűrőkkel.")
else:
    st.info("👋 Tölts fel CSV fájlokat a kezdéshez!")
