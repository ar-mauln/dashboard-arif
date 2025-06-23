import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import time
import numpy as np
import paho.mqtt.publish as mqtt_publish

# Konfigurasi MQTT
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_TOPIC_CONTROL = "smartwater/control"
MQTT_TOPIC_PARAMS = "smartwater/params"

def send_mqtt_command(topic, payload):
    try:
        mqtt_publish.single(
            topic,
            payload=str(payload),
            hostname=MQTT_BROKER,
            port=MQTT_PORT
        )
        return True
    except Exception as e:
        st.error(f"Gagal mengirim MQTT: {e}")
        return False

# Auto-refresh setiap 10 detik
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = time.time()
if 'valve_status' not in st.session_state:
    st.session_state.valve_status = False

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
        # Baca data dengan explicit format
        df = pd.read_csv(url)
        
        # Bersihkan kolom Flow Sensor
        df['Flow Sensor'] = (
            df['Flow Sensor']
            .astype(str)  # Konversi ke string dulu
            .str.replace(',', '.')  # Ganti koma dengan titik untuk desimal
            .str.replace(r'[^\d.]', '', regex=True)  # Hapus karakter non-digit/non-titik
            .replace('', np.nan)  # Kosongkan string jadi NaN
        )
        
        # Konversi ke numeric
        df['Flow Sensor'] = pd.to_numeric(df['Flow Sensor'], errors='coerce')
        
        # Pastikan kolom Biaya juga numeric
        df['Biaya'] = pd.to_numeric(df['Biaya'], errors='coerce')
        
        # Hitung Total Biaya
        df['Total Biaya'] = df['Flow Sensor'] * df['Biaya']
        
        # Konversi tanggal
        df['Date'] = pd.to_datetime(df['Date'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
        df['Bulan'] = df['Date'].dt.to_period('M').astype(str)
        df['Tanggal'] = df['Date'].dt.date
        
        return df.dropna(subset=['Date'])  # Hapus baris dengan tanggal invalid
    
    except Exception as e:
        st.error(f"Error memproses data: {str(e)}")
        return pd.DataFrame()
    
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

# Input Parameter di Sidebar
if menu in ["Home", "Monitoring"]:
    client_id = st.sidebar.text_input(
        "Client ID ESP32",
        value=str(df.iloc[-1, 2]) if len(df) > 0 else "esp32-client-1"
    )
    interval = st.sidebar.number_input(
        "Interval (S)",
        value=int(df.iloc[-1, 3]) if len(df) > 0 else 10000,
        min_value=1
    )
    tarif = st.sidebar.number_input(
        "Tarif per m³ (Rp)",
        value=int(df.iloc[-1, 4]) if len(df) > 0 else 10000,
        min_value=1
    )
    if st.sidebar.button("Kirim Parameter ke ESP32"):
        params = f"{interval},{tarif}"
        if send_mqtt_command(MQTT_TOPIC_PARAMS, params):
            st.sidebar.success("Parameter terkirim!")
        else:
            st.sidebar.error("Gagal mengirim parameter")

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
        # Kontrol Valve dengan session state
        valve_status = st.toggle("Kontrol Valve", value=st.session_state.valve_status)
        if valve_status != st.session_state.valve_status:
            st.session_state.valve_status = valve_status
            if send_mqtt_command(MQTT_TOPIC_CONTROL, "ON" if valve_status else "OFF"):
                st.success("Parameter terkirim!")
            else:
                st.error("Gagal mengirim parameter")
        
        # Tampilkan status aktual dari data
        if not df_bulan_ini.empty and 'Valve Status' in df_bulan_ini.columns:
            valve_display = "ON" if df_bulan_ini['Valve Status'].iloc[-1] == 1 else "OFF"
            st.text(f"Status Aktual: {valve_display}")
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
    Air merupakan sumber daya alam yang sangat vital bagi kehidupan manusia dan berbagai sektor, terutama pertanian dan peternakan yang menyerap lebih dari 70% pemanfaatan air. Di sisi lain, penggunaan air di sektor rumah tangga juga cukup besar, dengan konsumsi harian di kawasan perkotaan Indonesia mencapai 169–247 liter per orang. Tingginya permintaan air ini menimbulkan tantangan tersendiri terhadap ketersediaan air bersih, terutama di wilayah padat penduduk seperti Pulau Jawa yang ketersediaannya bahkan berada di bawah standar WHO. Kota Surabaya, sebagai salah satu contoh, diperkirakan akan membutuhkan lebih dari 625 juta m³ air per tahun pada 2040, seiring dengan pertumbuhan penduduk yang pesat. Tantangan ini diperparah oleh kebocoran infrastruktur, pemborosan, dan rendahnya kesadaran masyarakat dalam menggunakan air secara bijak.

    Permasalahan tersebut mendorong perlunya pengembangan sistem pemantauan konsumsi air yang efisien dan real-time. Sistem ini dirancang agar pengguna dapat memantau penggunaan air secara langsung melalui perangkat digital, serta menerima notifikasi ketika terjadi kebocoran atau penggunaan berlebih. Dengan dukungan komponen seperti solenoid valve yang dapat dikontrol otomatis, sistem ini memungkinkan pengguna untuk segera mengambil tindakan. Selain itu, sistem dibangun dengan mempertimbangkan efisiensi biaya menggunakan perangkat berbiaya rendah dan layanan penyimpanan data gratis, sehingga diharapkan dapat menjadi solusi yang efektif dalam mengurangi pemborosan dan meningkatkan kesadaran masyarakat akan pentingnya pengelolaan air secara bijak.

    Permasalahan tersebut mendorong dirancangnya sebuah sistem monitoring penggunaan air berbasis Internet of Things (IoT) yang mampu memberikan informasi pemakaian air secara real-time serta memungkinkan kontrol otomatis terhadap aliran air. Sistem ini memungkinkan pengguna untuk memantau data melalui dashboard berbasis web yang dapat diakses menggunakan perangkat digital.
    
                
    Spesifikasi:
    - ESP32 DevKit V1
    - Flow Meter YF-S201
    - LCD I2C 16X2
    - Relay 1 Channel 5V
    - Solenoin Valve 12V
    """)
    st.write("Dibuat oleh Arif Rahman - Smart Water Monitoring System")
