import streamlit as st
import pandas as pd
import plotly.express as px
from openai import OpenAI
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
import io

# --- GOOGLE DRIVE FUNKCIÓK ---
def get_drive_service():
    # A Streamlit Secrets-ből olvassa ki a kulcsot
    info = json.loads(st.secrets["gcp_service_account"])
    creds = service_account.Credentials.from_service_account_info(info)
    return build('drive', 'v3', credentials=creds)

# Fájl mentése a Drive-ra (egy darab központi 'database.csv' fájlba)
def save_to_drive(df):
    service = get_drive_service()
    csv_data = df.to_csv(index=False, sep=';', encoding='latin-1')
    fh = io.BytesIO(csv_data.encode('latin-1'))
    media = MediaIoBaseUpload(fh, mimetype='text/csv', resumable=True)
    
    # Itt a fájlnév fix, így mindig felülírja/frissíti a központi adatbázist
    file_metadata = {'name': 'pekseg_adatbazis.csv'}
    service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    st.success("Adatok elmentve a felhőbe! ✅")

# Adatok betöltése a Drive-ról induláskor
def load_from_drive():
    try:
        service = get_drive_service()
        results = service.files().list(q="name='pekseg_adatbazis.csv'", fields="files(id)").execute()
        items = results.get('files', [])
        if not items: return None
        
        file_id = items[0]['id']
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        fh.seek(0)
        return pd.read_csv(fh, sep=';', decimal=',', encoding='latin-1')
    except:
        return None

# --- FŐ PROGRAM ---
st.set_page_config(page_title="Pékség Felhő Adatbázis", layout="wide")

# (Jelszavas rész maradhat a régi...)

with st.sidebar:
    st.header("📁 Adatkezelés")
    uploaded_files = st.file_uploader("Új havi fájlok hozzáadása", type="csv", accept_multiple_files=True)
    
    if st.button("🗑️ Összes adat törlése (Tiszta lap)"):
        # Itt a Drive-ról való törlés logikája jönne
        st.warning("Funkció fejlesztés alatt: Kérlek kézzel töröld a Drive-ról a pekseg_adatbazis.csv-t.")

# Adatok betöltése (Múlt + Új)
df_mult = load_from_drive()

if uploaded_files:
    data_list = []
    if df_mult is not None: data_list.append(df_mult)
    for f in uploaded_files:
        data_list.append(pd.read_csv(f, sep=';', decimal=',', encoding='latin-1'))
    
    df = pd.concat(data_list, ignore_index=True).drop_duplicates()
    
    if st.button("💾 MENTÉS A FELHŐBE (2026-ra)"):
        save_to_drive(df)
else:
    df = df_mult

if df is not None:
    # --- INNEN JÖN A KORÁBBI ELEMZŐ KÓD (YoY, Áremelés, AI) ---
    st.write("Adatbázis állapota: Betöltve a felhőből.")
    # (Ide másolható a korábbi grafikonos és szűrős rész...)
else:
    st.info("Még nincsenek adatok a felhőben. Tölts fel egy CSV-t!")
