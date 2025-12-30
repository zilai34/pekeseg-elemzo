import streamlit as st
import pandas as pd
import plotly.express as px
from openai import OpenAI
import json

# --- 1. ALAPBEÁLLÍTÁSOK ---
HIVATALOS_JELSZO = "Velencei670905"
st.set_page_config(page_title="Pékség AI Pro + Visual Lab", layout="wide", page_icon="📊")

openai_api_key = st.secrets.get("OPENAI_API_KEY")

# Hónapnevek magyarosítása a vizualizációhoz
HONAP_NEVEK = {
    1: "Január", 2: "Február", 3: "Március", 4: "Április", 5: "Május", 6: "Június",
    7: "Július", 8: "Augusztus", 9: "Szeptember", 10: "Október", 11: "November", 12: "December"
}

# --- 2. BELÉPÉS ---
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
            st.error(f"Hiba a(z) {file.name} fájl beolvasásakor: {e}")
    if not all_dfs: return None
    df = pd.concat(all_dfs, ignore_index=True)
    df['ST_CIKKSZAM'] = df['ST_CIKKSZAM'].astype(str).str.strip()
    df['SF_TELJ'] = pd.to_datetime(df['SF_TELJ'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['SF_TELJ'])
    df['Év'] = df['SF_TELJ'].dt.year
    df['Hónap_szám'] = df['SF_TELJ'].dt.month
    df['Hónap'] = df['Hónap_szám'].map(HONAP_NEVEK)
    df['Kategória'] = df['ST_CIKKSZAM'].apply(lambda x: "Száraz áru" if x in SZARAZ_LISTA else "Friss áru")
    return df

# --- 4. OLDALSÁV ÉS ADATBETÖLTÉS ---
with st.sidebar:
    st.header("📂 Adatforrás")
    uploaded_files = st.file_uploader("CSV fájlok feltöltése", type="csv", accept_multiple_files=True)
    if st.button("Kijelentkezés"):
        st.session_state["bejelentkezve"] = False
        st.rerun()

if uploaded_files:
    df = load_data(uploaded_files)
    if df is not None:
        # --- 5. DASHBOARD FELSŐ RÉSZ (KPI) ---
        st.title("🍞 Pékség Adat-Műhely")
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Nettó Bevétel", f"{df['ST_NEFT'].sum():,.0f} Ft")
        m2.metric("Eladott Mennyiség", f"{df['ST_MENNY'].sum():,.0f} db")
        m3.metric("Tranzakciók", f"{len(df):,.0f}")

        # --- ÚJ: 6. HAVI ÖSSZEHASONLÍTÓ TÁBLÁZAT ---
        st.divider()
        st.subheader("📊 Havi összehasonlító kimutatás és eltérések")
        
        pivot_df = df.pivot_table(index=['Hónap_szám', 'Hónap'], columns='Év', values='ST_NEFT', aggfunc='sum').fillna(0)
        years = sorted([c for c in pivot_df.columns if isinstance(c, int)])
        
        if len(years) >= 2:
            y1, y2 = years[-2], years[-1]
            pivot_df['Eltérés (%)'] = ((pivot_df[y2] / pivot_df[y1]) - 1) * 100
            display_df = pivot_df.reset_index(level=0, drop=True)

            def color_diff(val):
                color = 'green' if val > 0 else 'red'
                return f'color: {color}; font-weight: bold'

            st.table(display_df.style.format({
                y1: "{:,.0f} Ft", y2: "{:,.0f} Ft", 'Eltérés (%)': "{:+.2f}%"
            }).applymap(color_diff, subset=['Eltérés (%)']))

            # Összesítő blokk
            sum1, sum2 = pivot_df[y1].sum(), pivot_df[y2].sum()
            total_diff = ((sum2 / sum1) - 1) * 100
            st.markdown(f"""
                <div style="background-color:#f0f2f6; padding:20px; border-radius:10px; text-align:center; border: 1px solid #d1d5db;">
                    <span style="font-size:18px;"><b>{y1} Összesen:</b> {sum1:,.0f} Ft  |  <b>{y2} Összesen:</b> {sum2:,.0f} Ft</span><br>
                    <span style="font-size:22px;"><b>Teljes éves eltérés: <span style="color:{'green' if total_diff > 0 else 'red'}">{total_diff:+.2f}%</span></b></span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Tölts fel több év adatait az összehasonlításhoz!")

        # --- 7. AI STRATÉGA ÉS GRAFIKON GENERÁTOR (RÉGI KÓDOD ALAPJÁN) ---
        st.divider()
        st.subheader("🤖 AI Vizualizációs Lab")
        st.info("Kérj egyedi elemzést vagy grafikont! (Pl.: 'Csinálj egy grafikont a top 5 partnerem bevételéről')")

        user_q = st.text_area("Milyen elemzést készítsek?", placeholder="Pl.: Elemezd a 2024 és 2025 február közötti különbséget termékenként...")

        if st.button("Elemzés és Grafikon készítése") and openai_api_key:
            with st.spinner("AI dolgozik az adatokon..."):
                client = OpenAI(api_key=openai_api_key)
                
                top_partners = df.groupby('SF_UGYFELNEV')['ST_NEFT'].sum().sort_values(ascending=False).head(20).to_dict()
                top_products = df.groupby('ST_CIKKNEV')['ST_NEFT'].sum().sort_values(ascending=False).head(20).to_dict()
                monthly_yoy = df.groupby(['Év', 'Hónap_szám'])['ST_NEFT'].sum().unstack(level=0).to_dict()

                prompt = f"""
                Te egy pékség üzleti elemzője vagy. Válaszolj a kérdésre az adatok alapján magyarul.
                
                ADATOK:
                - Top partnerek: {top_partners}
                - Top termékek: {top_products}
                - Havi trendek: {monthly_yoy}
                
                KÉRDÉS: {user_q}
                
                KÖVETELMÉNY:
                1. Adj egy szöveges elemzést.
                2. Ha a kérdés vizualizációra irányul, a válasz végén adj meg egy JSON blokkot 'CHART_DATA' címkével, ami egy listát tartalmaz szótárakkal (pl. [{{"Név": "Kifli", "Érték": 100}}]).
                """

                res = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "system", "content": "Üzleti elemző vagy."}, {"role": "user", "content": prompt}]
                )
                
                answer = res.choices[0].message.content
                
                if "CHART_DATA" in answer:
                    text_part = answer.split("CHART_DATA")[0]
                    json_part = answer.split("CHART_DATA")[1].strip()
                    st.markdown(text_part)
                    try:
                        clean_json = json_part.replace("```json", "").replace("```", "").strip()
                        chart_data = json.loads(clean_json)
                        chart_df = pd.DataFrame(chart_data)
                        
                        st.write("### 📈 AI által generált grafikon")
                        cols = chart_df.columns
                        fig = px.bar(chart_df, x=cols[0], y=cols[1], color=cols[0], title="AI Elemzés Eredménye")
                        st.plotly_chart(fig, use_container_width=True)
                    except:
                        st.warning("A grafikont nem sikerült kirajzolni, de az elemzés elkészült.")
                else:
                    st.markdown(answer)

        # --- 8. HAGYOMÁNYOS TÁBLÁZATOK ---
        with st.expander("📋 Nyers adatok megtekintése"):
            st.dataframe(df, use_container_width=True)

else:
    st.info("👋 Kezdéshez tölts fel CSV fájlokat a bal oldalon!")
