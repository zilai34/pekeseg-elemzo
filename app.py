import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from openai import OpenAI
import json
import datetime

# --- 1. KONFIGURÁCIÓ ÉS STÍLUS ---
HIVATALOS_JELSZO = "Velencei670905" 
st.set_page_config(page_title="Pékség Dashboard AI Pro", layout="wide", page_icon="🥐")

openai_api_key = st.secrets.get("OPENAI_API_KEY")

st.markdown("""
    <style>
    div[data-testid="metric-container"] {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #e0e0e0;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: #f8f9fa; border-radius: 5px; padding: 10px; }
    .stTabs [aria-selected="true"] { background-color: #e9ecef; border-bottom: 2px solid #007bff; }
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
    if st.button("Kijelentkezés"):
        st.session_state["bejelentkezve"] = False
        st.rerun()

# --- 5. FŐOLDAL ---
if uploaded_files:
    df = load_data(uploaded_files)
    if df is not None:
        st.title("📊 Pékség Dashboard & AI Stratégiai Műhely")
        
        with st.expander("🔍 Szűrés és Összehasonlítás beállítása", expanded=True):
            c1, c2, c3 = st.columns(3)
            v_partner = c1.selectbox("Partner választása:", ["Összes partner"] + sorted(df['SF_UGYFELNEV'].unique().tolist()))
            v_kat = c2.multiselect("Kategória:", ["Friss áru", "Száraz áru"], default=["Friss áru", "Száraz áru"])
            v_cikkszam_nev = c3.multiselect("Termékek összehasonlítása (max 5-10 javasolt):", sorted(df['Cikkszam_Nev'].unique().tolist()))
            
            min_d, max_d = df['SF_TELJ'].min().date(), df['SF_TELJ'].max().date()
            date_range = st.date_input("Dátum tartomány:", value=(min_d, max_d))

        # Alapszűrés
        f_df = df.copy()
        if isinstance(date_range, tuple) and len(date_range) == 2:
            f_df = f_df[(f_df['SF_TELJ'].dt.date >= date_range[0]) & (f_df['SF_TELJ'].dt.date <= date_range[1])]
        if v_kat: f_df = f_df[f_df['Kategória'].isin(v_kat)]
        if v_partner != "Összes partner": f_df = f_df[f_df['SF_UGYFELNEV'] == v_partner]

        if not f_df.empty:
            st.divider()
            m1, m2, m3 = st.columns(3)
            m1.metric("Szűrt mennyiség", f"{f_df['ST_MENNY'].sum():,.0f} db")
            m2.metric("Nettó árbevétel", f"{f_df['ST_NEFT'].sum():,.0f} Ft")
            m3.metric("Aktív napok", f"{f_df['SF_TELJ'].dt.date.nunique()} nap")

            tab_dash, tab_ai = st.tabs(["📈 Trendek & Összehasonlítás", "🤖 AI Stratégiai Műhely"])

            with tab_dash:
                st.subheader("📊 Dinamikus Termék Trendek")
                y_val = st.radio("Mértékegység:", ['ST_NEFT', 'ST_MENNY'], format_func=lambda x: "Ft" if x=='ST_NEFT' else "db", horizontal=True)

                fig = go.Figure()
                if v_cikkszam_nev:
                    # Minden kijelölt termék saját színt kap
                    for termek in v_cikkszam_nev:
                        t_data = f_df[f_df['Cikkszam_Nev'] == termek].groupby('SF_TELJ')[y_val].sum().reset_index()
                        fig.add_trace(go.Scatter(x=t_data['SF_TELJ'], y=t_data[y_val], name=termek, mode='lines'))
                    
                    # Összesítő vonal a kijelöltekre
                    if len(v_cikkszam_nev) > 1:
                        total_sel = f_df[f_df['Cikkszam_Nev'].isin(v_cikkszam_nev)].groupby('SF_TELJ')[y_val].sum().reset_index()
                        fig.add_trace(go.Scatter(x=total_sel['SF_TELJ'], y=total_sel[y_val], name="ÖSSZESÍTETT (Kijelölt)", 
                                                 line=dict(color='black', width=4, dash='dashdot')))
                else:
                    total_all = f_df.groupby('SF_TELJ')[y_val].sum().reset_index()
                    fig.add_trace(go.Scatter(x=total_all['SF_TELJ'], y=total_all[y_val], name="Teljes szűrt forgalom"))

                fig.update_layout(hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                st.plotly_chart(fig, use_container_width=True)

                st.subheader("📅 Éves összehasonlítás (YoY)")
                yoy_data = f_df.groupby(['Év', 'Hónap'])[y_val].sum().unstack(level=0)
                if len(yoy_data.columns) >= 2:
                    y_cols = sorted(yoy_data.columns)
                    yoy_data['Eltérés %'] = ((yoy_data[y_cols[-1]] / yoy_data[y_cols[-2]]) - 1) * 100
                    st.dataframe(yoy_data.style.format("{:,.0f}").background_gradient(subset=['Eltérés %'], cmap='RdYlGn'), use_container_width=True)
                else:
                    st.dataframe(yoy_data, use_container_width=True)

            with tab_ai:
                st.header("🤖 AI Üzleti Asszisztens & Vizualizáció")
                user_input = st.text_area("Kérdezz az adatokról vagy kérj grafikont (Pl.: 'Grafikont a top 5 partneremről'):", height=100)
                
                if st.button("AI Elemzés Indítása ✨") and openai_api_key:
                    with st.spinner("Az AI áttekinti az összes adatot..."):
                        client = OpenAI(api_key=openai_api_key)
                        context = {
                            "havi_trend": f_df.groupby(['Év', 'Hónap'])['ST_NEFT'].sum().to_dict(),
                            "top_termekek": f_df.groupby('ST_CIKKNEV')['ST_NEFT'].sum().sort_values(ascending=False).head(15).to_dict(),
                            "top_partnerek": f_df.groupby('SF_UGYFELNEV')['ST_NEFT'].sum().sort_values(ascending=False).head(10).to_dict()
                        }
                        # Dupla {{ }} a JSON minta miatt, hogy ne legyen hiba
                        prompt = f"""
                        Te egy profi pékségi elemző vagy. Adatok: {context}
                        Válaszolj magyarul. Ha grafikont kérnek, a válasz végére pontosan ezt szúrd be:
                        ---CHART---
                        [ {{"label": "Név", "value": 100}}, {{"label": "Név2", "value": 200}} ]
                        ---END---
                        """
                        res = client.chat.completions.create(
                            model="gpt-4o",
                            messages=[{"role": "system", "content": "Üzleti elemző vagy."}, {"role": "user", "content": f"{prompt}\nKérdés: {user_input}"}]
                        )
                        full_res = res.choices[0].message.content
                        if "---CHART---" in full_res:
                            parts = full_res.split("---CHART---")
                            st.markdown(parts[0])
                            try:
                                json_str = parts[1].split("---END---")[0].strip()
                                chart_data = json.loads(json_str)
                                st.plotly_chart(px.bar(pd.DataFrame(chart_data), x='label', y='value', color='label', text_auto='.2s', title="AI Statisztika"))
                            except: st.warning("A grafikont nem sikerült kirajzolni.")
                        else: st.markdown(full_res)
        else: st.warning("Nincs adat a szűrőkkel.")
else: st.info("👋 Tölts fel CSV fájlokat a kezdéshez!")
