import streamlit as st
import pandas as pd
import plotly.express as px

# --- 1. KONFIGURÁCIÓ ---
HIVATALOS_JELSZO = "Velencei670905" 
st.set_page_config(page_title="Pékség Profi Dashboard 2025", layout="wide", page_icon="🥐")

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

# --- 2. ADATKEZELÉS ---
@st.cache_data
def load_data(uploaded_files):
    all_dfs = []
    for file in uploaded_files:
        try:
            df_tmp = pd.read_csv(file, sep=';', decimal=',', encoding='latin-1')
            all_dfs.append(df_tmp)
        except:
            try:
                df_tmp = pd.read_csv(file, sep=',', decimal='.', encoding='utf-8')
                all_dfs.append(df_tmp)
            except: pass
            
    if not all_dfs: return None
    df = pd.concat(all_dfs, ignore_index=True)
    
    # Oszlopnevek igazítása
    rename_map = {'ST_NE': 'ST_NEFT', 'ST_NE_FT': 'ST_NEFT'}
    df.rename(columns=rename_map, inplace=True)
    
    df['ST_CIKKSZAM'] = df['ST_CIKKSZAM'].astype(str).str.strip()
    df['ST_CIKKNEV'] = df['ST_CIKKNEV'].astype(str).str.strip()
    df['SF_UGYFELNEV'] = df['SF_UGYFELNEV'].astype(str).str.strip()
    
    df['SF_TELJ'] = pd.to_datetime(df['SF_TELJ'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['SF_TELJ'])
    df['Datum_Csak'] = df['SF_TELJ'].dt.date
    
    df['ST_NEFT'] = pd.to_numeric(df['ST_NEFT'], errors='coerce').fillna(0)
    df['ST_MENNY'] = pd.to_numeric(df['ST_MENNY'], errors='coerce').fillna(0)
    
    # Egységár soronként
    df['Egyseg_Ar'] = 0.0
    mask = df['ST_MENNY'] != 0
    df.loc[mask, 'Egyseg_Ar'] = df.loc[mask, 'ST_NEFT'] / df.loc[mask, 'ST_MENNY']
    
    return df

# --- 3. OLDALSÁV ---
with st.sidebar:
    st.header("📂 Adatforrás")
    files = st.file_uploader("CSV fájlok feltöltése", accept_multiple_files=True)
    if st.button("🚪 Kijelentkezés"):
        st.session_state["bejelentkezve"] = False
        st.rerun()

# --- 4. FŐOLDAL ---
if files:
    df = load_data(files)
    if df is not None:
        lookup = df.groupby('ST_CIKKSZAM')['ST_CIKKNEV'].first().reset_index()
        lookup['Name'] = lookup['ST_CIKKSZAM'] + " - " + lookup['ST_CIKKNEV']
        
        st.title("🥐 Pékség Elemző Dashboard")

        with st.expander("🔍 Szűrők", expanded=True):
            c1, c2 = st.columns(2)
            d_range_a = c1.date_input("A időszak", [df['Datum_Csak'].min(), df['Datum_Csak'].max()])
            d_range_b = c2.date_input("B időszak", [df['Datum_Csak'].min(), df['Datum_Csak'].max()])
            
            st.divider()
            v_prod = st.multiselect("Termékek kiválasztása:", options=lookup['Name'].tolist())
            v_ids = [p.split(" - ")[0] for p in v_prod]

        def get_p(d_range, label):
            if not isinstance(d_range, (list, tuple)) or len(d_range) < 2: return df.head(0)
            mask = (df['Datum_Csak'] >= d_range[0]) & (df['Datum_Csak'] <= d_range[1])
            res = df[mask].copy()
            if v_ids: res = res[res['ST_CIKKSZAM'].isin(v_ids)]
            res['Időszak'] = label
            res['Display'] = res['ST_CIKKSZAM'].map(lookup.set_index('ST_CIKKSZAM')['Name'])
            return res

        df_a = get_p(d_range_a, 'A')
        df_b = get_p(d_range_b, 'B')

        if not df_a.empty:
            st.divider()
            metrika = st.radio("Válassz metrikát:", 
                               ["Érték (Ft)", "Mennyiség (db)", "Súlyozott átlagár (Ft/db)", "Aritmetikai átlagár (Ft/db)"], 
                               horizontal=True)

            def calc_metrics(data):
                if metrika == "Érték (Ft)": return data.groupby('Display')['ST_NEFT'].sum()
                if metrika == "Mennyiség (db)": return data.groupby('Display')['ST_MENNY'].sum()
                if metrika == "Súlyozott átlagár (Ft/db)":
                    g = data.groupby('Display').agg({'ST_NEFT':'sum', 'ST_MENNY':'sum'})
                    return g['ST_NEFT'] / g['ST_MENNY']
                return data.groupby('Display')['Egyseg_Ar'].mean()

            s_a = calc_metrics(df_a).rename('A_Val')
            s_b = calc_metrics(df_b).rename('B_Val')
            comp = pd.concat([s_a, s_b], axis=1).fillna(0)
            
            def get_pct(row):
                if row['B_Val'] == 0: return "Új" if row['A_Val'] > 0 else ""
                v = ((row['A_Val'] - row['B_Val']) / row['B_Val']) * 100
                return f"{'+' if v > 0 else ''}{v:.1f}%"
            comp['Pct'] = comp.apply(get_pct, axis=1)

            plot_df = comp.reset_index().melt(id_vars=['Display', 'Pct'], value_vars=['A_Val', 'B_Val'], var_name='Idő', value_name='Mérték')
            plot_df['Idő'] = plot_df['Idő'].str.replace('_Val', '')
            plot_df['Label'] = plot_df.apply(lambda x: x['Pct'] if x['Idő'] == 'A' else "", axis=1)

            fig = px.bar(plot_df, x='Mérték', y='Display', color='Idő', barmode='group', orientation='h', text='Label',
                         color_discrete_map={'A': '#1f77b4', 'B': '#aec7e8'}, labels={'Mérték': metrika})
            fig.update_traces(textposition='outside')
            st.plotly_chart(fig, use_container_width=True)

            st.subheader("📋 Tranzakciók")
            st.dataframe(pd.concat([df_a, df_b])[['Időszak', 'Datum_Csak', 'SF_UGYFELNEV', 'Display', 'ST_MENNY', 'ST_NEFT', 'Egyseg_Ar']].sort_values('Datum_Csak'), use_container_width=True)
