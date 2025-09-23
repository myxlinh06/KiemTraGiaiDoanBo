# app_full.py
import streamlit as st
import pandas as pd
import traceback
import requests
import threading
import uvicorn
from fastapi import FastAPI, Query
from pymongo import MongoClient
from datetime import datetime
from dateutil.relativedelta import relativedelta

# ================= Import logic riêng ==================
from giaidoanbo import classify_cow, stage_map, get_age_days
from dudoangiaidoanbo import simulate_lifecycle, parse_date

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

# Cache Mongo client connections
mongo_clients = {}
def get_collection(server_name: str, collection_name: str):
    if server_name not in mongo_clients:
        conn_str = MONGO_CONNECTIONS[server_name]
        mongo_clients[server_name] = MongoClient(conn_str, serverSelectionTimeoutMS=10000)
    client = mongo_clients[server_name]
    return client[DB_NAME][collection_name]

# ========== FASTAPI APP ==========
api_app = FastAPI(title="🐄 API quản lý bò")

# --- API 1: Kiểm tra giai đoạn bò ---
@api_app.get("/giaidoanbo")
def giaidoanbo(
    server: str = Query(...),
    trai: str = Query(...),
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
        age_days = get_age_days(d.get("NgaySinh"))
        expected = classify_cow(d)
        actual = d.get("PhanLoaiBo")
        is_ok = (expected == actual)
        results.append({
            "_id": d["_id"],
            "KiemTra": "✅ Đúng" if is_ok else "❌ Sai",
            "SoTai": d.get("SoTai", ""),
            "NgaySinh": str(d.get("NgaySinh")),
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

# --- API 2: Dự đoán vòng đời ---
@api_app.get("/dudoangiaidoanbo")
def predict(
    server: str = Query(...),
    trai: str = Query(...),
    nhom_bo: str = Query(None),
    phan_loai: str = Query("Tất cả"),
    limit: int = Query(100, ge=1),
    so_tai: str = Query(None),
    target_date: str = Query(None)
):
    col = get_collection(server, trai)
    query = {}
    if nhom_bo:
        query["NhomBo"] = nhom_bo
    if phan_loai and phan_loai != "Tất cả":
        query["PhanLoaiBo"] = phan_loai
    if so_tai:
        lst = [s.strip() for s in so_tai.split(",") if s.strip()]
        if lst:
            query["SoTai"] = {"$in": lst}
    docs = list(col.find(query).limit(limit))

    if target_date:
        try:
            td = parse_date(target_date) or datetime.now()
        except:
            td = datetime.now()
    else:
        td = (datetime.now().replace(day=1) + relativedelta(months=6))

    res = []
    for d in docs:
        try:
            start = datetime.now().date().replace(day=1)
            end = td.date().replace(day=1)
            lifecycle = simulate_lifecycle(d, start, end, base_now=datetime.now())
        except Exception as e:
            lifecycle = {"error": str(e)}

        out = {
            "_id": str(d.get("_id")),
            "SoTai": d.get("SoTai"),
            "NgaySinh": str(d.get("NgaySinh")),
            "NhomBo": d.get("NhomBo"),
            "PhanLoaiBo": d.get("PhanLoaiBo"),
            "TenGiaiDoan_DB": stage_map.get(d.get("PhanLoaiBo"), d.get("PhanLoaiBo")),
            "Prediction": lifecycle
        }
        res.append(out)
    return {"count": len(res), "data": res}

# Run FastAPI in background thread
def run_api():
    uvicorn.run(api_app, host="127.0.0.1", port=8000, log_level="error", timeout_keep_alive=600)

if "api_started" not in st.session_state:
    threading.Thread(target=run_api, daemon=True).start()
    st.session_state["api_started"] = True

# ========== STREAMLIT APP ==========
st.set_page_config(page_title="🐄 Quản lý giai đoạn bò", layout="wide")
st.title("🐄 Giao diện quản lý bò")

tab1, tab2 = st.tabs(["📡 Kiểm tra giai đoạn bò", "🔮 Dự đoán vòng đời"])

with tab1:
    selected_server = st.selectbox("🔗 Chọn Mongo Server:", list(MONGO_CONNECTIONS.keys()))
    selected_trai = st.selectbox("🏠 Chọn trại:", list(TRAI_COLLECTIONS.keys()))
    selected_group = st.selectbox("🐂 Chọn nhóm bò:", ["Tất cả", "Bo", "Be", "BoChuyenVoBeo", "BoDucGiong"])
    selected_phanloai = st.selectbox("📌 Chọn phân loại bò:", ["Tất cả"] + list(stage_map.keys()))
    limit = st.number_input("📊 Số lượng records:", min_value=1, max_value=100000, value=10)

    if st.button("📡 Kiểm tra dữ liệu"):
        params = {
            "server": selected_server,
            "trai": TRAI_COLLECTIONS[selected_trai],
            "nhom_bo": selected_group,
            "phan_loai": selected_phanloai,
            "limit": limit
        }
        
        
        try:
            res = requests.get("http://127.0.0.1:8000/giaidoanbo", params=params, timeout=600)
            if res.status_code == 200:
                data = res.json()
                st.success(f"✅ Lấy {len(data)} bản ghi thành công")
                st.dataframe(pd.DataFrame(data), use_container_width=True)
            else:
                st.error(f"❌ Lỗi API: {res.status_code}, nội dung: {res.text}")
        except requests.exceptions.RequestException as req_err:
            st.error(f"❌ Lỗi Requests: {req_err}")
            st.text(traceback.format_exc())
        except Exception as e:
            st.error(f"❌ Lỗi khác: {e}")
            st.text(traceback.format_exc())

with tab2:
    selected_server = st.selectbox("🔗 Chọn Mongo Server (dự đoán):", list(MONGO_CONNECTIONS.keys()))
    selected_trai = st.selectbox("🏠 Chọn trại (dự đoán):", list(TRAI_COLLECTIONS.keys()))

    so_tai_input = st.text_area("Nhập số tai (mỗi số 1 dòng hoặc cách nhau dấu phẩy)")
    target_date = st.date_input("Chọn ngày đích:", datetime.now().date() + relativedelta(months=6))

    if st.button("🔮 Dự đoán vòng đời"):
        so_tai = ",".join([s.strip() for s in so_tai_input.replace("\n", ",").split(",") if s.strip()])
        if not so_tai:
            st.warning("⚠️ Vui lòng nhập ít nhất 1 số tai!")
            st.stop()

        params = {
            "server": selected_server,
            "trai": TRAI_COLLECTIONS[selected_trai],
            "so_tai": so_tai,
            "limit": 200,  # limit lớn để không cắt mất
            "target_date": target_date.isoformat()
        }
        res = requests.get("http://127.0.0.1:8000/dudoangiaidoanbo", params=params, timeout=60)
        result = res.json()
        data = result["data"]

        if not data:
            st.warning("❌ Không tìm thấy dữ liệu cho số tai đã nhập.")
            st.stop()

        st.dataframe(pd.DataFrame([{
            "SoTai": r["SoTai"],
            "PhanLoaiBo_DB": r["PhanLoaiBo"],
            "TenGiaiDoan_DB": r["TenGiaiDoan_DB"]
        } for r in data]), use_container_width=True)

        # bảng dự đoán theo tháng
        all_months = set()
        for r in data: all_months.update(r["Prediction"].keys())
        months_sorted = sorted(list(all_months), key=lambda s: datetime.strptime(s, "%m/%Y"))
        rows = []
        for r in data:
            row = {"SoTai": r["SoTai"]}
            for m in months_sorted:
                row[m] = stage_map.get(r["Prediction"].get(m, ""), "")
            rows.append(row)
        pred_df = pd.DataFrame(rows)
        st.subheader("🔮 Dự đoán giai đoạn theo tháng")
        st.dataframe(pred_df, use_container_width=True)

        csv = pred_df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Tải CSV dự đoán", csv, "predictions.csv", "text/csv")
