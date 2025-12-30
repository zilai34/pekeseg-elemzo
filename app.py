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
            # Megjegyzés: sep=';' és latin-1 kódolás a magyar Excel/CSV fájlokhoz
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
            date_range = st.date_input("Időszak:", value=(df['SF_TELJ'].min().date(), df['SF_
