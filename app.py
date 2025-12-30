import streamlit as st
import pandas as pd
import plotly.express as px
from openai import OpenAI
import datetime

# --- 1. KONFIGURÁCIÓ ---
# Itt módosíthatod a belépési jelszót
HIVATALOS_JELSZO = "Velencei670905" 

st.set_page_config(
    page_title="Pékség Profi Dashboard 2025", 
    layout="wide", 
    page_icon="🥐"
)

# OpenAI kulcs automatikus betöltése a Streamlit Secrets-ből
openai_api_key = st.secrets.get("OPENAI_API_KEY")

# Egyedi stílus a Metric kártyáknak és a nyomtatási képnek
st.markdown("""
    <style>
    @media print {
        .stButton, .stFileUploader, [data-testid="stSidebar"], .stDownloadButton { display: none !important; }
        .main { padding: 0 !important; }
    }
    div[data-testid="metric-container"] {
        background-color: #f8f9fb;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #dee2e6;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. BIZTONSÁGI BELÉPÉS ---
if "bejelentkezve" not in st.session_state:
    st.session_state["bejelentkezve"] = False

if not st.session_state["bejelentkezve"]:
    st.title("🔐 Pékség Adatkezelő - Belépés")
    with st.form("login_form"):
        jelszo = st.text_input("Kérem a jelszót:", type="password")
        if st.form_submit_button("Belépés"):
            if jelszo == HIVATALOS_JELSZO:
                st.session_state["bejelentkezve"] = True
                st.rerun()
            else:
                st.error("❌ Hibás jelszó!")
    st.stop()

# --- 3. ADATKEZELÉS ÉS ELŐKÉSZÍTÉS ---
SZARAZ_LISTA = ['509496007', '509500001', '509502005', '524145003', '524149001']

@st.cache_data
def load_data(uploaded_files):
    all_dfs = []
    for file in uploaded_files:
        try:
            # A pékségi CSV-k általában latin-1 kódolásúak és pontosvesszővel tagoltak
            temp_df = pd.read_csv(file, sep=';', decimal=',', encoding='latin-1')
            all_dfs.append(temp_df)
        except Exception as e:
            st.error(f"Hiba a(z) {file.name} fájlban: {e}")
    
    if not all_dfs:
        return None
    
    df = pd.concat(all_dfs, ignore_index=True)
    
    # Adattisztítás
    df['ST_CIKKSZAM'] = df['ST_CIKKSZAM'].astype(str).str.strip()
    df = df[df['ST_CIKKSZAM'] != '146'] # Teszt vagy hibás cikk kiszűrése
    
    # Dátum kezelés
    df['SF_TELJ'] = pd.to_datetime(df['SF_TELJ'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['SF_TELJ'])
    
    # Extra oszlopok az elemzéshez
    df['Ev'] = df['SF_TELJ'].dt.year
    df['Honap'] = df['SF_TELJ'].dt.month
    df['Ev_Honap'] = df['SF_TELJ'].dt.strftime('%Y-%m')
    df['Kategória'] = df['ST_CIKKSZAM'].apply(lambda x: "Száraz áru" if x in SZARAZ_LISTA else "Friss áru")
    df['Cikkszam_Nev'] = df['ST_CIKKSZAM'] + " - " + df['ST_CIKKNEV'].astype(str)
    
    # Átlagár (Egységár) számítása
    # Kerüljük a nullával való osztást
    df['Atlagar'] = df.apply(lambda x: x['ST_NEFT'] / x['ST_MENNY'] if x['ST_MENNY'] != 0 else 0, axis=1)
    
    return df

# --- 4. OLDALSÁV (SIDEBAR) ---
with st.sidebar:
    st.header("📂 Adatforrás")
    uploaded_files = st.file_uploader("CSV fájlok feltöltése", type="csv", accept_multiple_files=True)
    
    st.divider()
    if openai_api_key:
        st.success("🤖 AI Asszisztens: AKTÍV")
    else:
        st.warning("🤖 AI Asszisztens: KULCS HIÁNYZIK")
        
    if st.button("🚪 Kijelentkezés"):
        st.session_state["bejelentkezve"] = False
        st.rerun()

# --- 5. FŐOLDAL LOGIKA ---
if uploaded_files:
    df = load_data(uploaded_files)
    
    if df is not None:
        st.title("🥐 Pékségi Üzleti Dashboard")

        # --- SZŰRŐK ---
        with st.expander("🔍 Intelligens Szűrők és Összehasonlítás", expanded=True):
            c1, c2, c3 = st.columns(3)
            
            # Hónapok és évek
            elerheto_evek = sorted(df['Ev'].unique(), reverse=True)
            v_honapok = c1.multiselect("Hónap(ok) kiválasztása:", 
                                      options=range(1, 13), 
                                      default=[datetime.datetime.now().month],
                                      format_func=lambda x: f"{x}. hónap")
            
            # Kategória és Partner
            v_kat = c2.multiselect("Kategória:", ["Friss áru", "Száraz áru"], default=["Friss áru", "Száraz áru"])
            partnerek = ["Összes partner"] + sorted(df['SF_UGYFELNEV'].unique().tolist())
            v_partner = c2.selectbox("Partner (Cég):", partnerek)
            
            # Rendezési elv
            v_rendezes = c3.selectbox("Rangsor alapja:", 
                                     options=['ST_MENNY', 'ST_NEFT', 'Atlagar'],
                                     format_func=lambda x: "Mennyiség (db)" if x=='ST_MENNY' else ("Bevétel (Ft)" if x=='ST_NEFT' else "Átlagár (Ft/db)"))
            v_irany = c3.radio("Irány:", ["Csökkenő", "Növekvő"], horizontal=True)

        # SZŰRÉS VÉGREHAJTÁSA
        f_df = df.copy()
        if v_honapok: f_df = f_df[f_df['Honap'].isin(v_honapok)]
        if v_kat: f_df = f_df[f_df['Kategória'].isin(v_kat)]
        if v_partner != "Összes partner": f_df = f_df[f_df['SF_UGYFELNEV'] == v_partner]

        if not f_df.empty:
            # --- 6. ÉV-ÉV (YoY) ÖSSZEHASONLÍTÁS ÉS KPI-K ---
            st.divider()
            
            yoy_agg = f_df.groupby('Ev').agg({'ST_MENNY': 'sum', 'ST_NEFT': 'sum'}).reset_index()
            yoy_agg = yoy_agg.sort_values('Ev', ascending=False)
            
            k1, k2, k3 = st.columns(3)
            
            if len(yoy_agg) >= 2:
                akt = yoy_agg.iloc[0]
                prev = yoy_agg.iloc[1]
                
                # Százalékos eltérések
                bev_pct = ((akt['ST_NEFT'] - prev['ST_NEFT']) / prev['ST_NEFT'] * 100) if prev['ST_NEFT'] != 0 else 0
                menny_pct = ((akt['ST_MENNY'] - prev['ST_MENNY']) / prev['ST_MENNY'] * 100) if prev['ST_MENNY'] != 0 else 0
                
                k1.metric(f"Nettó Bevétel ({akt['Ev']})", f"{akt['ST_NEFT']:,.0f} Ft".replace(",", " "), f"{bev_pct:.1f}% vs {prev['Ev']}")
                k2.metric(f"Mennyiség ({akt['Ev']})", f"{akt['ST_MENNY']:,.0f} db".replace(",", " "), f"{menny_pct:.1f}% vs {prev['Ev']}")
            else:
                akt = yoy_agg.iloc[0]
                k1.metric("Nettó Bevétel", f"{akt['ST_NEFT']:,.0f} Ft".replace(",", " "))
                k2.metric("Mennyiség", f"{akt['ST_MENNY']:,.0f} db".replace(",", " "))
            
            teljes_atlagar = f_df['ST_NEFT'].sum() / f_df['ST_MENNY'].sum() if f_df['ST_MENNY'].sum() != 0 else 0
            k3.metric("Súlyozott Átlagár", f"{teljes_atlagar:,.1f} Ft/db")

            # --- 7. ELEMZÉSI FÜLEK ---
            tab1, tab2, tab3, tab4 = st.tabs(["🏆 Ranglista", "💰 Árelemzés", "📊 Százalékos Összehasonlítás", "🤖 AI Asszisztens"])

            with tab1:
                st.subheader("Termékek / Partnerek rangsora")
                szint = st.radio("Elemzési szint:", ["Termék", "Partner"], horizontal=True)
                group_col = 'Cikkszam_Nev' if szint == "Termék" else 'SF_UGYFELNEV'
                
                rank_df = f_df.groupby(group_col).agg({
                    'ST_MENNY': 'sum', 'ST_NEFT': 'sum', 'Atlagar': 'mean'
                }).reset_index()
                
                rank_df = rank_df.sort_values(v_rendezes, ascending=(v_irany == "Növekvő"))
                
                fig_rank = px.bar(rank_df.head(25), 
                                 x=v_rendezes, y=group_col, 
                                 orientation='h', color=v_rendezes,
                                 color_continuous_scale='Blues' if v_rendezes == 'ST_MENNY' else 'Greens',
                                 text_auto='.3s')
                st.plotly_chart(fig_rank, use_container_width=True)

            with tab2:
                st.subheader("Árpolitika elemzése")
                st.write("Itt láthatod, hogy a különböző partnerek milyen átlagáron vásárolják a termékeket.")
                
                ar_trend = f_df.groupby(['Ev_Honap', 'SF_UGYFELNEV'])['Atlagar'].mean().reset_index()
                fig_ar = px.line(ar_trend, x='Ev_Honap', y='Atlagar', color='SF_UGYFELNEV', markers=True,
                                 title="Átlagár alakulása partnerenként")
                st.plotly_chart(fig_ar, use_container_width=True)
                
                st.dataframe(rank_df[[group_col, 'Atlagar']].sort_values('Atlagar', ascending=False), use_container_width=True)

            with tab3:
                st.subheader("Részletes Százalékos Eltérés (Év vs Év)")
                if len(yoy_agg) >= 2:
                    pivot_compare = f_df.pivot_table(
                        index='Cikkszam_Nev', 
                        columns='Ev', 
                        values='ST_NEFT', 
                        aggfunc='sum', 
                        fill_value=0
                    )
                    
                    # Utolsó két év oszlopa
                    c_akt, c_prev = evek[0], evek[1] if len(evek) > 1 else (None, None)
                    if c_prev:
                        pivot_compare['Eltérés (Ft)'] = pivot_compare[c_akt] - pivot_compare[c_prev]
                        pivot_compare['Eltérés (%)'] = (pivot_compare['Eltérés (Ft)'] / pivot_compare[c_prev] * 100).fillna(0)
                        
                        st.dataframe(pivot_compare.sort_values('Eltérés (%)', ascending=False).style.format(precision=1), use_container_width=True)
                else:
                    st.info("Nincs elegendő év az összehasonlításhoz.")

            with tab4:
                if openai_api_key:
                    st.subheader("Kérdezz az adatokról")
                    user_q = st.text_input("Pl: Melyik termék átlagára nőtt a legjobban? Melyik partner forgalma esett vissza?")
                    if st.button("Elemzés indítása"):
                        try:
                            client = OpenAI(api_key=openai_api_key)
                            # Adatok előkészítése az AI-nak
                            top_summary = rank_df.head(10).to_string()
                            res = client.chat.completions.create(
                                model="gpt-4o",
                                messages=[
                                    {"role": "system", "content": "Te egy profi pékségi üzleti elemző vagy. Válaszolj tömören, számokkal alátámasztva."},
                                    {"role": "user", "content": f"Adatok összefoglalója:\n{top_summary}\n\nKérdés: {user_q}"}
                                ]
                            )
                            st.info(res.choices[0].message.content)
                        except Exception as e:
                            st.error(f"AI hiba: {e}")
                else:
                    st.error("Az AI funkcióhoz be kell állítani az OPENAI_API_KEY-t a Streamlit Secrets-ben!")
        else:
            st.warning("⚠️ Nincs megjeleníthető adat a választott szűrőkkel.")
else:
    st.info("👋 Üdvözöllek! Kezdéshez tölts fel egy vagy több pékségi forgalmi CSV fájlt a bal oldali sávban.")
