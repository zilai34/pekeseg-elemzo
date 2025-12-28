import streamlit as st
import pandas as pd
import plotly.express as px
from openai import OpenAI
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
import io

# --- 1. EGYEDI BEÁLLÍTÁSOK ---
# A te Google Drive mappád azonosítója
MAPPA_ID = '1HkDyBW7bDWpDPSRzfQ3ZQSnPMUo8k1Vz' 
HIVATALOS_JELSZO = "Velencei670905"
SZARAZ_LISTA = ['509496007', '509500001', '509502005', '524145003', '524149001']
RAKLAP_KOD = '146'

# --- 2. GOOGLE DRIVE FUNKCIÓK ---
def get_drive_service():
    try:
        # A Streamlit Secrets-ből olvassa ki a JSON kulcsot
        info = json.loads(st.secrets["gcp_service_account"])
        creds = service_account.Credentials.from_service_account_info(info)
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"Google Drive kapcsolódási hiba: {e}")
        return None

def save_to_drive(df):
    service = get_drive_service()
    if not service: return
    
    # CSV előkészítése memóriában
    csv_data = df.to_csv(index=False, sep=';', decimal=',', encoding='latin-1')
    fh = io.BytesIO(csv_data.encode('latin-1'))
    media = MediaIoBaseUpload(fh, mimetype='text/csv', resumable=True)
    
    # Ellenőrizzük, létezik-e már a fájl ebben a mappában
    query = f"name='pekseg_db.csv' and '{MAPPA_ID}' in parents and trashed = false"
    results = service.files().list(q=query, fields="files(id)").execute()
    items = results.get('files', [])
    
    if items:
        # Ha létezik, frissítjük
        service.files().update(fileId=items[0]['id'], media_body=media).execute()
        st.success("Adatbázis frissítve a felhőben! ✅")
    else:
        # Ha nem létezik, létrehozzuk a megadott mappában
        file_metadata = {
            'name': 'pekseg_db.csv',
            'parents': [MAPPA_ID]
        }
        service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        st.success("Új adatbázis létrehozva a felhőben! ✅")

def load_from_drive():
    service = get_drive_service()
    if not service: return None
    
    query = f"name='pekseg_db.csv' and '{MAPPA_ID}' in parents and trashed = false"
    results = service.files().list(q=query, fields="files(id)").execute()
    items = results.get('files', [])
    
    if not items:
        return None
    
    request = service.files().get_media(fileId=items[0]['id'])
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    fh.seek(0)
    return pd.read_csv(fh, sep=';', decimal=',', encoding='latin-1')

# --- 3. OLDAL BEÁLLÍTÁSA ÉS BELÉPÉS ---
st.set_page_config(page_title="Pékség Vezetői Dashboard", layout="wide")

if "bejelentkezve" not in st.session_state:
    st.session_state["bejelentkezve"] = False

if not st.session_state["bejelentkezve"]:
    st.title("🔐 Pékség Adatbázis Belépés")
    jelszo_input = st.text_input("Jelszó:", type="password")
    if st.button("Belépés"):
        if jelszo_input == HIVATALOS_JELSZO:
            st.session_state["bejelentkezve"] = True
            st.rerun()
        else:
            st.error("Hibás jelszó!")
    st.stop()

# --- 4. FŐ PROGRAM ---
st.title("📊 Pékség YoY Dashboard & Felhő Adatbázis")

# Adatok betöltése a Drive-ról induláskor
if 'df_final' not in st.session_state:
    with st.spinner('Adatok betöltése a felhőből...'):
        st.session_state['df_final'] = load_from_drive()

with st.sidebar:
    st.header("📁 Adatkezelés")
    uploaded_files = st.file_uploader("Új havi CSV-k hozzáadása", type="csv", accept_multiple_files=True)
    
    st.divider()
    if st.button("💾 MENTÉS A FELHŐBE (Drive)"):
        if st.session_state['df_final'] is not None:
            save_to_drive(st.session_state['df_final'])
        else:
            st.warning("Nincs menthető adat!")

    st.divider()
    st.subheader("📈 Áremelés beállítása")
    aremele_merteke = st.number_input("Áremelés mértéke (%)", value=0)

# Új fájlok feldolgozása és összefűzése a felhőben lévőkkel
if uploaded_files:
    temp_list = []
    if st.session_state['df_final'] is not None:
        temp_list.append(st.session_state['df_final'])
    
    for f in uploaded_files:
        new_data = pd.read_csv(f, sep=';', decimal=',', encoding='latin-1')
        temp_list.append(new_data)
    
    combined_df = pd.concat(temp_list, ignore_index=True).drop_duplicates()
    st.session_state['df_final'] = combined_df
    st.info("Új adatok hozzáadva a nézethez. Ne felejts el Menteni!")

# Megjelenítés, ha van adat
df = st.session_state['df_final']

if df is not None:
    # Adat tisztítás és előkészítés
    if 'ST_NE' in df.columns:
        df = df.rename(columns={'ST_NE': 'ST_NEFT'})
    
    df = df[df['ST_CIKKSZAM'].astype(str).str.strip() != RAKLAP_KOD]
    df['SF_TELJ'] = pd.to_datetime(df['SF_TELJ'], errors='coerce')
    df = df.dropna(subset=['SF_TELJ'])
    
    df['Ev'] = df['SF_TELJ'].dt.year
    df['Honap'] = df['SF_TELJ'].dt.strftime('%m')
    df['Termek_Kereso'] = df['ST_CIKKSZAM'].astype(str) + " - " + df['ST_CIKKNEV']

    # --- SZŰRŐK ---
    col1, col2 = st.columns(2)
    v_partner = col1.selectbox("Partner választása:", ["Összes"] + sorted(df['SF_UGYFELNEV'].unique().tolist()))
    v_termekek = col2.multiselect("Termékek szűrése:", sorted(df['Termek_Kereso'].unique().tolist()))

    f_df = df.copy()
    if v_partner != "Összes":
        f_df = f_df[f_df['SF_UGYFELNEV'] == v_partner]
    if v_termekek:
        f_df = f_df[f_df['Termek_Kereso'].isin(v_termekek)]

    # --- YoY ELEMZÉS ---
    st.subheader("Összehasonlítás (Év/Év)")
    stats = f_df.groupby(['Honap', 'Ev'])['ST_NEFT'].sum().unstack()
    
    if len(stats.columns) >= 2:
        evek = sorted(stats.columns)
        st.dataframe(stats.style.format("{:,.0f} Ft"), use_container_width=True)
        
        fig = px.bar(f_df.groupby(['Honap', 'Ev'])['ST_NEFT'].sum().reset_index(), 
                     x='Honap', y='ST_NEFT', color='Ev', barmode='group',
                     title="Havi forgalom alakulása")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Legalább két különböző év adata szükséges az összehasonlításhoz!")

    # --- AI ELEMZÉS ---
    st.divider()
    openai_key = st.text_input("OpenAI API Key az elemzéshez:", type="password")
    if st.button("🤖 AI Vezetői Elemzés"):
        if openai_key:
            client = OpenAI(api_key=openai_key)
            osszesites = f_df.groupby(['Ev', 'Honap'])['ST_NEFT'].sum().to_string()
            prompt = f"Pékség adatok:\n{osszesites}\nÁremelés mértéke: {aremele_merteke}%\nÍrj rövid vezetői elemzést magyarul."
            
            with st.spinner('AI gondolkodik...'):
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}]
                )
                st.info(response.choices[0].message.content)
        else:
            st.error("Kérlek add meg az OpenAI kulcsodat!")
else:
    st.info("Nincs adat. Kérlek tölts fel CSV fájlokat a bal oldalon!")
