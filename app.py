import streamlit as st
import pandas as pd
import plotly.express as px
from openai import OpenAI
import datetime

# --- 1. KONFIGURÁCIÓ ---
HIVATALOS_JELSZO = "Velencei670905" 

st.set_page_config(
    page_title="Pékség Profi Dashboard 2025", 
    layout="wide", 
    page_icon="🥐"
)

openai_api_key = st.secrets.get("OPENAI_API_KEY")

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
            st.error(f"Hiba a(z) {file.name} fájlban: {e}")
    
    if not all_dfs: return None
    
    df = pd.concat(all_dfs, ignore_index=True)
    
    # ADATTISZTÍTÁS - a duplikációk elkerülése végett
    df['ST_CIKKSZAM'] = df['ST_CIKKSZAM'].astype(str).str.strip()
    df['ST_CIKKNEV'] = df['ST_CIKKNEV'].astype(str).str.strip()
    df['SF_UGYFELNEV'] = df['SF_UGYFELNEV'].astype(str).str.strip()
    
    df = df[df['ST_CIKKSZAM'] != '146']
    df['SF_TELJ'] = pd.to_datetime(df['SF_TELJ'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['SF_TELJ'])
    
    df['Ev'] = df['SF_TELJ'].dt.year
    df['Honap'] = df['SF_TELJ'].dt.month
    df['Datum_Csak'] = df['SF_TELJ'].dt.date
    df['Kategória'] = df['ST_CIKKSZAM'].apply(lambda x: "Száraz áru" if x in SZARAZ_LISTA else "Friss áru")
    
    # Itt építjük fel az egyedi azonosítót (Cikkszám + Név)
    df['Cikkszam_Nev'] = df['ST_CIKKSZAM'] + " - " + df['ST_CIKKNEV']
    
    df['Atlagar'] = df.apply(lambda x: x['ST_NEFT'] / x['ST_MENNY'] if x['ST_MENNY'] != 0 else 0, axis=1)
    
    return df

# --- 4. OLDALSÁV ---
with st.sidebar:
    st.header("📂 Adatforrás")
    uploaded_files = st.file_uploader("CSV fájlok feltöltése", type="csv", accept_multiple_files=True)
    if st.button("🚪 Kijelentkezés"):
        st.session_state["bejelentkezve"] = False
        st.rerun()

# --- 5. FŐOLDAL ---
if uploaded_files:
    df = load_data(uploaded_files)
    
    if df is not None:
        st.title("🥐 Pékségi Üzleti Dashboard")

        # --- SZŰRŐK ---
        with st.expander("🔍 Összes szűrő (Dátum, Kategória, Partner, Termék)", expanded=True):
            c1, c2 = st.columns(2)
            c3, c4 = st.columns(2)
            
            # 1. NAPTÁRAS TÓL-IG SZŰRŐ
            min_date = df['Datum_Csak'].min()
            max_date = df['Datum_Csak'].max()
            date_range = c1.date_input("Időszak (Tól - Ig):", 
                                       value=(min_date, max_date),
                                       min_value=min_date,
                                       max_value=max_date)
            
            # 2. KATEGÓRIA SZŰRŐ
            v_kat = c2.multiselect("Termék kategória:", 
                                   options=["Friss áru", "Száraz áru"], 
                                   default=["Friss áru", "Száraz áru"])
            
            # 3. PARTNER SZŰRŐ (Tisztított lista)
            v_partnerek = c3.multiselect("Partnerek kiválasztása:", 
                                         options=sorted(list(set(df['SF_UGYFELNEV'].dropna()))),
                                         placeholder="Összes partner")
            
            # 4. TERMÉK SZŰRŐ (Cikkszám és Név együtt, duplikáció mentesen)
            v_termekek = c4.multiselect("Konkrét termékek (Cikkszám - Név):", 
                                        options=sorted(list(set(df['Cikkszam_Nev'].dropna()))))
            
            st.divider()
            v_rendezes = st.selectbox("Rangsor alapja:", 
                                     options=['ST_MENNY', 'ST_NEFT', 'Atlagar'],
                                     format_func=lambda x: "Mennyiség (db)" if x=='ST_MENNY' else ("Bevétel (Ft)" if x=='ST_NEFT' else "Átlagár (Ft/db)"))

        # --- SZŰRÉS VÉGREHAJTÁSA ---
        f_df = df.copy()
        
        if isinstance(date_range, tuple) and len(date_range) == 2:
            f_df = f_df[(f_df['Datum_Csak'] >= date_range[0]) & (f_df['Datum_Csak'] <= date_range[1])]
        
        if v_kat:
            f_df = f_df[f_df['Kategória'].isin(v_kat)]
            
        if v_partnerek:
            f_df = f_df[f_df['SF_UGYFELNEV'].isin(v_partnerek)]
            
        if v_termekek:
            f_df = f_df[f_df['Cikkszam_Nev'].isin(v_termekek)]

        if not f_df.empty:
            # --- 6. KPI-K ---
            k1, k2, k3 = st.columns(3)
            total_bev = f_df['ST_NEFT'].sum()
            total_menny = f_df['ST_MENNY'].sum()
            avg_pr = total_bev / total_menny if total_menny != 0 else 0
            
            k1.metric("Szűrt Bevétel", f"{total_bev:,.0f} Ft".replace(",", " "))
            k2.metric("Szűrt Mennyiség", f"{total_menny:,.0f} db".replace(",", " "))
            k3.metric("Átlagár", f"{avg_pr:,.1f} Ft/db")

            # --- 7. TABS ---
            tab1, tab2, tab3 = st.tabs(["🏆 Rangsorok", "📈 Trendek", "📋 Részletes Adatok"])

            with tab1:
                szint = st.radio("Elemzés szintje:", ["Termék", "Partner"], horizontal=True)
                group_col = 'Cikkszam_Nev' if szint == "Termék" else 'SF_UGYFELNEV'
                
                rank_df = f_df.groupby(group_col).agg({
                    'ST_MENNY': 'sum', 'ST_NEFT': 'sum', 'Atlagar': 'mean'
                }).reset_index().sort_values(v_rendezes, ascending=False)
                
                fig_rank = px.bar(rank_df.head(25), x=v_rendezes, y=group_col, orientation='h', 
                                 color=v_rendezes, color_continuous_scale='Turbo', text_auto='.3s')
                # Grafikon javítása, hogy ne legyen fejjel lefelé a rangsor
                fig_rank.update_layout(yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig_rank, use_container_width=True)

            with tab2:
                st.subheader("Időbeli alakulás")
                trend_df = f_df.groupby(['Datum_Csak', 'Kategória'])[v_rendezes].sum().reset_index()
                fig_trend = px.line(trend_df, x='Datum_Csak', y=v_rendezes, color='Kategória', markers=True)
                st.plotly_chart(fig_trend, use_container_width=True)

            with tab3:
                # Itt is a tisztított oszlopokat mutatjuk
                st.dataframe(f_df[['SF_TELJ', 'SF_UGYFELNEV', 'Cikkszam_Nev', 'ST_MENNY', 'ST_NEFT', 'Atlagar']].sort_values('SF_TELJ'), use_container_width=True)

        else:
            st.warning("⚠️ Nincs találat a szűrők alapján.")
else:
    st.info("👋 Töltsd fel a CSV fájlokat a kezdéshez!")
