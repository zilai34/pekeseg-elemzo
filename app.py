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

# --- 3. ADATKEZELÉS ---
@st.cache_data
def load_data(uploaded_files):
    all_dfs = []
    for file in uploaded_files:
        try:
            # Megpróbáljuk beolvasni (pontosvesszővel vagy vesszővel)
            try:
                temp_df = pd.read_csv(file, sep=';', decimal=',', encoding='latin-1')
            except:
                temp_df = pd.read_csv(file, sep=',', decimal='.', encoding='utf-8')
            
            # Oszlopnevek egységesítése
            rename_map = {'ST_NE': 'ST_NEFT', 'ST_NE_FT': 'ST_NEFT'}
            temp_df.rename(columns=rename_map, inplace=True)
            
            # Itt javítottam: Ellenőrizzük, hogy az oszlop egyáltalán létezik-e, mielőtt számmá alakítjuk
            if 'ST_NEFT' in temp_df.columns:
                temp_df['ST_NEFT'] = pd.to_numeric(temp_df['ST_NEFT'], errors='coerce').fillna(0)
            if 'ST_MENNY' in temp_df.columns:
                temp_df['ST_MENNY'] = pd.to_numeric(temp_df['ST_MENNY'], errors='coerce').fillna(0)
            
            all_dfs.append(temp_df)
        except Exception as e:
            st.error(f"Hiba a(z) {file.name} beolvasásakor: {e}")
            continue
    
    if not all_dfs: return None
    
    # Összefűzés
    df = pd.concat(all_dfs, ignore_index=True)
    df = df.loc[:, ~df.columns.duplicated()]

    # Alapvető tisztítás
    df['ST_CIKKSZAM'] = df['ST_CIKKSZAM'].astype(str).str.strip()
    df['ST_CIKKNEV'] = df['ST_CIKKNEV'].astype(str).str.strip()
    df['SF_UGYFELNEV'] = df['SF_UGYFELNEV'].astype(str).str.strip()
    
    # Dátum kezelése
    df['SF_TELJ'] = pd.to_datetime(df['SF_TELJ'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['SF_TELJ'])
    df['Datum_Csak'] = df['SF_TELJ'].dt.date
    
    # Termék azonosító
    df['Cikkszam_Nev'] = df['ST_CIKKSZAM'] + " - " + df['ST_CIKKNEV']
    
    # Egységár az aritmetikai átlaghoz
    df['Egyseg_Ar'] = 0.0
    mask = df['ST_MENNY'] != 0
    df.loc[mask, 'Egyseg_Ar'] = df.loc[mask, 'ST_NEFT'] / df.loc[mask, 'ST_MENNY']
    
    return df

# --- 4. OLDALSÁV ---
with st.sidebar:
    st.header("📂 Adatok")
    files = st.file_uploader("CSV fájlok feltöltése", accept_multiple_files=True)
    st.divider()
    st.subheader("🛠️ Funkciók")
    # 2. KÉRÉS: Anomália-szűrő kapcsoló
    anomaly_filter_on = st.checkbox("Anomáliák (0 Ft) kiszűrése a grafikonról", value=False)
    
    if st.button("🚪 Kijelentkezés"):
        st.session_state["bejelentkezve"] = False
        st.rerun()

# --- 5. FŐOLDAL ---
if files:
    df_raw = load_data(files)
    if df_raw is not None:
        # Anomáliák kigyűjtése
        anomalies = df_raw[df_raw['ST_NEFT'] == 0].copy()
        
        # Szűrés a kapcsoló alapján
        df = df_raw[df_raw['ST_NEFT'] > 0].copy() if anomaly_filter_on else df_raw.copy()

        st.title("🥐 Pékség Elemző Dashboard")

        with st.expander("🔍 Időszakok és Termékek", expanded=True):
            c1, c2 = st.columns(2)
            min_d, max_d = df['Datum_Csak'].min(), df['Datum_Csak'].max()
            d_range_a = c1.date_input("A időszak", [min_d, max_d])
            d_range_b = c2.date_input("B időszak", [min_d, max_d])
            v_prod = st.multiselect("Termékek:", options=sorted(df['Cikkszam_Nev'].unique().tolist()))

        def get_p(d_range, label):
            if not isinstance(d_range, (list, tuple)) or len(d_range) < 2: return df.head(0)
            mask = (df['Datum_Csak'] >= d_range[0]) & (df['Datum_Csak'] <= d_range[1])
            res = df[mask].copy()
            if v_prod: res = res[res['Cikkszam_Nev'].isin(v_prod)]
            res['Időszak'] = label
            return res

        df_a, df_b = get_p(d_range_a, 'A'), get_p(d_range_b, 'B')

        if not df_a.empty:
            st.divider()
            # 1. KÉRÉS: A 4 metrika
            metrika = st.radio("Válassz metrikát:", 
                               ["Érték (Ft)", "Mennyiség (db)", "Súlyozott átlagár (Ft/db)", "Aritmetikai átlagár (Ft/db)"], 
                               horizontal=True)

            def calc(data):
                if metrika == "Érték (Ft)": return data.groupby('Cikkszam_Nev')['ST_NEFT'].sum()
                if metrika == "Mennyiség (db)": return data.groupby('Cikkszam_Nev')['ST_MENNY'].sum()
                if metrika == "Súlyozott átlagár (Ft/db)":
                    g = data.groupby('Cikkszam_Nev').agg({'ST_NEFT':'sum', 'ST_MENNY':'sum'})
                    return (g['ST_NEFT'] / g['ST_MENNY']).fillna(0)
                return data.groupby('Cikkszam_Nev')['Egyseg_Ar'].mean()

            s_a, s_b = calc(df_a).rename('A_Val'), calc(df_b).rename('B_Val')
            comp = pd.concat([s_a, s_b], axis=1).fillna(0)
            
            def get_pct(row):
                if row['B_Val'] == 0: return "Új" if row['A_Val'] > 0 else ""
                v = ((row['A_Val'] - row['B_Val']) / row['B_Val']) * 100
                return f"{'+' if v > 0 else ''}{v:.1f}%"
            comp['Pct'] = comp.apply(get_pct, axis=1)

            plot_df = comp.reset_index().melt(id_vars=['Cikkszam_Nev', 'Pct'], value_vars=['A_Val', 'B_Val'], var_name='Idő', value_name='Mertek')
            plot_df['Label'] = plot_df.apply(lambda x: x['Pct'] if x['Idő'] == 'A_Val' else "", axis=1)

            fig = px.bar(plot_df, x='Mertek', y='Cikkszam_Nev', color='Idő', barmode='group', orientation='h', text='Label',
                         color_discrete_map={'A_Val': '#1f77b4', 'B_Val': '#aec7e8'})
            fig.update_traces(textposition='outside')
            st.plotly_chart(fig, use_container_width=True)

            st.subheader("📋 Tranzakciók")
            st.dataframe(pd.concat([df_a, df_b])[['Időszak', 'Datum_Csak', 'SF_UGYFELNEV', 'Cikkszam_Nev', 'ST_MENNY', 'ST_NEFT', 'Egyseg_Ar']].sort_values('Datum_Csak'), use_container_width=True)

        # 3. KÉRÉS: Anomália jelentés az oldal alján
        st.divider()
        st.subheader("🚩 Anomália Jelentés (0 Ft-os tételek)")
        if not anomalies.empty:
            st.warning(f"Találtam {len(anomalies)} darab 0 Ft-os tételt.")
            st.dataframe(anomalies[['Datum_Csak', 'SF_UGYFELNEV', 'Cikkszam_Nev', 'ST_MENNY', 'ST_NEFT']], use_container_width=True)
        else:
            st.success("Nem található anomália.")
else:
    st.info("👋 Kérlek, töltsd fel a CSV fájlokat!")
