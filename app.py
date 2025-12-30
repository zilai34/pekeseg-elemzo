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
            # Próbálkozás pontosvesszővel (SQL export)
            temp_df = pd.read_csv(file, sep=';', decimal=',', encoding='latin-1')
        except:
            try:
                # Próbálkozás vesszővel (Standard CSV)
                temp_df = pd.read_csv(file, sep=',', decimal='.', encoding='utf-8')
            except:
                continue
        
        # Oszlopnevek egységesítése fájlonként (ez megelőzi a TypeError-t)
        rename_map = {'ST_NE': 'ST_NEFT', 'ST_NE_FT': 'ST_NEFT'}
        temp_df.rename(columns=rename_map, inplace=True)
        
        # Alapvető típuskonverziók fájlonként
        if 'ST_NEFT' in temp_df.columns:
            temp_df['ST_NEFT'] = pd.to_numeric(temp_df['ST_NEFT'], errors='coerce').fillna(0)
        if 'ST_MENNY' in temp_df.columns:
            temp_df['ST_MENNY'] = pd.to_numeric(temp_df['ST_MENNY'], errors='coerce').fillna(0)
        
        all_dfs.append(temp_df)
    
    if not all_dfs: return None
    df = pd.concat(all_dfs, ignore_index=True)
    
    # Duplikált oszlopok kezelése (ha a concat mégis létrehozna ST_NEFT_x, ST_NEFT_y oszlopokat)
    df = df.loc[:, ~df.columns.duplicated()]
    
    # Szöveges adatok tisztítása
    for col in ['ST_CIKKSZAM', 'ST_CIKKNEV', 'SF_UGYFELNEV', 'Cikkszam_Nev']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    
    # Dátum kezelése
    if 'SF_TELJ' in df.columns:
        df['SF_TELJ'] = pd.to_datetime(df['SF_TELJ'], dayfirst=True, errors='coerce')
    elif 'Datum_Csak' in df.columns:
        df['SF_TELJ'] = pd.to_datetime(df['Datum_Csak'], errors='coerce')
        
    df = df.dropna(subset=['SF_TELJ'])
    df['Datum_Csak'] = df['SF_TELJ'].dt.date
    
    # Cikkszám + Név oszlop létrehozása, ha még nincs
    if 'Cikkszam_Nev' not in df.columns:
        df['Cikkszam_Nev'] = df['ST_CIKKSZAM'] + " - " + df.get('ST_CIKKNEV', 'Ismeretlen')
    
    # SORONKÉNTI EGYSÉGÁR (Az aritmetikai átlaghoz)
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
    anomaly_filter_on = st.checkbox("Anomáliák (0 Ft) kiszűrése a grafikonról", value=False)
    
    if st.button("🚪 Kijelentkezés"):
        st.session_state["bejelentkezve"] = False
        st.rerun()

# --- 5. FŐOLDAL ---
if files:
    df_raw = load_data(files)
    if df_raw is not None:
        # Anomáliák detektálása (ahol az érték 0 vagy negatív)
        anomalies = df_raw[df_raw['ST_NEFT'] <= 0].copy()
        
        # Szűrt adat létrehozása
        if anomaly_filter_on:
            df = df_raw[df_raw['ST_NEFT'] > 0].copy()
        else:
            df = df_raw.copy()

        # Termék lista a szűrőhöz
        prod_list = sorted(df['Cikkszam_Nev'].unique().tolist())
        
        st.title("🥐 Pékség Elemző Dashboard")

        with st.expander("🔍 Időszakok és Termékek", expanded=True):
            c1, c2 = st.columns(2)
            min_d, max_d = df['Datum_Csak'].min(), df['Datum_Csak'].max()
            d_range_a = c1.date_input("A időszak", [min_d, max_d])
            d_range_b = c2.date_input("B időszak", [min_d, max_d])
            v_prod = st.multiselect("Termékek kiválasztása:", options=prod_list)

        def get_period_data(d_range, label):
            if not isinstance(d_range, (list, tuple)) or len(d_range) < 2: return df.head(0)
            mask = (df['Datum_Csak'] >= d_range[0]) & (df['Datum_Csak'] <= d_range[1])
            res = df[mask].copy()
            if v_prod: res = res[res['Cikkszam_Nev'].isin(v_prod)]
            res['Időszak'] = label
            return res

        df_a = get_period_data(d_range_a, 'A')
        df_b = get_period_data(d_range_b, 'B')

        if not df_a.empty:
            st.divider()
            # A 4 metrika
            metrika = st.radio("Válassz metrikát a grafikonhoz:", 
                               ["Érték (Ft)", "Mennyiség (db)", "Súlyozott átlagár (Ft/db)", "Aritmetikai átlagár (Ft/db)"], 
                               horizontal=True)

            def calc_metrics(data):
                if metrika == "Érték (Ft)": return data.groupby('Cikkszam_Nev')['ST_NEFT'].sum()
                if metrika == "Mennyiség (db)": return data.groupby('Cikkszam_Nev')['ST_MENNY'].sum()
                if metrika == "Súlyozott átlagár (Ft/db)":
                    g = data.groupby('Cikkszam_Nev').agg({'ST_NEFT':'sum', 'ST_MENNY':'sum'})
                    return (g['ST_NEFT'] / g['ST_MENNY']).fillna(0)
                if metrika == "Aritmetikai átlagár (Ft/db)":
                    return data.groupby('Cikkszam_Nev')['Egyseg_Ar'].mean()

            s_a = calc_metrics(df_a).rename('A_Val')
            s_b = calc_metrics(df_b).rename('B_Val')
            comp = pd.concat([s_a, s_b], axis=1).fillna(0)
            
            def get_pct(row):
                if row['B_Val'] == 0: return "Új" if row['A_Val'] > 0 else ""
                v = ((row['A_Val'] - row['B_Val']) / row['B_Val']) * 100
                return f"{'+' if v > 0 else ''}{v:.1f}%"
            comp['Pct'] = comp.apply(get_pct, axis=1)

            plot_df = comp.reset_index().melt(id_vars=['Cikkszam_Nev', 'Pct'], value_vars=['A_Val', 'B_Val'], var_name='Idő', value_name='Mérték')
            plot_df['Idő'] = plot_df['Idő'].str.replace('_Val', '')
            plot_df['Label'] = plot_df.apply(lambda x: x['Pct'] if x['Idő'] == 'A' else "", axis=1)

            fig = px.bar(plot_df, x='Mérték', y='Cikkszam_Nev', color='Idő', barmode='group', orientation='h', text='Label',
                         color_discrete_map={'A': '#1f77b4', 'B': '#aec7e8'}, labels={'Mérték': metrika, 'Cikkszam_Nev': 'Termék'})
            fig.update_traces(textposition='outside')
            st.plotly_chart(fig, use_container_width=True)

            st.subheader("📋 Tranzakciók részletei")
            df_final = pd.concat([df_a, df_b])
            st.dataframe(df_final[['Időszak', 'Datum_Csak', 'SF_UGYFELNEV', 'Cikkszam_Nev', 'ST_MENNY', 'ST_NEFT', 'Egyseg_Ar']].sort_values('Datum_Csak'), use_container_width=True)

        # --- ANOMÁLIA JELENTÉS AZ OLDAL ALJÁN ---
        st.divider()
        st.subheader("🚩 Anomália Jelentés")
        if not anomalies.empty:
            st.warning(f"Figyelem! {len(anomalies)} darab 0 Ft-os vagy hibás tételt találtam az adatokban.")
            st.write("Ezek a tételek az oldal alján láthatóak, és az oldalsávban lévő kapcsolóval szűrhetőek.")
            st.dataframe(anomalies[['Datum_Csak', 'SF_UGYFELNEV', 'Cikkszam_Nev', 'ST_MENNY', 'ST_NEFT']], use_container_width=True)
        else:
            st.success("🎉 Nem találtam 0 Ft-os anomáliát a feltöltött fájlokban.")
else:
    st.info("👋 Kérlek, töltsd fel a CSV fájlokat az induláshoz!")
