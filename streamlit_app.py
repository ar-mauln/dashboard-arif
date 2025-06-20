import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import time

import requests  # Tambahkan kalau belum ada

# Fungsi untuk mengirim perintah ON/OFF ke ESP32 via HTTP
def kontrol_valve(status, ip):
    try:
        url = f"http://{ip}/on" if status else f"http://{ip}/off"
        response = requests.get(url, timeout=3)
        return response.status_code
    except Exception as e:
        pass



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
    df['Date'] = pd.to_datetime(df['Date'], format='%d/%m/%Y %H:%M:%S')  # GANTI DI SINI
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

# Ambil interval terakhir dari kolom ke-3
ip_terakhir = df.iloc[-1, 2]  # index kolom ke-3 (mulai dari 0)

# Pastikan interval_terakhir angka (jaga-jaga kalau kosong)
try:
    ip_terakhir = str(ip_terakhir)
except:
    ip_terakhir = "192.168.1.100"  # default

ip_address = st.sidebar.text_input("IP Address ESP32", value=ip_terakhir)

#Setting Interval
interval_terakhir = df.iloc[-1, 3]

try:
    interval_terakhir = int(interval_terakhir)
except:
    interval_terakhir = 10000  # default

interval = st.sidebar.number_input("Interval (S)", value=interval_terakhir)

#Setting Tarif
tarif_terakhir = df.iloc[-1, 4]

try:
    tarif_terakhir = int(tarif_terakhir)
except:
    tarif_terakhir = 10000  # default

tarif = st.sidebar.number_input("Tarif per m³ (Rp)", value=tarif_terakhir)

#Tombol Update ke ESP
if st.sidebar.button("Kirim ke ESP32"):
    try:
        url = f"http://{ip_address}/set-parameter"
        payload = {
            "interval": interval,
            "tarif": tarif
        }
        response = requests.get(url, params=payload, timeout=3)
    except Exception as e:
        pass



# --- Halaman HOME ---
if menu == "Home":
    col_title, col_update = st.columns([3, 1])  # Kolom 3:1 rasio
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
        status_valve = st.toggle("Kontrol Valve")
        st.text(f"Status: {'ON' if status_valve else 'OFF'}")

        # Kirim HTTP ke ESP32 saat toggle berubah
        kontrol_valve(status_valve, ip_address)
    with col3:
        st.metric("Total Tagihan", f"Rp {biaya_total:,.0f}")

    col4, col5 = st.columns(2)
    with col4:
        # Pastikan kolom numerik tidak berisi string
        df['Flow Sensor'] = pd.to_numeric(df['Flow Sensor'], errors='coerce')
        df['Biaya'] = pd.to_numeric(df['Biaya'], errors='coerce')

        # Drop NaN hasil konversi
        df_clean = df.dropna(subset=['Flow Sensor', 'Biaya'])

        # Hitung total flow dan biaya per bulan
        df_bulanan = df_clean.groupby('Bulan').agg({
                'Flow Sensor': 'sum',
                'Biaya': 'last'
            }).reset_index()

        df_bulanan['Biaya Bulan'] = df_bulanan['Flow Sensor'] * df_bulanan['Biaya']

        # Plot grafik
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