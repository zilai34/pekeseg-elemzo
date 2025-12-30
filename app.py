import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from openai import OpenAI
import json

# --- 1. KONFIGURÁCIÓ ---
HIVATALOS_JELSZO = "Velencei670905" 
st.set_page_config(page_title="Pékség Dashboard AI Pro", layout="wide", page_icon="🥐")

# OpenAI API kulcs betöltése a titkokból (ha használsz AI-t)
openai_api_key = st.secrets.get("OPENAI_API_KEY")

# --- 2. ADATKEZELÉS ÉS KATALÓGUS ---
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
    
    # Adattisztítás
    df['ST_CIKKSZAM'] = df['ST_CIKKSZAM'].astype(str).str.strip()
    df = df[df['ST_CIKKSZAM'] != '146'] # Hibás sorok szűrése
    
    # Dátumkezelés
    df['SF_TELJ'] = pd.to_datetime(df['SF_TELJ'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['SF_TELJ']) 
    
    # Segédoszlopok
    df['Év'] = df['SF_TELJ'].dt.year
    df['Hónap'] = df['SF_TELJ'].dt.month
    df['Honap_Nev'] = df['SF_TELJ'].dt.strftime('%Y-%m')
    df['Kategória'] = df['ST_CIKKSZAM'].apply(lambda x: "Száraz áru" if x in SZARAZ_LISTA else "Friss áru")
    df['Cikkszam_Nev'] = df['ST_CIKKSZAM'] + " - " + df['ST_CIKKNEV'].astype(str)
    
    return df

# --- 3. LOGIN RENDSZER ---
if "bejelentkezve" not in st.session_state:
    st.session_state["bejelentkezve"] = False

if not st.session_state["bejelentkezve"]:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.subheader("🔐 Bejelentkezés")
        with st.form("login_form"):
            pw = st.text_input("Jelszó:", type="password")
            submit = st.form_submit_button("Belépés")
            if submit:
                if pw == HIVATALOS_JELSZO:
                    st.session_state["bejelentkezve"] = True
                    st.success("Sikeres belépés!")
                    st.rerun()
                else:
                    st.error("Hibás jelszó!")
    st.stop()

# --- 4. OLDALSÁV (Sidebar) ---
st.sidebar.header("📂 Adatforrás")
uploaded_files = st.sidebar.file_uploader("Válassz ki egy vagy több CSV fájlt", type="csv", accept_multiple_files=True)

if uploaded_files:
    df = load_data(uploaded_files)
    if df is not None:
        st.title("📊 Pékség Dashboard & AI Műhely")
        
        # --- 5. SZŰRŐK ---
        with st.expander("🔍 Szűrés és Összehasonlítás", expanded=True):
            c1, c2, c3 = st.columns(3)
            v_partner = c1.selectbox("Partner választása:", ["Összes partner"] + sorted(df['SF_UGYFELNEV'].unique().tolist()))
            v_kat = c2.multiselect("Kategória:", ["Friss áru", "Száraz áru"], default=["Friss áru", "Száraz áru"])
            v_cikkszam_nev = c3.multiselect("Konkrét termékek összehasonlítása:", sorted(df['Cikkszam_Nev'].unique().tolist()))
            
            # Dátum tartomány csúszka
            min_date = df['SF_TELJ'].min().date()
            max_date = df['SF_TELJ'].max().date()
            date_range = st.date_input("Dátum tartomány:", value=(min_date, max_date))

        # --- 6. SZŰRÉSI LOGIKA ---
        # Alapszűrés (Idő, Partner, Kategória)
        f_df = df.copy()
        if isinstance(date_range, tuple) and len(date_range) == 2:
            f_df = f_df[(f_df['SF_TELJ'].dt.date >= date_range[0]) & (f_df['SF_TELJ'].dt.date <= date_range[1])]
        
        if v_kat:
            f_df = f_df[f_df['Kategória'].isin(v_kat)]
            
        if v_partner != "Összes partner":
            f_df = f_df[f_df['SF_UGYFELNEV'] == v_partner]

        # Termék szintű szűrés a KPI-okhoz
        final_df = f_df.copy()
        if v_cikkszam_nev:
            final_df = final_df[final_df['Cikkszam_Nev'].isin(v_cikkszam_nev)]

        # --- 7. KPI MUTATÓK ---
        if not final_df.empty:
            st.divider()
            m1, m2, m3 = st.columns(3)
            m1.metric("Szűrt mennyiség", f"{final_df['ST_MENNY'].sum():,.0f} db")
            m2.metric("Nettó árbevétel", f"{final_df['ST_NEFT'].sum():,.0f} Ft")
            m3.metric("Aktív napok száma", f"{final_df['SF_TELJ'].dt.date.nunique()} nap")

            # --- 8. TABS (Grafikonok és AI) ---
            tab_dash, tab_ai = st.tabs(["📈 Trendek & Összehasonlítás", "🤖 AI Stratégiai Műhely"])

            with tab_dash:
                y_val = st.radio("Mértékegység:", ['ST_NEFT', 'ST_MENNY'], 
                                format_func=lambda x: "HUF (Ft)" if x=='ST_NEFT' else "Mennyiség (db)", horizontal=True)
                
                # Dinamikus grafikon
                fig = go.Figure()
                if v_cikkszam_nev:
                    # Ha van kiválasztott termék, mindet külön vonalra tesszük
                    for termek in v_cikkszam_nev:
                        t_data = final_df[final_df['Cikkszam_Nev'] == termek].groupby('SF_TELJ')[y_val].sum().reset_index()
                        fig.add_trace(go.Scatter(x=t_data['SF_TELJ'], y=t_data[y_val], name=termek, mode='lines'))
                    
                    # Ha több termék van, egy vastag összesített vonal is kell
                    if len(v_cikkszam_nev) > 1:
                        total_sel = final_df.groupby('SF_TELJ')[y_val].sum().reset_index()
                        fig.add_trace(go.Scatter(x=total_sel['SF_TELJ'], y=total_sel[y_val], 
                                               name="KIJELÖLTEK ÖSSZESEN", 
                                               line=dict(color='black', width=4, dash='dashdot')))
                else:
                    # Ha nincs termék kijelölve, a teljes szűrt forgalmat mutatjuk
                    total_all = final_df.groupby('SF_TELJ')[y_val].sum().reset_index()
                    fig.add_trace(go.Scatter(x=total_all['SF_TELJ'], y=total_all[y_val], name="Teljes szűrt forgalom", fill='tozeroy'))

                fig.update_layout(title="Forgalmi trendek", hovermode="
