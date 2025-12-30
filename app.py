import streamlit as st
import pandas as pd
import plotly.express as px

# --- 1. KONFIGURÁCIÓ ---
HIVATALOS_JELSZO = "Velencei670905" 
st.set_page_config(page_title="Pékség Számla Dashboard", layout="wide", page_icon="🧾")

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
            # Próbáljuk meg kitalálni a szeparátort (pontosvessző az SQL exportnál)
            temp_df = pd.read_csv(file, sep=';', decimal=',', encoding='latin-1')
            all_dfs.append(temp_df)
        except Exception as e:
            st.error(f"Hiba a(z) {file.name} fájlban: {e}")
    
    if not all_dfs: return None
    df = pd.concat(all_dfs, ignore_index=True)
    
    # Alapvető tisztítás
    for col in ['ST_CIKKSZAM', 'ST_CIKKNEV', 'SF_UGYFELNEV', 'SF_TIP']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    
    # Dátumkezelés
    df['SF_TELJ'] = pd.to_datetime(df['SF_TELJ'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['SF_TELJ'])
    df['Datum_Csak'] = df['SF_TELJ'].dt.date
    
    # Értékek tisztítása (ST_NE = Nettó Érték a számlán)
    df['ST_NEFT'] = pd.to_numeric(df['ST_NE'], errors='coerce').fillna(0)
    df['ST_MENNY'] = pd.to_numeric(df['ST_MENNY'], errors='coerce').fillna(0)
    
    df['Kategória'] = df['ST_CIKKSZAM'].apply(lambda x: "Száraz áru" if x in SZARAZ_LISTA else "Friss áru")
    return df

# --- 4. OLDALSÁV ---
with st.sidebar:
    st.header("📂 Adatok")
    uploaded_files = st.file_uploader("Számla export (CSV)", type="csv", accept_multiple_files=True)
    st.divider()
    clean_anomalies = st.checkbox("Anomáliák kiszűrése (0 Ft-os tételek törlése)", value=True)
    only_invoices = st.checkbox("Csak SZÁMLA típusú tételek", value=False)

# --- 5. FŐOLDAL ---
if uploaded_files:
    df = load_data(uploaded_files)
    if df is not None:
        # SZŰRÉSEK AZ ANOMÁLIÁKRA
        if clean_anomalies:
            df = df[df['ST_NEFT'] > 0]
        if only_invoices and 'SF_TIP' in df.columns:
            df = df[df['SF_TIP'] == 'SZLA']

        st.title("🧾 Pékség Számla-alapú Elemzés")

        # Cikkszám lookup
        product_lookup = df.groupby('ST_CIKKSZAM')['ST_CIKKNEV'].first().reset_index()
        product_lookup['Display_Name'] = product_lookup['ST_CIKKSZAM'] + " - " + product_lookup['ST_CIKKNEV']
        product_options = sorted(product_lookup['Display_Name'].tolist())

        with st.expander("🔍 Szűrők", expanded=True):
            c1, c2 = st.columns(2)
            min_d, max_d = df['Datum_Csak'].min(), df['Datum_Csak'].max()
            range_a = c1.date_input("'A' időszak", [min_d, max_d])
            range_b = c2.date_input("'B' időszak", [min_d, max_d])
            
            st.divider()
            v_termek_nevek = st.multiselect("Termékek:", options=product_options)
            v_cikkszamok = [name.split(" - ")[0] for name in v_termek_nevek]

        # Szűrési logika
        def filter_p(d_range, label):
            mask = (df['Datum_Csak'] >= d_range[0]) & (df['Datum_Csak'] <= d_range[1])
            res = df[mask].copy()
            if v_cikkszamok: res = res[res['ST_CIKKSZAM'].isin(v_cikkszamok)]
            res['Időszak'] = label
            res['Cikkszam_Nev'] = res['ST_CIKKSZAM'].map(product_lookup.set_index('ST_CIKKSZAM')['Display_Name'])
            return res

        df_a = filter_p(range_a, 'A')
        df_b = filter_p(range_b, 'B')

        if not df_a.empty:
            # KPI-K
            m1, m2, m3 = st.columns(3)
            bev_a, bev_b = df_a['ST_NEFT'].sum(), df_b['ST_NEFT'].sum()
            m1.metric("Bevétel 'A'", f"{bev_a:,.0f} Ft", delta=f"{((bev_a-bev_b)/bev_b*100):.1f}%" if bev_b else None)
            m2.metric("Bevétel 'B'", f"{bev_b:,.0f} Ft")
            m3.metric("Különbség", f"{(bev_a-bev_b):,.0f} Ft")

            # GRAFIKON
            st.subheader("📊 Termék összehasonlítás")
            metrika = st.radio("Válassz:", ["Érték (Ft)", "Mennyiség (db)", "Átlagár (Ft/db)"], horizontal=True)
            
            # Dinamikus grafikon számítás (hasonló az előzőhöz)
            # ... [Grafikon kódja a választott metrikával] ...
            # (A korábbi verzió grafikon logikája ide kerül, de már a tisztított számla adatokkal)

            st.plotly_chart(px.bar(pd.concat([df_a, df_b]).groupby(['Cikkszam_Nev', 'Időszak'])['ST_NEFT'].sum().reset_index(), 
                                   x='ST_NEFT', y='Cikkszam_Nev', color='Időszak', barmode='group', orientation='h'))

            st.subheader("📋 Számla részletek")
            st.dataframe(pd.concat([df_a, df_b])[['SF_SZLASZAM', 'SF_TIP', 'Datum_Csak', 'SF_UGYFELNEV', 'ST_CIKKNEV', 'ST_MENNY', 'ST_NEFT']], use_container_width=True)
        else:
            st.warning("Válassz ki adatokat!")

else:
    st.info("Kérlek, töltsd fel a számla adatokat tartalmazó CSV fájlt!")
