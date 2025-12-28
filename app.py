import streamlit as st
import pandas as pd
import plotly.express as px
from openai import OpenAI
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
import io

# --- 1. GOOGLE DRIVE KAPCSOLAT ---
def get_drive_service():
    try:
        info = json.loads(st.secrets["gcp_service_account"])
        creds = service_account.Credentials.from_service_account_info(info)
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"Google Drive hiba: {e}")
        return None

def save_to_drive(df):
    service = get_drive_service()
    if not service: return
    csv_data = df.to_csv(index=False, sep=';', decimal=',', encoding='latin-1')
    fh = io.BytesIO(csv_data.encode('latin-1'))
    media = MediaIoBaseUpload(fh, mimetype='text/csv', resumable=True)
    
    # Keressük meg, létezik-e már a fájl
    results = service.files().list(q="name='pekseg_db.csv'", fields="files(id)").execute()
    items = results.get('files', [])
    
    if items:
        service.files().update(fileId=items[0]['id'], media_body=media).execute()
    else:
        file_metadata = {'name': 'pekseg_db.csv'}
        service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    st.success("Adatok elmentve a felhőbe! 2026-ban is elérhetőek lesznek. ✅")

def load_from_drive():
    service = get_drive_service()
    if not service: return None
    results = service.files().list(q="name='pekseg_db.csv'", fields="files(id)").execute()
    items = results.get('files', [])
    if not items: return None
    
    request = service.files().get_media(fileId=items[0]['id'])
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    fh.seek(0)
    return pd.read_csv(fh, sep=';', decimal=',', encoding='latin-1')

# --- 2. ALAPBEÁLLÍTÁSOK ---
HIVATALOS_JELSZO = "Velencei670905"
SZARAZ_LISTA = ['509496007', '509500001', '509502005', '524145003', '524149001']
RAKLAP_KOD = '146'

st.set_page_config(page_title="Pékség Vezetői Dashboard", layout="wide")

# --- 3. JELSZÓ ÉS BELÉPÉS ---
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

# --- 4. ADATOK BETÖLTÉSE ---
df_cloud = load_from_drive()

with st.sidebar:
    st.header("📂 Adatkezelés")
    uploaded_files = st.file_uploader("Új havi CSV feltöltése", type="csv", accept_multiple_files=True)
    
    st.divider()
    st.subheader("📈 Áremelés korrekció")
    aremele_datuma = st.date_input("Áremelés napja:", value=pd.to_datetime("2025-01-01"))
    aremele_merteke = st.number_input("Mértéke (%)", value=0)
    
    if st.button("💾 MENTÉS A FELHŐBE"):
        if 'df_final' in st.session_state:
            save_to_drive(st.session_state['df_final'])

# Adatfeldolgozás
data_list = []
if df_cloud is not None:
    data_list.append(df_cloud)

if uploaded_files:
    for f in uploaded_files:
        temp = pd.read_csv(f, sep=';', decimal=',', encoding='latin-1')
        data_list.append(temp)

if data_list:
    df = pd.concat(data_list, ignore_index=True).drop_duplicates()
    
    # Oszlop javítás
    if 'ST_NE' in df.columns and 'ST_NEFT' not in df.columns:
        df = df.rename(columns={'ST_NE': 'ST_NEFT'})
    
    df = df[df['ST_CIKKSZAM'].astype(str).str.strip() != RAKLAP_KOD]
    df['SF_TELJ'] = pd.to_datetime(df['SF_TELJ'], errors='coerce')
    df = df.dropna(subset=['SF_TELJ'])
    
    # Segédoszlopok
    df['Ev'] = df['SF_TELJ'].dt.year
    df['Honap_Nev'] = df['SF_TELJ'].dt.strftime('%m')
    df['Kategória'] = df['ST_CIKKSZAM'].apply(lambda x: "Száraz" if str(x).strip() in SZARAZ_LISTA else "Friss")
    df['Termek_Kereso'] = df['ST_CIKKSZAM'].astype(str) + " - " + df['ST_CIKKNEV']
    
    st.session_state['df_final'] = df

    st.title("📊 Pékség YoY Dashboard")

    # --- SZŰRŐK ---
    c1, c2, c3 = st.columns(3)
    v_partner = c1.selectbox("Partner:", ["Összes"] + sorted(df['SF_UGYFELNEV'].unique().tolist()))
    v_termek = c2.multiselect("Termék:", sorted(df['Termek_Kereso'].unique().tolist()))
    v_kat = c3.multiselect("Kategória:", ["Friss", "Száraz"], default=["Friss", "Száraz"])

    f_df = df[df['Kategória'].isin(v_kat)]
    if v_partner != "Összes": f_df = f_df[f_df['SF_UGYFELNEV'] == v_partner]
    if v_termek: f_df = f_df[f_df['Termek_Kereso'].isin(v_termek)]

    # --- ÖSSZEHASONLÍTÁS ---
    stats_ft = f_df.groupby(['Honap_Nev', 'Ev'])['ST_NEFT'].sum().unstack()
    stats_db = f_df.groupby(['Honap_Nev', 'Ev'])['ST_MENNY'].sum().unstack()

    if len(stats_ft.columns) >= 2:
        evek = sorted(stats_ft.columns)
        tavaly, idei = evek[-2], evek[-1]
        
        diff_df = pd.DataFrame({
            f'Tavaly ({tavaly}) Ft': stats_ft[tavaly],
            f'Idén ({idei}) Ft': stats_ft[idei],
            'Változás Ft': stats_ft[idei] - stats_ft[tavaly],
            'Mennyiség vált. %': ((stats_db[idei] / stats_db[tavaly]) - 1) * 100
        })

        st.subheader(f"📅 Teljesítmény: {tavaly} vs {idei}")
        st.dataframe(diff_df.style.format("{:,.0f} Ft").format("{:+.1f}%", subset=['Mennyiség vált. %']), use_container_width=True)

        # Grafikonok
        g1, g2 = st.columns(2)
        g1.plotly_chart(px.bar(f_df.groupby(['Honap_Nev', 'Ev'])['ST_NEFT'].sum().reset_index(), x='Honap_Nev', y='ST_NEFT', color='Ev', barmode='group', title="Forgalom Ft"), use_container_width=True)
        g2.plotly_chart(px.bar(f_df.groupby(['Honap_Nev', 'Ev'])['ST_MENNY'].sum().reset_index(), x='Honap_Nev', y='ST_MENNY', color='Ev', barmode='group', title="Mennyiség db"), use_container_width=True)

    # --- AI ---
    st.divider()
    openai_key = st.text_input("OpenAI API Key:", type="password")
    if st.button("AI Elemzés indítása"):
        if openai_key:
            client = OpenAI(api_key=openai_key)
            prompt = f"Adatok:\n{f_df.groupby(['Ev', 'Honap_Nev'])['ST_NEFT'].sum().to_string()}\nÁremelés: {aremele_datuma}, {aremele_merteke}%. Elemezd a változást magyarul."
            res = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
            st.info(res.choices[0].message.content)
else:
    st.info("Tölts fel adatokat vagy várj a felhőből való betöltésre!")
