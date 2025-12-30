import streamlit as st
import pandas as pd
import plotly.express as px
from openai import OpenAI
import json

# --- 1. ALAPBEÁLLÍTÁSOK ---
# [cite_start]A jelszó és az oldal alapbeállításai a megadott kód alapján [cite: 1]
HIVATALOS_JELSZO = "Velencei670905"
st.set_page_config(page_title="Pékség AI Pro + Visual Lab", layout="wide", page_icon="📊")

openai_api_key = st.secrets.get("OPENAI_API_KEY")

# Hónapnevek magyarosítása a vizualizációhoz
HONAP_NEVEK = {
    1: "Január", 2: "Február", 3: "Március", 4: "Április", 5: "Május", 6: "Június",
    7: "Július", 8: "Augusztus", 9: "Szeptember", 10: "Október", 11: "November", 12: "December"
}

# --- 2. BELÉPÉS ---
# [cite_start]Munkamenet alapú beléptető rendszer [cite: 1, 2]
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
[cite_start]SZARAZ_LISTA = ['509496007', '509500001', '509502005', '524145003', '524149001'] [cite: 2]

@st.cache_data
def load_data(uploaded_files):
    all_dfs = []
    for file in uploaded_files:
        try:
            # [cite_start]CSV fájlok beolvasása a megadott kód szerint [cite: 2, 3]
            temp_df = pd.read_csv(file, sep=';', decimal=',', encoding='latin-1')
            all_dfs.append(temp_df)
        except Exception as e:
            st.error(f"Hiba a(z) {file.name} fájl beolvasásakor: {e}")
    if not all_dfs: return None
    df = pd.concat(all_dfs, ignore_index=True)
    [cite_start]df['ST_CIKKSZAM'] = df['ST_CIKKSZAM'].astype(str).str.strip() [cite: 3]
    [cite_start]df['SF_TELJ'] = pd.to_datetime(df['SF_TELJ'], dayfirst=True, errors='coerce') [cite: 3]
    [cite_start]df = df.dropna(subset=['SF_TELJ']) [cite: 3]
    [cite_start]df['Év'] = df['SF_TELJ'].dt.year [cite: 3]
    df['Hónap_szám'] = df['SF_TELJ'].dt.month
    df['Hónap'] = df['Hónap_szám'].map(HONAP_NEVEK)
    [cite_start]df['Kategória'] = df['ST_CIKKSZAM'].apply(lambda x: "Száraz áru" if x in SZARAZ_LISTA else "Friss áru") [cite: 3]
    return df

# --- 4. OLDALSÁV ÉS ADATBETÖLTÉS ---
with st.sidebar:
    st.header("📂 Adatforrás")
    [cite_start]uploaded_files = st.file_uploader("CSV fájlok feltöltése", type="csv", accept_multiple_files=True) [cite: 4]
    if st.button("Kijelentkezés"):
        st.session_state["bejelentkezve"] = False
        st.rerun()

if uploaded_files:
    df = load_data(uploaded_files)
    if df is not None:
        # --- 5. DASHBOARD FELSŐ RÉSZ (KPI) ---
        st.title("🍞 Pékség Adat-Műhely")
        
        [cite_start]m1, m2, m3 = st.columns(3) [cite: 5]
        [cite_start]m1.metric("Nettó Bevétel", f"{df['ST_NEFT'].sum():,.0f} Ft") [cite: 5]
        [cite_start]m2.metric("Eladott Mennyiség", f"{df['ST_MENNY'].sum():,.0f} db") [cite: 5]
        [cite_start]m3.metric("Tranzakciók", f"{len(df):,.0f}") [cite: 5]

        # --- 6. ÚJ: HAVI ÖSSZEHASONLÍTÓ TÁBLÁZAT ---
        st.divider()
        st.subheader("📊 Havi összehasonlítás és százalékos eltérés")
        
        pivot_df = df.pivot_table(index=['Hónap_szám', 'Hónap'], columns='Év', values='ST_NEFT', aggfunc='sum').fillna(0)
        years = sorted([c for c in pivot_df.columns if isinstance(c, int)])
        
        if len(years) >= 2:
            y1, y2 = years[-2], years[-1]
            pivot_df['Eltérés (%)'] = ((pivot_df[y2] / pivot_df[y1]) - 1) * 100
            display_df = pivot_df.reset_index(level=0, drop=True)

            def color_diff(val):
                return f'color: {"green" if val > 0 else "red"}; font-weight: bold'

            st.table(display_df.style.format({
                y1: "{:,.0f} Ft", y2: "{:,.0f} Ft", 'Eltérés (%)': "{:+.2f}%"
            }).applymap(color_diff, subset=['Eltérés (%)']))

            # Végösszegek megjelenítése
            sum1, sum2 = pivot_df[y1].sum(), pivot_df[y2].sum()
            total_diff = ((sum2 / sum1) - 1) * 100
            st.markdown(f"**Összesen {y1}:** {sum1:,.0f} Ft | **Összesen {y2}:** {sum2:,.0f} Ft | **Eltérés:** {total_diff:+.2f}%")
        else:
            st.info("Több év adatai szükségesek az összehasonlításhoz.")

        # --- 7. AI STRATÉGA ÉS GRAFIKON GENERÁTOR ---
        # [cite_start]A megadott AI logika integrálása [cite: 6, 7]
        st.divider()
        st.subheader("🤖 AI Vizualizációs Lab")
        user_q = st.text_area("Milyen elemzést készítsek?", placeholder="Pl.: Hasonlítsd össze a top 5 partner bevételét...")

        if st.button("Elemzés és Grafikon készítése") and openai_api_key:
            with st.spinner("AI dolgozik az adatokon..."):
                client = OpenAI(api_key=openai_api_key)
                [cite_start]top_partners = df.groupby('SF_UGYFELNEV')['ST_NEFT'].sum().sort_values(ascending=False).head(20).to_dict() [cite: 7]
                [cite_start]top_products = df.groupby('ST_CIKKNEV')['ST_NEFT'].sum().sort_values(ascending=False).head(20).to_dict() [cite: 7]
                monthly_yoy = df.groupby(['Év', 'Hónap_szám'])['ST_NEFT'].sum().unstack(level=0).to_dict()

                [cite_start]prompt = f"Üzleti elemző vagy. Adatok: Partnerek: {top_partners}, Termékek: {top_products}, Trendek: {monthly_yoy}. Kérdés: {user_q}. Válaszolj szöveggel és ha kell grafikont, adj CHART_DATA JSON-t." [cite: 8, 9, 10, 11]

                [cite_start]res = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": "Üzleti elemző vagy."}, {"role": "user", "content": prompt}]) [cite: 12]
                [cite_start]answer = res.choices[0].message.content [cite: 13]
                
                if "CHART_DATA" in answer:
                    [cite_start]text_part = answer.split("CHART_DATA")[0] [cite: 13]
                    [cite_start]json_part = answer.split("CHART_DATA")[1].strip() [cite: 14]
                    st.markdown(text_part)
                    try:
                        [cite_start]clean_json = json_part.replace("```json", "").replace("```", "").strip() [cite: 15]
                        [cite_start]chart_df = pd.DataFrame(json.loads(clean_json)) [cite: 15, 16]
                        [cite_start]fig = px.bar(chart_df, x=chart_df.columns[0], y=chart_df.columns[1], title="AI Elemzés") [cite: 17]
                        st.plotly_chart(fig, use_container_width=True)
                    [cite_start]except: st.warning("Grafikon hiba.") [cite: 18]
                [cite_start]else: st.markdown(answer) [cite: 18]

        with st.expander("📋 Nyers adatok megtekintése"):
            [cite_start]st.dataframe(df, use_container_width=True) [cite: 19]
else:
    st.info("👋 Kezdéshez tölts fel CSV fájlokat a bal oldalon!")
