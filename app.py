import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from openai import OpenAI
import json

# --- 1. KONFIGURÁCIÓ ---
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
    </style>
""", unsafe_allow_html=True)

# --- 2. ADATKEZELÉS ---
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

# --- 3. BEJELENTKEZÉS ---
if "bejelentkezve" not in st.session_state:
    st.session_state["bejelentkezve"] = False

if not st.session_state["bejelentkezve"]:
    st.title("🔐 Bejelentkezés")
    with st.form("login_form"):
        bevitt_jelszo = st.text_input("Jelszó:", type="password")
        submit_button = st.form_submit_button("Belépés")
        if submit_button:
            if bevitt_jelszo == HIVATALOS_JELSZO:
                st.session_state["bejelentkezve"] = True
                st.rerun()
            else:
                st.error("Hibás jelszó!")
    st.stop()

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
        
        with st.expander("🔍 Szűrés és Összehasonlítás", expanded=True):
            c1, c2, c3 = st.columns(3)
            v_partner = c1.selectbox("Partner:", ["Összes partner"] + sorted(df['SF_UGYFELNEV'].unique().tolist()))
            v_kat = c2.multiselect("Kategória:", ["Friss áru", "Száraz áru"], default=["Friss áru", "Száraz áru"])
            v_cikkszam_nev = c3.multiselect("Termékek kiválasztása:", sorted(df['Cikkszam_Nev'].unique().tolist()))
            date_range = st.date_input("Időszak:", value=(df['SF_TELJ'].min().date(), df['SF_TELJ'].max().date()))

        # --- SZŰRÉSI LOGIKA ---
        f_df = df.copy()
        if isinstance(date_range, tuple) and len(date_range) == 2:
            f_df = f_df[(f_df['SF_TELJ'].dt.date >= date_range[0]) & (f_df['SF_TELJ'].dt.date <= date_range[1])]
        if v_kat: f_df = f_df[f_df['Kategória'].isin(v_kat)]
        if v_partner != "Összes partner": f_df = f_df[f_df['SF_UGYFELNEV'] == v_partner]

        # KPI-khez és grafikonhoz használt végső tábla
        final_df = f_df.copy()
        if v_cikkszam_nev:
            final_df = final_df[final_df['Cikkszam_Nev'].isin(v_cikkszam_nev)]

        if not final_df.empty:
            st.divider()
            m1, m2, m3 = st.columns(3)
            m1.metric("Szűrt mennyiség", f"{final_df['ST_MENNY'].sum():,.0f} db".replace(",", " "))
            m2.metric("Nettó árbevétel", f"{final_df['ST_NEFT'].sum():,.0f} Ft".replace(",", " "))
            m3.metric("Aktív napok", f"{final_df['SF_TELJ'].dt.date.nunique()} nap")

            tab_dash, tab_ai = st.tabs(["📈 Trendek & Összehasonlítás", "🤖 AI Stratégiai Műhely"])

            with tab_dash:
                y_val = st.radio("Mértékegység:", ['ST_NEFT', 'ST_MENNY'], format_func=lambda x: "Ft" if x=='ST_NEFT' else "db", horizontal=True)
                
                fig = go.Figure()
                if v_cikkszam_nev:
                    for termek in v_cikkszam_nev:
                        t_data = final_df[final_df['Cikkszam_Nev'] == termek].groupby('SF_TELJ')[y_val].sum().reset_index()
                        fig.add_trace(go.Scatter(x=t_data['SF_TELJ'], y=t_data[y_val], name=termek, mode='lines'))
                    if len(v_cikkszam_nev) > 1:
                        total_line = final_df.groupby('SF_TELJ')[y_val].sum().reset_index()
                        fig.add_trace(go.Scatter(x=total_line['SF_TELJ'], y=total_line[y_val], name="ÖSSZESÍTETT", line=dict(color='black', width=4, dash='dashdot')))
                else:
                    total_all = final_df.groupby('SF_TELJ')[y_val].sum().reset_index()
                    fig.add_trace(go.Scatter(x=total_all['SF_TELJ'], y=total_all[y_val], name="Teljes forgalom"))

                fig.update_layout(hovermode="x unified", legend=dict(orientation="h", y=1.02))
                st.plotly_chart(fig, use_container_width=True)

                st.subheader("📅 Havi bontás (YoY)")
                yoy = final_df.groupby(['Év', 'Hónap'])[y_val].sum().unstack(level=0)
                st.dataframe(yoy.style.format("{:,.0f}"), use_container_width=True)

            with tab_ai:
                st.header("🤖 AI Üzleti Asszisztens")
                user_input = st.text_area("Kérdezz az adatokról vagy kérj statisztikát:")
                if st.button("Elemzés ✨") and openai_api_key:
                    with st.spinner("Gondolkodom..."):
                        client = OpenAI(api_key=openai_api_key)
                        ctx = {"top_10_termek": final_df.groupby('ST_CIKKNEV')['ST_NEFT'].sum().sort_values(ascending=False).head(10).to_dict()}
                        
                        prompt = f"""
                        Pékségi elemző vagy. Adatok: {ctx}
                        Ha grafikont kérnek, szúrd be a végére:
                        ---CHART---
                        [ {{"label": "Példa", "value": 100}} ]
                        ---END---
                        Kérdés: {user_input}
                        """
                        res = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
                        ans = res.choices[0].message.content
                        
                        if "---CHART---" in ans:
                            st.markdown(ans.split("---CHART---")[0])
                            try:
                                raw_js = ans.split("---CHART---")[1].split("---END---")[0].strip()
                                st.plotly_chart(px.bar(pd.DataFrame(json.loads(raw_js)), x='label', y='value', color='label'))
                            except: st.warning("Grafikon hiba.")
                        else: st.markdown(ans)
        else: st.warning("Nincs adat.")
else: st.info("👋 Tölts fel CSV fájlokat!")
