import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import time
import numpy as np

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

# --- Fungsi Load Data dengan Error Handling ---
@st.cache_data(ttl=10)
def load_data(url):
    try:
        df = pd.read_csv(url)
        df['Date'] = pd.to_datetime(df['Date'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
        
        # Convert numeric columns safely
        df['Flow Sensor'] = pd.to_numeric(df['Flow Sensor'], errors='coerce')
        df['Biaya'] = pd.to_numeric(df['Biaya'], errors='coerce')
        
        # Calculate Total Biaya only for valid rows
        valid_rows = df['Flow Sensor'].notna() & df['Biaya'].notna()
        df['Total Biaya'] = np.where(valid_rows, df['Flow Sensor'] * df['Biaya'], np.nan)
        
        df['Bulan'] = df['Date'].dt.to_period('M').astype(str)
        df['Tanggal'] = df['Date'].dt.date
        
        return df
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return pd.DataFrame()  # Return empty dataframe on error

# --- Ganti dengan URL CSV dari Google Sheets ---
gsheet_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQde6k9bpztDrdIY93vx12iJqtxs_CRH7tGVXeZ-qcUQogmlYRgSr4vRUxGqMJswjLXzNXsYg9dL9TF/pub?output=csv"
df = load_data(gsheet_url)

# Handle empty dataframe case
if df.empty:
    st.error("Data tidak dapat dimuat. Silakan cek koneksi atau format data.")
    st.stop()

# --- Sidebar Navigasi ---
st.sidebar.title("Menu")
menu = st.sidebar.radio("", ["Home", "Monitoring", "About"])

# --- Halaman HOME ---
if menu == "Home":
    col_title, col_update = st.columns([3, 1])
    with col_title:
        st.title("Dashboard")
    with col_update:
        last_update = df['Date'].max().strftime("%d %B %Y %H:%M:%S") if not df['Date'].isnull().all() else "N/A"
        st.markdown(f"<p style='text-align:right; font-size:16px; margin-top:24px;'>Last Update:<br><b>{last_update}</b></p>", unsafe_allow_html=True)

    now = datetime.now()
    df_bulan_ini = df[(df['Date'].dt.month == now.month) & (df['Date'].dt.year == now.year)]
    
    # Safe calculations with NaN handling
    pemakaian_bulan_ini = df_bulan_ini['Flow Sensor'].sum(skipna=True) or 0
    biaya_total = df_bulan_ini['Total Biaya'].sum(skipna=True) or 0

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Penggunaan", f"{pemakaian_bulan_ini:.2f} m³")
    with col2:
        # Tampilkan status valve dengan error handling
        if not df_bulan_ini.empty and 'Valve Status' in df_bulan_ini.columns:
            valve_status = "ON" if df_bulan_ini['Valve Status'].iloc[-1] == 1 else "OFF"
            st.text(f"Status Valve: {valve_status}")
        else:
            st.text("Status Valve: Data tidak tersedia")
    with col3:
        st.metric("Total Tagihan", f"Rp {biaya_total:,.0f}")

    col4, col5 = st.columns(2)
    with col4:
        # Filter out NaN values
        df_clean = df.dropna(subset=['Flow Sensor', 'Biaya', 'Bulan'])
        
        if not df_clean.empty:
            df_bulanan = df_clean.groupby('Bulan').agg({
                'Flow Sensor': 'sum',
                'Biaya': 'last'
            }).reset_index()
            df_bulanan['Biaya Bulan'] = df_bulanan['Flow Sensor'] * df_bulanan['Biaya']
            
            fig1 = px.bar(df_bulanan, x='Bulan', y='Biaya Bulan', title="Biaya Bulanan (Total)", color_discrete_sequence=["green"])
            st.plotly_chart(fig1, use_container_width=True)
        else:
            st.warning("Tidak ada data yang valid untuk ditampilkan")

    with col5:
        if not df.empty:
            pemakaian_harian = df.groupby('Tanggal')['Flow Sensor'].sum().reset_index()
            fig2 = px.line(pemakaian_harian, x='Tanggal', y='Flow Sensor', title="Pemakaian Harian")
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.warning("Tidak ada data yang valid untuk ditampilkan")

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
