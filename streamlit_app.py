import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import time

# Auto-refresh setiap 10 detik
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = time.time()

REFRESH_INTERVAL = 10
if time.time() - st.session_state.last_refresh > REFRESH_INTERVAL:
    st.cache_data.clear()  # bersihkan cache
    st.session_state.last_refresh = time.time()
    st.rerun()  # rerun setelah cache dibersihkan

# --- Konfigurasi Awal ---
st.set_page_config(page_title="Dashboard Monitoring", layout="wide")

# --- Fungsi Load Data ---
@st.cache_data(ttl=10)
def load_data(url):
    df = pd.read_csv(url)
    df['Date'] = pd.to_datetime(df['Date'], format='%d/%m/%Y %H:%M:%S')
    df['Total Biaya'] = df['Flow Sensor'] * df['Biaya']
    df['Bulan'] = df['Date'].dt.to_period('M').astype(str)
    df['Tanggal'] = df['Date'].dt.date
    return df

# --- Ganti dengan URL CSV dari Google Sheets ---
gsheet_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQde6k9bpztDrdIY93vx12iJqtxs_CRH7tGVXeZ-qcUQogmlYRgSr4vRUxGqMJswjLXzNXsYg9dL9TF/pub?output=csv"
df = load_data(gsheet_url)

# --- Sidebar Navigasi ---
st.sidebar.title("Menu")
menu = st.sidebar.radio("", ["Home", "Monitoring", "About"])

# --- Halaman HOME ---
if menu == "Home":
    col_title, col_update = st.columns([3, 1])
    with col_title:
        st.title("Dashboard")
    with col_update:
        last_update = df['Date'].max().strftime("%d %B %Y %H:%M:%S")
        st.markdown(f"<p style='text-align:right; font-size:16px; margin-top:24px;'>Last Update:<br><b>{last_update}</b></p>", unsafe_allow_html=True)

    now = datetime.now()
    df_bulan_ini = df[(df['Date'].dt.month == now.month) & (df['Date'].dt.year == now.year)]
    pemakaian_bulan_ini = df_bulan_ini['Flow Sensor'].sum()
    biaya_total = (df_bulan_ini['Flow Sensor'] * df_bulan_ini['Biaya']).sum()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Penggunaan", f"{pemakaian_bulan_ini} m³")
    with col2:
        # Tampilkan status valve saja (tanpa kontrol)
        valve_status = "ON" if df_bulan_ini['Valve Status'].iloc[-1] == 1 else "OFF"
        st.text(f"Status Valve: {valve_status}")
    with col3:
        st.metric("Total Tagihan", f"Rp {biaya_total:,.0f}")

    col4, col5 = st.columns(2)
    with col4:
        df['Flow Sensor'] = pd.to_numeric(df['Flow Sensor'], errors='coerce')
        df['Biaya'] = pd.to_numeric(df['Biaya'], errors='coerce')
        df_clean = df.dropna(subset=['Flow Sensor', 'Biaya'])
        
        df_bulanan = df_clean.groupby('Bulan').agg({
            'Flow Sensor': 'sum',
            'Biaya': 'last'
        }).reset_index()
        df_bulanan['Biaya Bulan'] = df_bulanan['Flow Sensor'] * df_bulanan['Biaya']
        
        fig1 = px.bar(df_bulanan, x='Bulan', y='Biaya Bulan', title="Biaya Bulanan (Total)", color_discrete_sequence=["green"])
        st.plotly_chart(fig1, use_container_width=True)

    with col5:
        pemakaian_harian = df.groupby('Tanggal')['Flow Sensor'].sum().reset_index()
        fig2 = px.line(pemakaian_harian, x='Tanggal', y='Flow Sensor', title="Pemakaian Harian")
        st.plotly_chart(fig2, use_container_width=True)

# --- Halaman Monitoring ---
elif menu == "Monitoring":
    st.title("Data Monitoring")
    st.dataframe(df)

# --- Halaman History / About ---
elif menu == "About":
    st.title("Smart Water Meter")
    st.markdown("""
    Air merupakan sumber daya alam yang sangat vital bagi kehidupan manusia...
    [rest of your about text remains unchanged]
    """)
    st.write("Dibuat oleh Arif Rahman - Smart Water Monitoring System")
