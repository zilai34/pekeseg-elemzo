import streamlit as st
import pandas as pd
import plotly.express as px
from openai import OpenAI
import datetime

# --- 1. KONFIGURÁCIÓ ÉS TITKOK ---
HIVATALOS_JELSZO = "Velencei670905" 
st.set_page_config(page_title="Pékség Dashboard AI Pro", layout="wide", page_icon="🥐")

openai_api_key = st.secrets.get("OPENAI_API_KEY")

st.markdown("""
    <style>
    @media print {
        .stButton, .stFileUploader, [data-testid="stSidebar"], .stDownloadButton { display: none !important; }
        .main { padding: 0 !important; }
    }
    div[data-testid="metric-container"] {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 10px;
        border: 1px solid #e0e0e0;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. BELÉPÉS ---
if "bejelentkezve" not in st.session_state:
    st.session_state["bejelentkezve"] = False

if not st.session_state["bejelentkezve"]:
    st.title("🔐 Bejelentkezés")
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
    df = df[df['ST_CIKKSZAM'] != '146'] 
    
    df['SF_TELJ'] = pd.to_datetime(df['SF_TELJ'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['SF_TELJ']) 
    
    df['Év'] = df['SF_TELJ'].dt.year
    df['Hónap'] = df['SF_TELJ'].dt.month
    df['Honap_Nev'] = df['SF_TELJ'].dt.strftime('%Y-%m')
    df['Kategória'] = df['ST_CIKKSZAM'].apply(lambda x: "Száraz áru" if x in SZARAZ_LISTA else "Friss áru")
    df['Cikkszam_Nev'] = df['ST_CIKKSZAM'] + " - " + df['ST_CIKKNEV'].astype(str)
    
    return df

# --- 4. OLDALSÁV ---
with st.sidebar:
    st.header("⚙️ Beállítások")
    uploaded_files = st.file_uploader("CSV fájlok feltöltése", type="csv", accept_multiple_files=True)
    
    if openai_api_key:
        st.success("🤖 AI Asszisztens aktív")
    else:
        st.info("ℹ️ AI modul inaktív")

    st.divider()
    if st.button("Kijelentkezés"):
        st.session_state["bejelentkezve"] = False
        st.rerun()

# --- 5. FŐOLDAL ÉS SZŰRŐK ---
if uploaded_files:
    df = load_data(uploaded_files)
    
    if df is not None:
        st.title("📊 Pékség Forgalmi Jelentés")
        
        with st.expander("🔍 Szűrési feltételek", expanded=True):
            c1, c2, c3 = st.columns(3)
            partnerek = ["Összes partner"] + sorted(df['SF_UGYFELNEV'].unique().tolist())
            v_partner = c1.selectbox("Partner választása:", partnerek)
            v_kat = c2.multiselect("Kategória:", ["Friss áru", "Száraz áru"], default=["Friss áru", "Száraz áru"])
            cikkszam_lista = sorted(df['Cikkszam_Nev'].unique().tolist())
            v_cikkszam_nev = c3.multiselect("Cikkszám és név szerinti szűrés:", cikkszam_lista)
            
            min_d = df['SF_TELJ'].min().date()
            max_d = df['SF_TELJ'].max().date()
            date_range = st.date_input("Dátum tartomány:", value=(min_d, max_d), min_value=min_d, max_value=max_d)

        f_df = df.copy()
        if isinstance(date_range, tuple) and len(date_range) == 2:
            f_df = f_df[(f_df['SF_TELJ'].dt.date >= date_range[0]) & (f_df['SF_TELJ'].dt.date <= date_range[1])]
        if v_kat: f_df = f_df[f_df['Kategória'].isin(v_kat)]
        if v_partner != "Összes partner": f_df = f_df[f_df['SF_UGYFELNEV'] == v_partner]
        if v_cikkszam_nev: f_df = f_df[f_df['Cikkszam_Nev'].isin(v_cikkszam_nev)]

        # --- 6. KPI MUTATÓK ---
        if not f_df.empty:
            st.divider()
            m1, m2, m3 = st.columns(3)
            osszes_menny = f_df['ST_MENNY'].sum()
            osszes_netto = f_df['ST_NEFT'].sum()
            napok = f_df['SF_TELJ'].dt.date.nunique()
            
            m1.metric("Szűrt mennyiség", f"{osszes_menny:,.0f}".replace(",", " ") + " db")
            m2.metric("Nettó árbevétel", f"{osszes_netto:,.0f}".replace(",", " ") + " Ft")
            m3.metric("Napi átlag forgalom", f"{(osszes_netto/napok if napok>0 else 0):,.0f}".replace(",", " ") + " Ft")

            # --- 7. ÉV-ÉV ÖSSZEHASONLÍTÁS (%) ---
            st.subheader("📈 Éves összehasonlítás (YoY)")
            y_tengely = st.radio("Mértékegység:", ['ST_NEFT', 'ST_MENNY'], 
                                 format_func=lambda x: "Nettó összeg (Ft)" if x=='ST_NEFT' else "Mennyiség (db)", horizontal=True)

            yoy_df = f_df.groupby(['Év', 'Hónap'])[y_tengely].sum().reset_index()
            pivot_yoy = yoy_df.pivot(index='Hónap', columns='Év', values=y_tengely)
            
            available_years = sorted([c for c in pivot_yoy.columns if isinstance(c, int)])
            
            yoy_summary_for_ai = "" # Ezt adjuk majd át az AI-nak
            
            if len(available_years) >= 2:
                y1, y2 = available_years[-2], available_years[-1]
                pivot_yoy['Eltérés (abs)'] = pivot_yoy[y2] - pivot_yoy[y1]
                pivot_yoy['Eltérés (%)'] = (pivot_yoy[y2] / pivot_yoy[y1] - 1) * 100
                yoy_summary_for_ai = pivot_yoy.to_string() # AI látni fogja a táblázatot
                
                def color_val(val):
                    color = '#1D8348' if val > 0 else '#C0392B'
                    return f'color: {color}; font-weight: bold'

                st.dataframe(
                    pivot_yoy.style.format({
                        y1: "{:,.0f}", y2: "{:,.0f}",
                        'Eltérés (abs)': "{:+,.0f}",
                        'Eltérés (%)': "{:+.1f}%"
                    }).applymap(color_val, subset=['Eltérés (%)']),
                    use_container_width=True
                )
                
                fig_yoy = px.bar(yoy_df, x='Hónap', y=y_tengely, color='Év', barmode='group',
                                 title=f"Havi összevetés ({y1} vs {y2})")
                fig_yoy.update_xaxes(dtick=1)
                st.plotly_chart(fig_yoy, use_container_width=True)
            else:
                st.info("Tölts fel több év adatait az összehasonlításhoz.")

            # --- 8. RÉSZLETEK ÉS AI ---
            tabs = st.tabs(["📋 Adatok", "🤖 AI Üzleti Asszisztens"])
            
            with tabs[0]:
                st.dataframe(f_df[['SF_TELJ', 'SF_UGYFELNEV', 'ST_CIKKNEV', 'ST_MENNY', 'ST_NEFT']].sort_values('SF_TELJ'), use_container_width=True)
            
            with tabs[1]:
                if openai_api_key:
                    st.write("### 💬 Kérdezz bármit az adatokról!")
                    user_q = st.text_input("Pl.: Melyik termék esett vissza legjobban tavalyhoz képest?")
                    
                    if st.button("Elemzés futtatása"):
                        with st.spinner('Az AI elemzi a forgalmat...'):
                            try:
                                client = OpenAI(api_key=openai_api_key)
                                
                                # Kontextus összeállítása: Mi mindenről tudjon az AI?
                                top_products = f_df.groupby(['ST_CIKKNEV'])[y_tengely].sum().sort_values(ascending=False).head(15).to_string()
                                top_customers = f_df.groupby(['SF_UGYFELNEV'])[y_tengely].sum().sort_values(ascending=False).head(10).to_string()
                                
                                prompt_context = f"""
                                Te egy pékség professzionális üzleti elemzője vagy. 
                                Itt vannak a dashboard adatai:
                                
                                1. Éves összehasonlító táblázat (Hónapok szerint):
                                {yoy_summary_for_ai}
                                
                                2. Top 15 termék forgalma:
                                {top_products}
                                
                                3. Top 10 partner:
                                {top_customers}
                                
                                A felhasználó kérdése: {user_q}
                                
                                Kérlek, adj pontos, üzleti szemléletű választ. Ha látsz jelentős visszaesést vagy növekedést, emeld ki!
                                """
                                
                                res = client.chat.completions.create(
                                    model="gpt-4o",
                                    messages=[
                                        {"role": "system", "content": "Üzleti elemző vagy. Válaszolj tömören, lényegre törően."},
                                        {"role": "user", "content": prompt_context}
                                    ]
                                )
                                st.markdown("---")
                                st.markdown(f"**AI válasza:**\n\n{res.choices[0].message.content}")
                            except Exception as e: st.error(f"AI hiba: {e}")
                else: st.info("Az AI-hoz API kulcs szükséges.")
        else: st.warning("Nincs adat a választott szűrőkkel.")
else: st.info("👋 Kezdéshez tölts fel CSV fájlokat!")
