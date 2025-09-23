# app.py
import streamlit as st
import requests
import pandas as pd
import threading
import uvicorn
from fastapi import FastAPI, Query
from pymongo import MongoClient
from datetime import datetime
from giaidoanbo import classify_cow, stage_map, get_age_days

# ================== CONFIG ==================
MONGO_CONNECTIONS = {
    "Server Test": "mongodb://root:tgx2025@103.48.84.200:27017/",
    "Server Dev": "mongodb://admin:tgx2025@103.48.84.199:27017/?authSource=admin",
}

DB_NAME = "QuanLyTrangTraiDb"

TRAI_COLLECTIONS = {
    "Trại IA PUCH": "BoNhapTrai",
    "Trại EA H'LEO": "BoNhapTrai_1",
    "Trại AD1": "BoNhapTrai_2",
    "Trại ERC": "BoNhapTrai_3",
    "Trại BSA": "BoNhapTrai_4",
}

# ========== FASTAPI APP ==========
api_app = FastAPI(title="🐄 API Phân loại giai đoạn bò")

# Cache Mongo client connections
mongo_clients = {}

def get_collection(server_name: str, collection_name: str):
    if server_name not in mongo_clients:
        conn_str = MONGO_CONNECTIONS[server_name]
        mongo_clients[server_name] = MongoClient(conn_str, serverSelectionTimeoutMS=10000)
    client = mongo_clients[server_name]
    return client[DB_NAME][collection_name]

@api_app.get("/giaidoanbo")
def giaidoanbo(
    server: str = Query(..., description="Tên server Mongo"),
    trai: str = Query(..., description="Tên collection"),
    nhom_bo: str = Query(...),
    phan_loai: str = Query("Tất cả"),
    limit: int = Query(10)
):
    col = get_collection(server, trai)

    query = {}
    if nhom_bo != "Tất cả":
        query["NhomBo"] = nhom_bo
    if phan_loai != "Tất cả":
        query["PhanLoaiBo"] = phan_loai

    docs = list(col.find(query).limit(limit))

    results = []
    for d in docs:
        d["_id"] = str(d["_id"])
        bd = d.get("NgaySinh")
        age_days = get_age_days(bd)

        expected = classify_cow(d)
        actual = d.get("PhanLoaiBo")
        is_ok = (expected == actual)

        results.append({
            "_id": d["_id"],
            "KiemTra": "✅ Đúng" if is_ok else "❌ Sai",
            "SoTai": d.get("SoTai", ""),
            "NgaySinh": str(bd),
            "SoNgayTuoi": age_days,
            "GioiTinhBe": d.get("GioiTinhBe", ""),
            "SoNgayMangThai": d.get("SoNgayMangThai", ""),
            "NhomBo": d.get("NhomBo", ""),
            "PhanLoaiBo_DB": actual,
            "TenGiaiDoan_DB": stage_map.get(actual, "Không rõ"),
            "PhanLoaiBo_Expected": expected,
            "TenGiaiDoan_Expected": stage_map.get(expected, "Không rõ")
        })

    return results

def run_api():
    uvicorn.run(api_app, host="127.0.0.1", port=8000, log_level="error", timeout_keep_alive=120)

# Start FastAPI server in background thread
if "api_started" not in st.session_state:
    threading.Thread(target=run_api, daemon=True).start()
    st.session_state["api_started"] = True

# ========== STREAMLIT APP ==========
st.set_page_config(page_title="🐄 Giai đoạn bò", layout="wide")
st.title("🐄 Kiểm tra giai đoạn bò")

# chọn server Mongo
selected_server = st.selectbox("🔗 Chọn Mongo Server:", list(MONGO_CONNECTIONS.keys()))

# chọn collection (trại)
selected_trai = st.selectbox("🏠 Chọn trại:", list(TRAI_COLLECTIONS.keys()))

# chọn nhóm bò
group_options = ["Tất cả", "Bo", "Be", "BoChuyenVoBeo", "BoDucGiong"]
selected_group = st.selectbox("🐂 Chọn nhóm bò:", group_options)

# chọn phân loại
phanloai_options = [
    "Tất cả",
    "BeSinh", "BeTheoMe", "BeCaiSua", "BoHauBi",
    "BoNuoiThitBCT", "BoNuoiThitBCT8_12", "BoNuoiThitBCT18_20",
    "BoHauBiChoPhoi", "BoChoPhoi", "BoMoiPhoi",
    "BoMangThaiNho", "BoMangThaiLon", "BoChoDe",
    "BoMeNuoiConNho", "BoMeNuoiConLon",
    "BoVoBeoNho", "BoVoBeoLon", "BoDucChoBanThuongPham",
    "BoXuLySinhSan", "BoCachLy", "BoDucGiong"
]
selected_phanloai = st.selectbox("📌 Chọn phân loại bò:", phanloai_options)

# chọn số lượng
limit = st.number_input("📊 Số lượng records lấy từ DB:", min_value=1, max_value=150000, value=10)

if st.button("📡 Kiểm tra dữ liệu"):
    with st.spinner("⏳ Đang gọi API..."):
        params = {
            "server": selected_server,
            "trai": TRAI_COLLECTIONS[selected_trai],
            "nhom_bo": selected_group,
            "phan_loai": selected_phanloai,
            "limit": limit
        }
        try:
            res = requests.get("http://127.0.0.1:8000/giaidoanbo", params=params, timeout=120)
            if res.status_code == 200:
                data = res.json()
                st.success(f"✅ Lấy {len(data)} bản ghi thành công")
                st.dataframe(pd.DataFrame(data), use_container_width=True)
            else:
                st.error(f"❌ Lỗi API: {res.status_code}")
        except Exception as e:
            st.error(f"❌ Không kết nối được API: {e}")
