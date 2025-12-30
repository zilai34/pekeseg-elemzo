import streamlit as st
import pandas as pd
import plotly.express as px
from openai import OpenAI
import json

# --- 1. ALAPBEÁLLÍTÁSOK ---
HIVATALOS_JELSZO = "Velencei670905"
st.set_page_config(page_title="Pékség AI Pro + Visual Lab", layout="wide", page_icon="📊")

openai_api_key = st.secrets.get("OPENAI_API_KEY")

# Magyar hónapnevek szótára a helyes megjelenítéshez
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
            # Rugalmas beolvasás latin-1 kódolással
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

# --- 4. OLDALSÁV ---
with st.sidebar:
    st.header("📂 Adatforrás")
    uploaded_files = st.file_uploader("CSV fájlok feltöltése", type="csv", accept_multiple_files=True)
    if st.button("Kijelentkezés"):
        st.session_state["bejelentkezve"] = False
        st.rerun()

if uploaded_files:
    df = load_data(uploaded_files)
    if df is not None:
        st.title("🍞 Pékség Adat-Műhely")
        
        # --- 5. KPI SÁV ---
        m1, m2, m3 = st.columns(3)
        m1.metric("Nettó Bevétel", f"{df['ST_NEFT'].sum():,.0f} Ft")
        m2.metric("Eladott Mennyiség", f"{df['ST_MENNY'].sum():,.0f} db")
        m3.metric("Tranzakciók", f"{len(df):,.0f}")

        # --- 6. HAVI ÖSSZEHASONLÍTÓ TÁBLÁZAT (2024 vs 2025) ---
        st.divider()
        st.subheader("📊 Havi összehasonlító kimutatás")
        
        # Létrehozzuk a táblázatot
        pivot_df = df.pivot_table(index=['Hónap_szám', 'Hónap'], columns='Év', values='ST_NEFT', aggfunc='sum').fillna(0)
        
        # Megnézzük, melyik évek vannak meg (pl. 2024 és 2025)
        years = sorted([c for c in pivot_df.columns if isinstance(c, int)])
        
        if len(years) >= 2:
            y1, y2 = years[-2], years[-1] # Az utolsó két év
            
            # Kiszámoljuk az eltérést
            pivot_df['Eltérés (%)'] = ((pivot_df[y2] / pivot_df[y1]) - 1) * 100
            
            # Formázás a megjelenítéshez
            display_df = pivot_df.reset_index(level=0, drop=True)

            def color_diff(val):
                color = 'green' if val > 0 else 'red'
                return f'color: {color}; font-weight: bold'

            # A táblázat megjelenítése formázva
            st.table(display_df.style.format({
                y1: "{:,.0f} Ft",
                y2: "{:,.0f} Ft",
                'Eltérés (%)': "{:+.2f}%"
            }).applymap(color_diff, subset=['Eltérés (%)']))

            # Összesen sor kiszámítása
            sum1 = pivot_df[y1].sum()
            sum2 = pivot_df[y2].sum()
            total_pct = ((sum2 / sum1) - 1) * 100
            
            st.markdown(f"""
                <div style="background-color:#f9f9f9; padding:10px; border-radius:5px; border: 1px solid #ddd;">
                    <b>Összesen {y1}:</b> {sum1:,.0f} Ft | 
                    <b>Összesen {y2}:</b> {sum2:,.0f} Ft | 
                    <b>Teljes Eltérés: <span style="color:{'green' if total_pct > 0 else 'red'}">{total_pct:+.2f}%</span></b>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Az összehasonlításhoz tölts fel 2024 és 2025-ös adatokat is!")

        # --- 7. AI VIZUALIZÁCIÓS LAB (A RÉGI KÓDOD ALAPJÁN) ---
        st.divider()
        st.subheader("🤖 AI Vizualizációs Lab")
        user_q = st.text_area("Milyen elemzést vagy grafikont készítsek?", placeholder="Pl.: Melyik 5 partner hozta a legtöbb bevételt?")

        if st.button("Elemzés és Grafikon készítése") and openai_api_key:
            with st.spinner("Az AI dolgozik..."):
                client = OpenAI(api_key=openai_api_key)
                
                # Kontextus az AI-nak
                top_partners = df.groupby('SF_UGYFELNEV')['ST_NEFT'].sum().sort_values(ascending=False).head(15).to_dict()
                top_products = df.groupby('ST_CIKKNEV')['ST_NEFT'].sum().sort_values(ascending=False).head(15).to_dict()
                
                prompt = f"""
                Pékség üzleti elemzője vagy. Válaszolj magyarul.
                ADATOK:
                Top vevők: {top_partners}
                Top termékek: {top_products}
                KÉRDÉS: {user_q}
                
                SZABÁLY: Ha grafikon kell, adj meg egy 'CHART_DATA' felirat után egy JSON listát: [{"Név": "...", "Érték": 0}]
                """

                res = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
                answer = res.choices[0].message.content
                
                if "CHART_DATA" in answer:
                    text_part = answer.split("CHART_DATA")[0]
                    json_part = answer.split("CHART_DATA")[1].strip()
                    st.markdown(text_part)
                    try:
                        clean_json = json_part.replace("```json", "").replace("```", "").strip()
                        c_df = pd.DataFrame(json.loads(clean_json))
                        fig = px.bar(c_df, x=c_df.columns[0], y=c_df.columns[1], color=c_df.columns[0], title="AI Grafikon")
                        st.plotly_chart(fig, use_container_width=True)
                    except: st.warning("Grafikon hiba.")
                else: st.markdown(answer)

        # --- 8. NYERS ADATOK ---
        with st.expander("📋 Nyers adatok megtekintése"):
            st.dataframe(df, use_container_width=True)
else:
    st.info("👋 Kezdéshez tölts fel CSV fájlokat!")
