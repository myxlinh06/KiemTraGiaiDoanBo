# app_streamlit.py
import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from dateutil.relativedelta import relativedelta

st.set_page_config(page_title="🐄 Dự đoán giai đoạn bò", layout="wide")
st.title("🐄 Dự đoán giai đoạn bò — mô phỏng vòng đời")

API_URL = st.text_input("API URL (ví dụ http://127.0.0.1:8000/dudoangiaidoanbo)", value="http://127.0.0.1:8000/dudoangiaidoanbo")

limit = st.number_input("Số lượng records lấy từ DB:", min_value=1, max_value=150000, value=50)

trai_options = {
    "Trại IA PUCH": "BoNhapTrai",
    "Trại EA H'LEO": "BoNhapTrai_1",
    "Trại AD1": "BoNhapTrai_2",
    "Trại ERC": "BoNhapTrai_3",
    "Trại BSA": "BoNhapTrai_4",
}
selected_trai = st.selectbox("Chọn trại:", list(trai_options.keys()))

group_options = ["", "Bo", "Be", "BoChuyenVoBeo", "BoDucGiong"]
selected_group = st.selectbox("Chọn nhóm bò (bỏ trống = tất cả):", group_options)

phanloai_options = ["Tất cả","BeSinh","BeTheoMe","BeCaiSua","BoHauBi","BoNuoiThitBCT","BoNuoiThitBCT8_12","BoNuoiThitBCT18_20","BoHauBiChoPhoi","BoChoPhoi","BoMoiPhoi","BoMangThaiNho","BoMangThaiLon","BoChoDe","BoMeNuoiConNho","BoMeNuoiConLon","BoVoBeoNho","BoVoBeoLon","BoDucChoBanThuongPham","BoXuLySinhSan","BoCachLy","BoDucGiong"]
selected_phanloai = st.selectbox("Chọn phân loại bò:", phanloai_options)

so_tai_input = st.text_area("Nhập số tai (mỗi số 1 dòng hoặc cách nhau dấu phẩy)")

target_date = st.date_input("Chọn ngày đích (tương lai):", datetime.now().date())

if st.button("Lấy và dự đoán"):
    params = {
        "trai": trai_options[selected_trai],
        "limit": limit,
        "target_date": target_date.isoformat()
    }
    if selected_group:
        params["nhom_bo"] = selected_group
    if selected_phanloai and selected_phanloai != "Tất cả":
        params["phan_loai"] = selected_phanloai
    so_tai = ",".join([s.strip() for s in so_tai_input.replace("\n",",").split(",") if s.strip()])
    if so_tai:
        params["so_tai"] = so_tai

    try:
        resp = requests.get(API_URL, params=params, timeout=30)
        resp.raise_for_status()
        result = resp.json()
    except Exception as e:
        st.error(f"Lỗi gọi API: {e}")
        st.stop()

    data = result.get("data", [])
    if not data:
        st.warning("Không có bản ghi trả về.")
        st.stop()

    # show basic table
    df = pd.DataFrame([{
        "_id": r["_id"],
        "SoTai": r.get("SoTai"),
        "NgaySinh": r.get("NgaySinh"),
        "NhomBo": r.get("NhomBo"),
        "PhanLoaiBo_DB": r.get("PhanLoaiBo"),
        "TenGiaiDoan_DB": r.get("TenGiaiDoan_DB")
    } for r in data])
    st.subheader("Danh sách bò (DB)")
    st.dataframe(df, use_container_width=True)

    # Build prediction table: columns months from today to target_date
    # Use the Prediction map returned in each doc
    # Collect all months keys to ensure consistent columns
    all_months = set()
    for r in data:
        p = r.get("Prediction", {}) or {}
        all_months.update(p.keys())
    # sort months by parse mm/yyyy
    def mm_yyyy_to_dt(s):
        try:
            return datetime.strptime(s, "%m/%Y")
        except:
            return datetime.min
    months_sorted = sorted(list(all_months), key=mm_yyyy_to_dt)

    # build rows
    rows = []
    for r in data:
        row = {"SoTai": r.get("SoTai")}
        pred = r.get("Prediction", {}) or {}
        for m in months_sorted:
            stage_code = pred.get(m, "")
            row[m] = stage_code
        rows.append(row)

    pred_df = pd.DataFrame(rows)
    st.subheader("Dự đoán giai đoạn theo tháng (mã giai đoạn)")
    st.dataframe(pred_df, use_container_width=True)

    # also show with friendly names
    from dudoangiaidoanbo import stage_map
    pred_df_friendly = pred_df.copy()
    for c in months_sorted:
        pred_df_friendly[c] = pred_df_friendly[c].map(lambda code: stage_map.get(code, code))
    st.subheader("Dự đoán giai đoạn theo tháng (tên)")
    st.dataframe(pred_df_friendly, use_container_width=True)

    # Download CSV
    csv = pred_df_friendly.to_csv(index=False).encode("utf-8")
    st.download_button("Tải CSV kết quả dự đoán", data=csv, file_name="predictions.csv", mime="text/csv")
