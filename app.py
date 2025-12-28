import streamlit as st
import pandas as pd
import plotly.express as px
from openai import OpenAI
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
import io

# ==========================================
# 1. KONFIGURÁCIÓ ÉS BEÁLLÍTÁSOK
# ==========================================
MAPPA_ID = '1HkDyBW7bDWpDPSRzfQ3ZQSnPMUo8k1Vz' 
HIVATALOS_JELSZO = "Velencei670905"
RAKLAP_KOD = '146'

# ==========================================
# 2. GOOGLE DRIVE MOTOR (GCP)
# ==========================================
def get_drive_service():
    try:
        # A Secrets-ből olvassa be a dupla visszaperjeles JSON-t
        info = json.loads(st.secrets["gcp_service_account"])
        creds = service_account.Credentials.from_service_account_info(info)
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"⚠️ Kritikus hiba a Google elérésekor: {e}")
        return None

def save_to_drive(df):
    service = get_drive_service()
    if not service: return
    
    # Adatok előkészítése CSV formátumba a memóriában
    csv_data = df.to_csv(index=False, sep=';', decimal=',', encoding='latin-1')
    fh = io.BytesIO(csv_data.encode('latin-1'))
    media = MediaIoBaseUpload(fh, mimetype='text/csv', resumable=True)
    
    # Megnézzük, létezik-e már a fájl
    query = f"name='pekseg_db.csv' and '{MAPPA_ID}' in parents and trashed = false"
    results = service.files().list(q=query, fields="files(id)").execute()
    items = results.get('files', [])
    
    if items:
        # Frissítés
        service.files().update(fileId=items[0]['id'], media_body=media).execute()
        st.success("✅ Adatbázis sikeresen frissítve a felhőben!")
    else:
        # Új fájl létrehozása
        file_metadata = {'name': 'pekseg_db.csv', 'parents': [MAPPA_ID]}
        service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        st.success("✅ Új adatbázis létrehozva a felhőben!")

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

# ==========================================
# 3. BELÉPÉSI RENDSZER
# ==========================================
st.set_page_config(page_title="Pékség Vezetői Dashboard", layout="wide")

if "bejelentkezve" not in st.session_state:
    st.session_state["bejelentkezve"] = False

if not st.session_state["bejelentkezve"]:
    st.title("🔐 Pékség Adatbázis - Belépés")
    col_login, _ = st.columns([1, 2])
    with col_login:
        jelszo_input = st.text_input("Kérem a jelszót:", type="password")
        if st.button("Belépés"):
            if jelszo_input == HIVATALOS_JELSZO:
                st.session_state["bejelentkezve"] = True
                st.rerun()
            else:
                st.error("❌ Hibás jelszó!")
    st.stop()

# ==========================================
# 4. ADATOK BETÖLTÉSE ÉS OLDALSÁV
# ==========================================
st.title("📊 Pékség YoY Dashboard & Felhő Adatbázis")

# Automatikus betöltés indításkor
if 'df_final' not in st.session_state:
    with st.spinner('Adatok beolvasása a Drive-ról...'):
        st.session_state['df_final'] = load_from_drive()

with st.sidebar:
    st.header("📁 Adatok Kezelése")
    uploaded_files = st.file_uploader("Új havi CSV fájlok kiválasztása", type="csv", accept_multiple_files=True)
    
    if st.button("💾 MENTÉS A FELHŐBE"):
        if st.session_state['df_final'] is not None:
            save_to_drive(st.session_state['df_final'])
        else:
            st.warning("Nincs menthető adat az adatbázisban!")
    
    st.divider()
    st.subheader("⚙️ Beállítások")
    aremele_merteke = st.number_input("Tervezett áremelés (%)", value=0)

# Új fájlok feldolgozása
if uploaded_files:
    temp_list = []
    if st.session_state['df_final'] is not None:
        temp_list.append(st.session_state['df_final'])
    
    for f in uploaded_files:
        new_data = pd.read_csv(f, sep=';', decimal=',', encoding='latin-1')
        temp_list.append(new_data)
    
    # Összefűzés és duplikációk szűrése
    combined_df = pd.concat(temp_list, ignore_index=True).drop_duplicates()
    st.session_state['df_final'] = combined_df
    st.info("💡 Új adatok hozzáadva a nézethez. Ne felejts el menteni a felhőbe!")

# ==========================================
# 5. ELEMZÉS ÉS VIZUALIZÁCIÓ
# ==========================================
df = st.session_state['df_final']

if df is not None:
    # Adattisztítás
    if 'ST_NE' in df.columns:
        df = df.rename(columns={'ST_NE': 'ST_NEFT'})
    
    # Raklap és üres dátumok kiszűrése
    df = df[df['ST_CIKKSZAM'].astype(str).str.strip() != RAKLAP_KOD]
    df['SF_TELJ'] = pd.to_datetime(df['SF_TELJ'], errors='coerce')
    df = df.dropna(subset=['SF_TELJ'])
    
    # Segédoszlopok
    df['Ev'] = df['SF_TELJ'].dt.year
    df['Honap'] = df['SF_TELJ'].dt.strftime('%m')
    df['Termek_Kereso'] = df['ST_CIKKSZAM'].astype(str) + " - " + df['ST_CIKKNEV']

    # Szűrők a főoldalon
    c1, c2 = st.columns(2)
    v_partner = c1.selectbox("Válassz partnert:", ["Összes"] + sorted(df['SF_UGYFELNEV'].unique().tolist()))
    v_termekek = c2.multiselect("Válassz termékeket:", sorted(df['Termek_Kereso'].unique().tolist()))

    # Szűrés végrehajtása
    f_df = df.copy()
    if v_partner != "Összes":
        f_df = f_df[f_df['SF_UGYFELNEV'] == v_partner]
    if v_termekek:
        f_df = f_df[f_df['Termek_Kereso'].isin(v_termekek)]

    # Táblázat megjelenítése (STABIL VERZIÓ)
    st.subheader("Havi nettó árbevétel alakulása (Év/Év)")
    stats = f_df.groupby(['Honap', 'Ev'])['ST_NEFT'].sum().unstack()
    
    if not stats.empty:
        st.dataframe(
            stats, 
            use_container_width=True,
            column_config={str(ev): st.column_config.NumberColumn(format="%.0f Ft") for ev in stats.columns}
        )
        
        # Grafikon
        fig = px.bar(
            f_df.groupby(['Honap', 'Ev'])['ST_NEFT'].sum().reset_index(), 
            x='Honap', y='ST_NEFT', color='Ev', barmode='group',
            labels={'ST_NEFT': 'Nettó árbevétel (Ft)', 'Honap': 'Hónap'},
            height=500
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Nincs megjeleníthető adat a kiválasztott szűrőkkel.")

    # OpenAI AI Elemzés
    st.divider()
    st.subheader("🤖 Mesterséges Intelligencia Elemzése")
    openai_key = st.text_input("OpenAI API kulcs beírása:", type="password")
    
    if st.button("Elemzés indítása"):
        if openai_key:
            try:
                client = OpenAI(api_key=openai_key)
                # Adatok tömörítése az AI-nak
                ai_data = f_df.groupby(['Ev', 'Honap'])['ST_NEFT'].sum().to_string()
                prompt = f"Te egy üzleti elemző vagy. Itt a pékség árbevétele:\n{ai_data}\nÁremelés: {aremele_merteke}%. Írj 5 fontos pontot magyarul!"
                
                with st.spinner('Az AI elemzi az adatokat...'):
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "user", "content": prompt}]
                    )
                    st.info(response.choices[0].message.content)
            except Exception as e:
                st.error(f"AI hiba: {e}")
        else:
            st.error("Az elemzéshez meg kell adnod az OpenAI API kulcsodat!")
else:
    st.info("Az adatbázis üres. Tölts fel CSV fájlokat a bal oldali sávban!")
