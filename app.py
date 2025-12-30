import streamlit as st
import pandas as pd
import plotly.express as px
from openai import OpenAI

# --- KONFIGURÁCIÓ ---
st.set_page_config(page_title="Pékség Forgalmi Elemző", layout="wide")

# Sidebar - Beállítások
st.sidebar.header("Beállítások")
api_key = st.sidebar.text_input("OpenAI API Key", type="password")
client = OpenAI(api_key=api_key) if api_key else None

st.title("📊 Profi Áruforgalmi Dashboard")

# --- SZABÁLYOK ---
SZARAZ_LISTA = ['509496007', '509500001', '509502005', '524145003', '524149001']
GONGYOLEG_CIKKSZAM = '146' # EUR Raklap - Ezt töröljük

# --- ADATFELDOLGOZÁS ---
uploaded_file = st.sidebar.file_uploader("Töltsd fel a CSV fájlt", type="csv")

if uploaded_file:
    # Beolvasás
    df = pd.read_csv(uploaded_file, sep=';', decimal=',', encoding='utf-8')
    
    # 1. SZŰRÉS: Raklap eltávolítása (ne szerepeljen sehol)
    df = df[df['ST_CIKKSZAM'].astype(str).str.strip() != GONGYOLEG_CIKKSZAM]
    
    # 2. Dátumok és Kategóriák
    df['SF_TELJ'] = pd.to_datetime(df['SF_TELJ'])
    df['Honap'] = df['SF_TELJ'].dt.strftime('%Y-%m')
    
    def kategorizal(c):
        return "Száraz áru" if str(c).strip() in SZARAZ_LISTA else "Friss áru"
    
    df['Kategória'] = df['ST_CIKKSZAM'].apply(kategorizal)

    # --- SZŰRŐK ---
    col1, col2, col3 = st.columns(3)
    with col1:
        partner = st.selectbox("Partner:", ["Mindenki"] + sorted(df['SF_UGYFELNEV'].unique().tolist()))
    with col2:
        kat_szuro = st.multiselect("Kategória:", ["Friss áru", "Száraz áru"], default=["Friss áru", "Száraz áru"])
    with col3:
        # Időszak választó (év/hónap alapján)
        időszakok = sorted(df['Honap'].unique().tolist())
        valasztott_ido = st.select_slider("Időszak tartomány:", options=időszakok, value=(időszakok[0], időszakok[-1]))

    # Szűrt adatok létrehozása
    mask = (df['Kategória'].isin(kat_szuro)) & (df['Honap'] >= valasztott_ido[0]) & (df['Honap'] <= valasztott_ido[1])
    if partner != "Mindenki":
        mask &= (df['SF_UGYFELNEV'] == partner)
    
    f_df = df[mask]

    # --- KPI MUTATÓK ---
    m1, m2, m3 = st.columns(3)
    total_db = f_df['ST_MENNY'].sum()
    total_ft = f_df['ST_NEFT'].sum()
    
    m1.metric("Összes mennyiség", f"{total_db:,.0f} db".replace(",", " "))
    m2.metric("Nettó Forgalom", f"{total_ft:,.0f} Ft".replace(",", " "))
    
    # Előző hónap összehasonlítása (Trend)
    monthly = f_df.groupby('Honap')['ST_MENNY'].sum()
    if len(monthly) > 1:
        valtozas = ((monthly.iloc[-1] / monthly.iloc[-2]) - 1) * 100
        m3.metric("Havi trend (utolsó vs előző)", f"{valtozas:+.1f}%")

    # --- VIZUALIZÁCIÓ ---
    st.divider()
    tab1, tab2 = st.tabs(["📊 Grafikonok", "📋 Nyers adatok"])
    
    with tab1:
        # Havi bontású oszlopdiagram
        chart_data = f_df.groupby(['Honap', 'Kategória'])['ST_MENNY'].sum().reset_index()
        fig = px.bar(chart_data, x='Honap', y='ST_MENNY', color='Kategória', barmode='group',
                     title="Forgalom alakulása (db)", template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)
        
        # Termékenkénti toplista
        st.subheader("Top 10 termék (mennyiség szerint)")
        top_products = f_df.groupby('ST_CIKKNEV')['ST_MENNY'].sum().sort_values(ascending=False).head(10).reset_index()
        fig2 = px.bar(top_products, x='ST_MENNY', y='ST_CIKKNEV', orientation='h', color='ST_MENNY')
        st.plotly_chart(fig2, use_container_width=True)

    with tab2:
        st.dataframe(f_df[['SF_TELJ', 'SF_UGYFELNEV', 'ST_CIKKNEV', 'Kategória', 'ST_MENNY', 'ST_NEFT']])

    # --- AI ELEMZÉS ---
    st.divider()
    if st.button("🤖 AI Üzleti jelentés készítése"):
        if client:
            with st.spinner("A GPT-4o elemzi az adatokat..."):
                stats_text = f_df.groupby(['Honap', 'Kategória'])['ST_MENNY'].sum().to_string()
                prompt = f"Elemezd a pékség adatait: {stats_text}. Szempontok: trendek, friss-száraz arány, jövőbeli növekedési javaslat."
                res = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
                st.success(res.choices[0].message.content)
        else:
            st.warning("Adj meg API kulcsot az AI-hoz!")

    # Letöltés
    csv = f_df.to_csv(index=False, sep=';').encode('utf-8')
    st.download_button("Exportálás CSV-be", csv, "pekség_elemzes.csv", "text/csv")

else:
    st.info("Töltsd fel a CSV-t a kezdéshez!")
