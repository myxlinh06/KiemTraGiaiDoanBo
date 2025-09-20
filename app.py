import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="🐄 Giai đoạn bò", layout="wide")
st.title("🐄 Kiểm tra giai đoạn bò")

# ====== Input options ======
limit = st.number_input("Số lượng records lấy từ DB:", min_value=1, max_value=150000, value=10)

trai_options = {
    "Trại IA PUCH": "BoNhapTrai",
    "Trại EA H'LEO": "BoNhapTrai_1",
    "Trại AD1": "BoNhapTrai_2",
    "Trại ERC": "BoNhapTrai_3",
    "Trại BSA": "BoNhapTrai_4",
}
selected_trai = st.selectbox("Chọn trại:", list(trai_options.keys()))

group_options = ["Bo", "Be", "BoChuyenVoBeo", "BoDucGiong"]
selected_group = st.selectbox("Chọn nhóm bò:", group_options)

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
selected_phanloai = st.selectbox("Chọn phân loại bò:", phanloai_options)

# ====== Call API ======
if st.button("Kiểm tra dữ liệu"):
    with st.spinner("Đang gọi API..."):
        params = {
            "trai": trai_options[selected_trai],
            "nhom_bo": selected_group,
            "phan_loai": selected_phanloai,
            "limit": limit
        }
        res = requests.get("http://localhost:8000/giaidoanbo", params=params)

        if res.status_code == 200:
            data = res.json()
            st.success(f"Lấy {len(data)} bản ghi thành công ✅")
            st.dataframe(pd.DataFrame(data))
        else:
            st.error(f"Lỗi API: {res.status_code}")
