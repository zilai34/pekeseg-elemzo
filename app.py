import streamlit as st
import pandas as pd
import plotly.express as px
from openai import OpenAI
import io

# ==========================================
# 1. KONFIGURÁCIÓ
# ==========================================
HIVATALOS_JELSZO = "Velencei670905"
RAKLAP_KOD = '146'

# ==========================================
# 2. BELÉPÉSI RENDSZER
# ==========================================
st.set_page_config(page_title="Pékség Dashboard (Teszt)", layout="wide")

if "bejelentkezve" not in st.session_state:
    st.session_state["bejelentkezve"] = False

if not st.session_state["bejelentkezve"]:
    st.title("🔐 Pékség Belépés")
    col_login, _ = st.columns([1, 2])
    with col_login:
        jelszo_input = st.text_input("Jelszó:", type="password")
        if st.button("Belépés"):
            if jelszo_input == HIVATALOS_JELSZO:
                st.session_state["bejelentkezve"] = True
                st.rerun()
            else:
                st.error("❌ Hibás jelszó!")
    st.stop()

# ==========================================
# 3. OLDALSÁV ÉS FELTÖLTÉS
# ==========================================
st.title("📊 Pékség Adat-Elemző (Drive nélkül)")

with st.sidebar:
    st.header("📁 Adatfeltöltés")
    st.info("Ebben a módban a mentés nem marad meg frissítés után.")
    uploaded_files = st.file_uploader("Válassz ki egy vagy több havi CSV-t", type="csv", accept_multiple_files=True)
    
    st.divider()
    aremele_merteke = st.number_input("Áremelés (%)", value=0)

# Adatok feldolgozása a memóriában
if uploaded_files:
    temp_list = []
    for f in uploaded_files:
        try:
            # Megpróbáljuk beolvasni a fájlt
            new_data = pd.read_csv(f, sep=';', decimal=',', encoding='latin-1')
            temp_list.append(new_data)
        except Exception as e:
            st.error(f"Hiba a fájl beolvasásakor ({f.name}): {e}")
    
    if temp_list:
        df = pd.concat(temp_list, ignore_index=True).drop_duplicates()
        
        # --- ADATTISZTÍTÁS ---
        if 'ST_NE' in df.columns:
            df = df.rename(columns={'ST_NE': 'ST_NEFT'})
        
        # Raklap szűrés és dátum kezelés
        df = df[df['ST_CIKKSZAM'].astype(str).str.strip() != RAKLAP_KOD]
        df['SF_TELJ'] = pd.to_datetime(df['SF_TELJ'], errors='coerce')
        df = df.dropna(subset=['SF_TELJ'])
        
        df['Ev'] = df['SF_TELJ'].dt.year
        df['Honap'] = df['SF_TELJ'].dt.strftime('%m')
        df['Termek_Kereso'] = df['ST_CIKKSZAM'].astype(str) + " - " + df['ST_CIKKNEV']

        # --- SZŰRŐK ÉS MEGJELENÍTÉS ---
        c1, c2 = st.columns(2)
        v_partner = c1.selectbox("Partner:", ["Összes"] + sorted(df['SF_UGYFELNEV'].unique().tolist()))
        v_termekek = c2.multiselect("Termékek:", sorted(df['Termek_Kereso'].unique().tolist()))

        f_df = df.copy()
        if v_partner != "Összes":
            f_df = f_df[f_df['SF_UGYFELNEV'] == v_partner]
        if v_termekek:
            f_df = f_df[f_df['Termek_Kereso'].isin(v_termekek)]

        # Táblázat
        st.subheader("Havi árbevétel (Év/Év)")
        stats = f_df.groupby(['Honap', 'Ev'])['ST_NEFT'].sum().unstack()
        
        if not stats.empty:
            st.dataframe(
                stats, 
                use_container_width=True,
                column_config={str(ev): st.column_config.NumberColumn(format="%.0f Ft") for ev in stats.columns}
            )
            
            # Diagram
            fig = px.bar(
                f_df.groupby(['Honap', 'Ev'])['ST_NEFT'].sum().reset_index(), 
                x='Honap', y='ST_NEFT', color='Ev', barmode='group',
                height=500
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # --- AI RÉSZ ---
        st.divider()
        st.subheader("🤖 AI Elemzés")
        openai_key = st.text_input("OpenAI API kulcs:", type="password")
        if st.button("Elemzés indítása"):
            if openai_key:
                client = OpenAI(api_key=openai_key)
                ai_data = f_df.groupby(['Ev', 'Honap'])['ST_NEFT'].sum().to_string()
                prompt = f"Pékség adatok:\n{ai_data}\nÍrj rövid elemzést magyarul!"
                response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
                st.info(response.choices[0].message.content)
            else:
                st.warning("Adj meg API kulcsot!")
    else:
        st.info("Tölts fel legalább egy CSV fájlt!")
else:
    st.info("Várom a CSV fájlokat a bal oldali sávban...")
