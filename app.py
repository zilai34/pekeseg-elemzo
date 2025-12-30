import streamlit as st
import pandas as pd
import plotly.express as px
from openai import OpenAI
import json

# --- 1. ALAPBEÁLLÍTÁSOK ---
HIVATALOS_JELSZO = "Velencei670905"
st.set_page_config(page_title="Pékség AI Pro + Visual Lab", layout="wide", page_icon="📊")

openai_api_key = st.secrets.get("OPENAI_API_KEY")

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

# --- 3. ADATKEZELÉS ÉS HÓNAP NEVEK ---
HONAP_NEVEK = {
    1: "Január", 2: "Február", 3: "Március", 4: "Április", 5: "Május", 6: "Június",
    7: "Július", 8: "Augusztus", 9: "Szeptember", 10: "Október", 11: "November", 12: "December"
}

@st.cache_data
def load_data(uploaded_files):
    all_dfs = []
    for file in uploaded_files:
        try:
            # Rugalmas beolvasás latin-1 kódolással a magyar ékezetekhez
            temp_df = pd.read_csv(file, sep=';', decimal=',', encoding='latin-1')
            all_dfs.append(temp_df)
        except Exception as e:
            st.error(f"Hiba a(z) {file.name} fájl beolvasásakor: {e}")
    
    if not all_dfs: return None
    df = pd.concat(all_dfs, ignore_index=True)
    
    # Időpontok konvertálása és kiegészítő oszlopok
    df['SF_TELJ'] = pd.to_datetime(df['SF_TELJ'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['SF_TELJ'])
    df['Év'] = df['SF_TELJ'].dt.year
    df['Hónap_szám'] = df['SF_TELJ'].dt.month
    df['Hónap'] = df['Hónap_szám'].map(HONAP_NEVEK)
    
    return df

# --- 4. OLDALSÁV ---
with st.sidebar:
    st.header("📂 Adatforrás")
    uploaded_files = st.file_uploader("CSV fájlok feltöltése", type="csv", accept_multiple_files=True)
    if st.button("Kijelentkezés"):
        st.session_state["bejelentkezve"] = False
        st.rerun()

# --- 5. DASHBOARD MEGJELENÍTÉS ---
if uploaded_files:
    df = load_data(uploaded_files)
    if df is not None:
        st.title("🍞 Pékség Adat-Műhely")
        
        # --- 6. HAVI ÖSSZEHASONLÍTÓ TÁBLÁZAT ---
        st.subheader("📊 Havi összehasonlítás és százalékos eltérés")
        
        # Pivot tábla: Hónapok a sorokban, Évek az oszlopokban
        pivot_df = df.pivot_table(index=['Hónap_szám', 'Hónap'], columns='Év', values='ST_NEFT', aggfunc='sum').fillna(0)
        
        years = sorted(pivot_df.columns)
        if len(years) >= 2:
            y1, y2 = years[-2], years[-1] # Az utolsó két év összehasonlítása
            
            # Százalékos eltérés számítása
            pivot_df['Eltérés (%)'] = ((pivot_df[y2] / pivot_df[y1]) - 1) * 100
            
            # Csak a hónap neve maradjon az indexben a megjelenítéshez
            display_df = pivot_df.reset_index(level=0, drop=True)

            # Formázó függvény a színes százalékokhoz
            def color_diff_style(val):
                color = 'green' if val > 0 else 'red'
                return f'color: {color}; font-weight: bold'

            # Táblázat kirajzolása
            st.table(
                display_df.style.format({
                    y1: "{:,.0f} Ft",
                    y2: "{:,.0f} Ft",
                    'Eltérés (%)': "{:+.2f}%"
                }).applymap(color_diff_style, subset=['Eltérés (%)'])
            )

            # --- ÖSSZESEN BLOKK ---
            sum_y1 = pivot_df[y1].sum()
            sum_y2 = pivot_df[y2].sum()
            total_diff = ((sum_y2 / sum_y1) - 1) * 100
            color_total = "green" if total_diff > 0 else "red"

            st.markdown(f"""
                <div style="background-color:#f8f9fb; padding:25px; border-radius:15px; border: 1px solid #e6e9ef; text-align: center;">
                    <h2 style="margin-top:0; color:#31333f;">Összesített Eredmény</h2>
                    <p style="font-size:24px; margin:0;">
                        <b>{y1}:</b> {sum_y1:,.0f} Ft &nbsp;&nbsp; | &nbsp;&nbsp;
                        <b>{y2}:</b> {sum_y2:,.0f} Ft &nbsp;&nbsp; | &nbsp;&nbsp;
                        <b>Eltérés: <span style="color:{color_total};">{total_diff:+.2f}%</span></b>
                    </p>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.warning("Legalább két különböző év (pl. 2024 és 2025) adatai szükségesek az összehasonlításhoz!")

        # --- 7. AI VIZUALIZÁCIÓS LAB ---
        st.divider()
        st.subheader("🤖 AI Vizualizációs Lab")
        user_q = st.text_area("Milyen elemzést készítsek még?", placeholder="Pl. Melyik termék emelkedett a legjobban?")

        if st.button("AI Elemzés indítása") and openai_api_key:
            with st.spinner("Az AI elemzi az adatokat..."):
                client = OpenAI(api_key=openai_api_key)
                
                # Adatok tömörítése az AI-nak
                top_products = df.groupby('ST_CIKKNEV')['ST_NEFT'].sum().sort_values(ascending=False).head(10).to_dict()
                
                prompt = f"""
                Pékség elemző vagy. Válaszolj magyarul.
                ADATOK:
                Havi statisztika: {pivot_df.to_dict()}
                Top 10 termék: {top_products}
                KÉRDÉS: {user_q}
                FORMÁTUM: Szöveges elemzés, majd ha grafikon kell: CHART_DATA [{"Cimke": "...", "Ertek": 0}]
                """
                
                res = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}]
                )
                
                answer = res.choices[0].message.content
                if "CHART_DATA" in answer:
                    parts = answer.split("CHART_DATA")
                    st.markdown(parts[0])
                    try:
                        c_data = json.loads(parts[1].strip().replace("'", '"'))
                        fig = px.bar(pd.DataFrame(c_data), x='Cimke', y='Ertek', title="AI Grafikon")
                        st.plotly_chart(fig)
                    except: st.warning("Grafikon hiba.")
                else: st.markdown(answer)

else:
    st.info("👋 Kezdéshez tölts fel CSV fájlokat a bal oldali menüben!")
