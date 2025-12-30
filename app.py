import streamlit as st
import pandas as pd
import plotly.express as px
from openai import OpenAI
import datetime

# --- 1. KONFIGURÁCIÓ ---
HIVATALOS_JELSZO = "Velencei670905" 

st.set_page_config(
    page_title="Pékség Összehasonlító Dashboard", 
    layout="wide", 
    page_icon="🥐"
)

# --- 2. BIZTONSÁGI BELÉPÉS ---
if "bejelentkezve" not in st.session_state:
    st.session_state["bejelentkezve"] = False

if not st.session_state["bejelentkezve"]:
    st.title("🔐 Belépés")
    with st.form("login"):
        jelszo = st.text_input("Jelszó:", type="password")
        if st.form_submit_button("Belépés"):
            if jelszo == HIVATALOS_JELSZO:
                st.session_state["bejelentkezve"] = True
                st.rerun()
            else: st.error("Hibás jelszó!")
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
    df['ST_CIKKSZAM'] = df['ST_CIKKSZAM'].astype(str).str.strip()
    df['ST_CIKKNEV'] = df['ST_CIKKNEV'].astype(str).str.strip()
    df['SF_UGYFELNEV'] = df['SF_UGYFELNEV'].astype(str).str.strip()
    df = df[df['ST_CIKKSZAM'] != '146']
    df['SF_TELJ'] = pd.to_datetime(df['SF_TELJ'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['SF_TELJ'])
    df['Datum_Csak'] = df['SF_TELJ'].dt.date
    df['Kategória'] = df['ST_CIKKSZAM'].apply(lambda x: "Száraz áru" if x in SZARAZ_LISTA else "Friss áru")
    df['Cikkszam_Nev'] = df['ST_CIKKSZAM'] + " - " + df['ST_CIKKNEV']
    df['ST_NEFT'] = pd.to_numeric(df['ST_NEFT'], errors='coerce').fillna(0)
    df['ST_MENNY'] = pd.to_numeric(df['ST_MENNY'], errors='coerce').fillna(0)
    return df

# --- 4. OLDALSÁV ---
with st.sidebar:
    st.header("📂 Adatok")
    uploaded_files = st.file_uploader("CSV fájlok", type="csv", accept_multiple_files=True)
    if st.button("🚪 Kijelentkezés"):
        st.session_state["bejelentkezve"] = False
        st.rerun()

# --- 5. FŐOLDAL ---
if uploaded_files:
    df = load_data(uploaded_files)
    if df is not None:
        st.title("🥐 Pékség Elemző & Összehasonlító")

        # --- SZŰRŐK ---
        with st.expander("🔍 Időszakok és Szűrők beállítása", expanded=True):
            # Időszak A
            c1, c2 = st.columns(2)
            min_d, max_d = df['Datum_Csak'].min(), df['Datum_Csak'].max()
            
            range_a = c1.date_input(" 'A' időszak (Alap):", [min_d, max_d])
            
            # Időszak B kapcsoló és szűrő
            osszehasonlitas_be = c2.checkbox("Összehasonlítás egy másik időszakkal ('B')", value=False)
            if osszehasonlitas_be:
                range_b = c2.date_input(" 'B' időszak (Összevetés):", [min_d, max_d])
            else:
                range_b = None

            st.divider()
            c3, c4, c5 = st.columns(3)
            v_kat = c3.multiselect("Kategória:", ["Friss áru", "Száraz áru"], ["Friss áru", "Száraz áru"])
            v_partnerek = c4.multiselect("Partnerek:", sorted(list(set(df['SF_UGYFELNEV']))))
            v_termekek = c5.multiselect("Termékek:", sorted(list(set(df['Cikkszam_Nev']))))

        # --- SZŰRÉSI LOGIKA ---
        def filter_data(data, d_range):
            if not (isinstance(d_range, list) or isinstance(d_range, tuple)) or len(d_range) < 2:
                return data.head(0)
            mask = (data['Datum_Csak'] >= d_range[0]) & (data['Datum_Csak'] <= d_range[1])
            res = data[mask]
            if v_kat: res = res[res['Kategória'].isin(v_kat)]
            if v_partnerek: res = res[res['SF_UGYFELNEV'].isin(v_partnerek)]
            if v_termekek: res = res[res['Cikkszam_Nev'].isin(v_termekek)]
            return res

        df_a = filter_data(df, range_a)
        
        # --- MEGJELENÍTÉS ---
        if not df_a.empty:
            if osszehasonlitas_be and range_b:
                df_b = filter_data(df, range_b)
                
                # KPI-k Összehasonlítva
                st.subheader("📊 Időszakok összevetése (A vs B)")
                m1, m2, m3 = st.columns(3)
                
                bev_a, bev_b = df_a['ST_NEFT'].sum(), df_b['ST_NEFT'].sum()
                menny_a, menny_b = df_a['ST_MENNY'].sum(), df_b['ST_MENNY'].sum()
                
                def get_delta(a, b):
                    if b == 0: return "0%"
                    pct = ((a - b) / b) * 100
                    return f"{pct:.1f}%"

                m1.metric("Nettó Bevétel (A)", f"{bev_a:,.0f} Ft".replace(","," "), delta=get_delta(bev_a, bev_b))
                m2.metric("Mennyiség (A)", f"{menny_a:,.0f} db".replace(","," "), delta=get_delta(menny_a, menny_b))
                m3.metric("Bevétel különbség", f"{(bev_a - bev_b):,.0f} Ft".replace(","," "))

                # Összehasonlító grafikon
                df_a_plot = df_a.groupby('Cikkszam_Nev')['ST_NEFT'].sum().reset_index()
                df_a_plot['Időszak'] = 'A'
                df_b_plot = df_b.groupby('Cikkszam_Nev')['ST_NEFT'].sum().reset_index()
                df_b_plot['Időszak'] = 'B'
                
                compare_df = pd.concat([df_a_plot, df_b_plot]).sort_values('ST_NEFT', ascending=False)
                fig = px.bar(compare_df.head(40), x='ST_NEFT', y='Cikkszam_Nev', color='Időszak', 
                             barmode='group', orientation='h', title="Top termékek forgalma: A vs B időszak")
                st.plotly_chart(fig, use_container_width=True)

            else:
                # Sima nézet (csak A időszak)
                st.subheader("📈 'A' időszak eredményei")
                k1, k2 = st.columns(2)
                k1.metric("Bevétel", f"{df_a['ST_NEFT'].sum():,.0f} Ft".replace(","," "))
                k2.metric("Mennyiség", f"{df_a['ST_MENNY'].sum():,.0f} db".replace(","," "))
                
                fig_single = px.bar(df_a.groupby('Cikkszam_Nev')['ST_NEFT'].sum().reset_index().sort_values('ST_NEFT', ascending=False).head(20),
                                   x='ST_NEFT', y='Cikkszam_Nev', orientation='h', title="Top 20 termék")
                st.plotly_chart(fig_single, use_container_width=True)
                
            st.write("📋 **Részletes adatok (A időszak):**")
            st.dataframe(df_a[['Datum_Csak', 'SF_UGYFELNEV', 'Cikkszam_Nev', 'ST_MENNY', 'ST_NEFT']], use_container_width=True)
        else:
            st.warning("Nincs adat az 'A' időszakra.")
else:
    st.info("👋 Töltsd fel a CSV fájlokat a kezdéshez!")
