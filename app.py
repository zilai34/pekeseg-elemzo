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
    uploaded_files = st.file_uploader("CSV fájlok feltöltése (több év is lehet)", type="csv", accept_multiple_files=True)
    
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
        
        # --- SZŰRŐK ---
        with st.expander("🔍 Szűrési feltételek", expanded=True):
            c1, c2, c3 = st.columns(3)
            partnerek = ["Összes partner"] + sorted(df['SF_UGYFELNEV'].unique().tolist())
            v_partner = c1.selectbox("Partner választása:", partnerek)
            v_kat = c2.multiselect("Kategória:", ["Friss áru", "Száraz áru"], default=["Friss áru", "Száraz áru"])
            cikkszam_lista = sorted(df['Cikkszam_Nev'].unique().tolist())
            v_cikkszam_nev = c3.multiselect("Termék szerinti szűrés:", cikkszam_lista)
            
            min_d, max_d = df['SF_TELJ'].min().date(), df['SF_TELJ'].max().date()
            date_range = st.date_input("Dátum tartomány:", value=(min_d, max_d), min_value=min_d, max_value=max_d)

        f_df = df.copy()
        if isinstance(date_range, tuple) and len(date_range) == 2:
            f_df = f_df[(f_df['SF_TELJ'].dt.date >= date_range[0]) & (f_df['SF_TELJ'].dt.date <= date_range[1])]
        if v_kat: f_df = f_df[f_df['Kategória'].isin(v_kat)]
        if v_partner != "Összes partner": f_df = f_df[f_df['SF_UGYFELNEV'] == v_partner]
        if v_cikkszam_nev: f_df = f_df[f_df['Cikkszam_Nev'].isin(v_cikkszam_nev)]

        # --- 6. KPI MUTATÓK ---
        if not f_df.empty:
            st.divider()
            m1, m2, m3 = st.columns(3)
            osszes_menny = f_df['ST_MENNY'].sum()
            osszes_netto = f_df['ST_NEFT'].sum()
            napok = f_df['SF_TELJ'].dt.date.nunique()
            
            m1.metric("Szűrt mennyiség", f"{osszes_menny:,.0f}".replace(",", " ") + " db")
            m2.metric("Nettó árbevétel", f"{osszes_netto:,.0f}".replace(",", " ") + " Ft")
            m3.metric("Napi átlag forgalom", f"{(osszes_netto/napok if napok>0 else 0):,.0f}".replace(",", " ") + " Ft")

            # --- 7. TABS: DASHBOARD VS AI MŰHELY ---
            tab_dash, tab_ai = st.tabs(["📈 Dashboard & Trendek", "🤖 AI Stratégiai Műhely"])

            with tab_dash:
                st.subheader("📅 Éves összehasonlítás (YoY)")
                y_val = st.radio("Mértékegység:", ['ST_NEFT', 'ST_MENNY'], 
                                format_func=lambda x: "Ft" if x=='ST_NEFT' else "db", horizontal=True)

                # YoY Táblázat
                yoy_data = f_df.groupby(['Év', 'Hónap'])[y_val].sum().unstack(level=0)
                if len(yoy_data.columns) >= 2:
                    y_cols = sorted(yoy_data.columns)
                    y_prev, y_curr = y_cols[-2], y_cols[-1]
                    yoy_data['Eltérés %'] = ((yoy_data[y_curr] / yoy_data[y_prev]) - 1) * 100
                    st.dataframe(yoy_data.style.format("{:,.0f}").background_gradient(subset=['Eltérés %'], cmap='RdYlGn'))
                else:
                    st.dataframe(yoy_data)

                # Trend grafikon
                fig_trend = px.line(f_df.groupby('SF_TELJ')[y_val].sum().reset_index(), x='SF_TELJ', y=y_val, title="Napi forgalmi trend")
                st.plotly_chart(fig_trend, use_container_width=True)

            with tab_ai:
                st.header("🤖 AI Üzleti Asszisztens & Grafikon Generátor")
                st.info("Kérdezz bármit! Példa: 'Készíts egy grafikont a 5 legtöbbet hozó partneremről' vagy 'Melyik hónapban volt a legnagyobb a visszaesés?'")
                
                user_input = st.text_area("Írd ide a kérdésed vagy az elemzési igényed:", height=100)
                
                if st.button("AI Elemzés Indítása ✨") and openai_api_key:
                    with st.spinner("Az AI elemzi az összes adatot és grafikont készít..."):
                        client = OpenAI(api_key=openai_api_key)
                        
                        # Kontextus összeállítása az összes fájlból
                        context = {
                            "havi_trend": f_df.groupby(['Év', 'Hónap'])['ST_NEFT'].sum().to_dict(),
                            "top_termekek": f_df.groupby('ST_CIKKNEV')['ST_NEFT'].sum().sort_values(ascending=False).head(15).to_dict(),
                            "top_partnerek": f_df.groupby('SF_UGYFELNEV')['ST_NEFT'].sum().sort_values(ascending=False).head(10).to_dict(),
                            "kategoriak": f_df.groupby('Kategória')['ST_NEFT'].sum().to_dict()
                        }

                        prompt = f"""
                        Te egy profi pékségi üzleti elemző vagy. Minden adathoz hozzáférsz.
                        ADATOK: {context}
                        
                        FELADAT:
                        1. Válaszolj a kérdésre magyarul, szakmai szemmel.
                        2. Ha a válaszodban statisztika van, a végére szúrd be ezt a pontos formátumot a grafikonhoz:
                           ---CHART---
                           [{"label": "Név1", "value": 100}, {"label": "Név2", "value": 200}]
                           ---END---
                        
                        KÉRDÉS: {user_input}
                        """

                        res = client.chat.completions.create(
                            model="gpt-4o",
                            messages=[{"role": "system", "content": "Üzleti elemző vagy."}, {"role": "user", "content": prompt}]
                        )
                        
                        full_res = res.choices[0].message.content
                        
                        # Szöveg és grafikon szétválasztása
                        if "---CHART---" in full_res:
                            text_part = full_res.split("---CHART---")[0]
                            json_part = full_res.split("---CHART---")[1].split("---END---")[0].strip()
                            
                            st.markdown(text_part)
                            try:
                                data = json.loads(json_part)
                                c_df = pd.DataFrame(data)
                                fig_ai = px.bar(c_df, x='label', y='value', color='label', title="AI által generált statisztika", text_auto='.2s')
                                st.plotly_chart(fig_ai, use_container_width=True)
                            except:
                                st.error("A grafikont nem sikerült legenerálni, de az elemzést láthatod fent.")
                        else:
                            st.markdown(full_res)
        else:
            st.warning("Nincs adat a választott szűrőkkel.")
else:
    st.info("👋 Kezdéshez tölts fel CSV fájlokat a bal oldali sávban!")
