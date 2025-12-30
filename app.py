import streamlit as st
import pandas as pd
import plotly.express as px
import datetime

# --- 1. KONFIGURÁCIÓ ---
HIVATALOS_JELSZO = "Velencei670905" 

st.set_page_config(
    page_title="Pékség Profi Dashboard 2025", 
    layout="wide", 
    page_icon="🥐"
)

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

# --- 3. ADATKEZELÉS ÉS TISZTÍTÁS ---
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
    
    # Szigorú tisztítás a duplikációk ellen
    df['ST_CIKKSZAM'] = df['ST_CIKKSZAM'].astype(str).str.strip()
    df['ST_CIKKNEV'] = df['ST_CIKKNEV'].astype(str).str.strip()
    df['SF_UGYFELNEV'] = df['SF_UGYFELNEV'].astype(str).str.strip()
    
    df = df[df['ST_CIKKSZAM'] != '146']
    
    df['SF_TELJ'] = pd.to_datetime(df['SF_TELJ'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['SF_TELJ'])
    df['Datum_Csak'] = df['SF_TELJ'].dt.date
    
    df['Kategória'] = df['ST_CIKKSZAM'].apply(lambda x: "Száraz áru" if x in SZARAZ_LISTA else "Friss áru")
    
    # Numerikus adatok
    df['ST_NEFT'] = pd.to_numeric(df['ST_NEFT'], errors='coerce').fillna(0)
    df['ST_MENNY'] = pd.to_numeric(df['ST_MENNY'], errors='coerce').fillna(0)
    
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
        st.title("🥐 Pékségi Összehasonlító Dashboard")

        # --- EGYEDI CIKKSZÁM LISTA ELŐKÉSZÍTÉSE (Összevonás) ---
        # Cikkszám szerint csoportosítunk, és vesszük az első előforduló nevet
        product_lookup = df.groupby('ST_CIKKSZAM')['ST_CIKKNEV'].first().reset_index()
        product_lookup['Display_Name'] = product_lookup['ST_CIKKSZAM'] + " - " + product_lookup['ST_CIKKNEV']
        product_options = sorted(product_lookup['Display_Name'].tolist())

        # --- SZŰRŐK ---
        with st.expander("🔍 Időszakok és Termékszűrők beállítása", expanded=True):
            c1, c2 = st.columns(2)
            min_d, max_d = df['Datum_Csak'].min(), df['Datum_Csak'].max()
            
            range_a = c1.date_input("'A' időszak (Alap):", [min_d, max_d])
            osszehasonlitas_be = c2.checkbox("Összehasonlítás egy másik időszakkal ('B')", value=False)
            
            if osszehasonlitas_be:
                range_b = c2.date_input("'B' időszak (Összevetés):", [min_d, max_d])
            else:
                range_b = None

            st.divider()
            c3, c4, c5 = st.columns(3)
            
            v_kat = c3.multiselect("Kategória:", ["Friss áru", "Száraz áru"], ["Friss áru", "Száraz áru"])
            v_partnerek = c4.multiselect("Partnerek:", sorted(list(set(df['SF_UGYFELNEV']))))
            
            # Itt használjuk az összevont listát
            v_termek_nevek = c5.multiselect("Termékek (Cikkszám - Név):", options=product_options)
            
            # Visszakeressük a kiválasztott cikkszámokat
            v_cikkszamok = [name.split(" - ")[0] for name in v_termek_nevek]

        # --- SZŰRÉSI FÜGGVÉNY ---
        def filter_data(data, d_range, period_label):
            if not (isinstance(d_range, list) or isinstance(d_range, tuple)) or len(d_range) < 2:
                return data.head(0)
            mask = (data['Datum_Csak'] >= d_range[0]) & (data['Datum_Csak'] <= d_range[1])
            res = data[mask].copy()
            if v_kat: res = res[res['Kategória'].isin(v_kat)]
            if v_partnerek: res = res[res['SF_UGYFELNEV'].isin(v_partnerek)]
            if v_cikkszamok: res = res[res['ST_CIKKSZAM'].isin(v_cikkszamok)]
            res['Időszak'] = period_label
            # Létrehozzuk a Cikkszam_Nev oszlopot az egységes névvel a grafikonhoz
            res['Cikkszam_Nev'] = res['ST_CIKKSZAM'].map(product_lookup.set_index('ST_CIKKSZAM')['Display_Name'])
            return res

        df_a = filter_data(df, range_a, 'A')

        # --- MEGJELENÍTÉS ---
        if not df_a.empty:
            if osszehasonlitas_be and range_b:
                df_b = filter_data(df, range_b, 'B')
                df_combined = pd.concat([df_a, df_b])
                
                # KPI-K
                st.subheader("📊 Időszakok összevetése (A vs B)")
                m1, m2, m3 = st.columns(3)
                bev_a, bev_b = df_a['ST_NEFT'].sum(), df_b['ST_NEFT'].sum()
                menny_a, menny_b = df_a['ST_MENNY'].sum(), df_b['ST_MENNY'].sum()
                
                def get_delta(a, b):
                    if b == 0: return "0%"
                    return f"{((a - b) / b) * 100:.1f}%"

                m1.metric("Nettó Bevétel (A)", f"{bev_a:,.0f} Ft".replace(","," "), delta=get_delta(bev_a, bev_b))
                m2.metric("Mennyiség (A)", f"{menny_a:,.0f} db".replace(","," "), delta=get_delta(menny_a, menny_b))
                m3.metric("Bevétel különbség (A-B)", f"{(bev_a - bev_b):,.0f} Ft".replace(","," "))

                # DINAMIKUS MAGASSÁGÚ GRAFIKON
                st.divider()
                st.subheader("📦 Termékforgalom összevont cikkszámok alapján (A vs B)")
                
                plot_data = df_combined.groupby(['Cikkszam_Nev', 'Időszak'])['ST_NEFT'].sum().reset_index()
                sorrend = plot_data.groupby('Cikkszam_Nev')['ST_NEFT'].sum().sort_values(ascending=True).index
                chart_height = max(400, len(sorrend) * 30)

                fig = px.bar(
                    plot_data, x='ST_NEFT', y='Cikkszam_Nev', color='Időszak', 
                    barmode='group', orientation='h',
                    category_orders={"Cikkszam_Nev": list(sorrend)},
                    height=chart_height,
                    color_discrete_map={'A': '#1f77b4', 'B': '#aec7e8'},
                    labels={'ST_NEFT': 'Nettó árbevétel (Ft)', 'Cikkszam_Nev': 'Termék (Cikkszám alapján összevont)'}
                )
                st.plotly_chart(fig, use_container_width=True)

                # TÁBLÁZAT
                st.divider()
                st.subheader("📋 Összevont tranzakciós lista")
                st.dataframe(
                    df_combined[['Időszak', 'Datum_Csak', 'SF_UGYFELNEV', 'Cikkszam_Nev', 'ST_MENNY', 'ST_NEFT']]
                    .sort_values(['Datum_Csak', 'Időszak']), 
                    use_container_width=True
                )

            else:
                # Sima nézet csak 'A' időszakkal
                st.subheader("📈 'A' időszak adatai")
                k1, k2 = st.columns(2)
                k1.metric("Bevétel", f"{df_a['ST_NEFT'].sum():,.0f} Ft".replace(","," "))
                k2.metric("Mennyiség", f"{df_a['ST_MENNY'].sum():,.0f} db".replace(","," "))
                
                single_plot = df_a.groupby('Cikkszam_Nev')['ST_NEFT'].sum().reset_index().sort_values('ST_NEFT', ascending=True)
                fig_single = px.bar(single_plot, x='ST_NEFT', y='Cikkszam_Nev', orientation='h', 
                                   height=max(400, len(single_plot)*25), title="Összevont terméklista")
                st.plotly_chart(fig_single, use_container_width=True)
                
                st.dataframe(df_a[['Datum_Csak', 'SF_UGYFELNEV', 'Cikkszam_Nev', 'ST_MENNY', 'ST_NEFT']], use_container_width=True)
        else:
            st.warning("⚠️ Nincs adat az 'A' időszakra.")
else:
    st.info("👋 Töltsd fel a CSV fájlokat a kezdéshez!")
