import os
from urllib.parse import quote_plus
from pymongo import MongoClient
import streamlit as st
from datetime import datetime

# ====== Kết nối MongoDB ======
# def get_mongo_collection():
#     """Kết nối tới MongoDB"""
#     uri = "mongodb://root:tgx2025@103.48.84.200:27017/"
#     client = MongoClient(uri, serverSelectionTimeoutMS=5000)
#     db = client["QuanLyTrangTraiDb"]
#     return db["collection_name"]
def get_mongo_collection(collection_name: str):
    """Kết nối tới MongoDB và trả về collection theo tên"""
    uri = "mongodb://root:tgx2025@103.48.84.200:27017/"
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    db = client["QuanLyTrangTraiDb"]
    return db[collection_name]

# ====== Rule phân loại ======
def classify_cow(doc):
    now = datetime.now()

    # --- Map field ---
    cow_id = str(doc.get("_id"))
    ear_tag = doc.get("SoTai", "")
    birth_date = None
    bd = doc.get("NgaySinh")
    if bd:
        if isinstance(bd, datetime):
            birth_date = bd
        elif isinstance(bd, str):
            try:
                birth_date = datetime.fromisoformat(bd)
            except Exception:
                birth_date = None

    gender = str(doc.get("GioiTinhBe", "")).lower()
    def safe_int(value, default=0):
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    pregnant_days = safe_int(doc.get("SoNgayMangThai", 0))

    group = doc.get("NhomBo", "")
    current_stage = doc.get("PhanLoaiBo", "")
    
    # --- Tính số ngày tuổi ---
    age_days = (now.date() - birth_date.date()).days + 1 if birth_date else None

    # ===== RULE =====
    if age_days is not None:

        # ==== GIAI ĐOẠN BÊ ====
        if age_days <= 60:
            return "BeSinh"
        elif 60 < age_days <= 120:
            return "BeTheoMe"
        elif 120 < age_days <= 210:
            return "BeCaiSua"
        elif 210 < age_days <= 360:
            if gender == "đực":
                return "BoNuoiThitBCT8_12"
            elif gender == "cái":
                return "BoHauBi"

        # ==== GIAI ĐOẠN BÒ HẬU BỊ ====
        if 360 < age_days <= 540:
            if gender == "đực":
                return "BoNuoiThitBCT"
            elif gender == "cái" and pregnant_days ==0:
                return "BoHauBiChoPhoi"

        if 540 < age_days <= 600 and gender == "đực":
            return "BoNuoiThitBCT18_20"

        # ==== VỖ BÉO ====
        if 600 < age_days <= 690:
            if gender == "đực":
                return "BoVoBeoNho"
            if gender == "cái" and pregnant_days ==0:
                return "BoVoBeoNho"

        if 690 < age_days <= 720:
            if gender == "đực":
                return "BoVoBeoLon"
            if gender == "cái" and pregnant_days ==0:
                return "BoVoBeoLon"

        if age_days > 720:
            if gender == "đực":
                return "BoDucChoBanThuongPham"
            if gender == "cái" and pregnant_days == 0:
                return "BoCaiChoBanThuongPham"
            
    # ==== Bò mẹ nuôi con / bò mang thai / bò chờ phối ====
    if gender == "cái":
        # Mang thai
        if pregnant_days > 0:
            if pregnant_days <= 210:
                return "BoMangThaiNho"
            elif pregnant_days <= 270:
                return "BoMangThaiLon"
            else:
                return "BoChoDe"

        # Nếu có thông tin sinh sản 
        tinh_trang = doc.get("TinhTrangSinhSan", "")
        sinh_san = doc.get("ThongTinSinhSans") or {}
        if not isinstance(sinh_san, dict):
            sinh_san = {}
        ngay_sinh_be = sinh_san.get("NgaySinh")
        
        x = None
        if ngay_sinh_be:
            try:
                if isinstance(ngay_sinh_be, str):
                    ngay_sinh_be = datetime.fromisoformat(ngay_sinh_be)
                x = (now - ngay_sinh_be).days + 1
            except Exception:
                x = None

        if x is not None:
            if 1 <= x <= 60:
                return "BoMeNuoiConNho"
            elif 60 < x <= 120:
                return "BoMeNuoiConLon"
            elif x > 120:
                if tinh_trang == "Bò chờ phối":
                    return "BoChoPhoi"
                elif tinh_trang == "Bò mới phối":
                    return "BoMoiPhoi"
        else:
            # Nếu không có NgaySinh hoặc = 0 thì xét theo tình trạng sinh sản
            if tinh_trang == "Bò chờ phối":
                return "BoChoPhoi"
            elif tinh_trang == "Bò mới phối":
                return "BoMoiPhoi"
        # Nếu không rơi vào các case trên → bò chờ phối mặc định
        return "BoChoPhoi"

    
    # ==== NHÓM ĐẶC BIỆT ====
    if group == "BoXuLySinhSan":
        return "BoXuLySinhSan"
    if group == "BoCachLy":
        return "BoCachLy"
    if group == "BoDucGiong":
        return "BoDucGiong"
    return "KhongXacDinh"

# ===== Map PhanLoaiBo -> Tên giai đoạn =====
stage_map = {
    "BeSinh": "Bê theo mẹ 0-2 tháng",
    "BeTheoMe": "Bê theo mẹ >2-4 tháng",
    "BeCaiSua": "Bê cai sữa >4-7 tháng",
    "BoNuoiThitBCT8_12": "Bê đực >7-12 tháng",
    "BoHauBi": "Bê hậu bị >7-12 tháng",
    "BoNuoiThitBCT": "Bò nuôi thịt BCT >12-18 tháng",
    "BoHauBiChoPhoi": "Bò hậu bị chờ phối >12-18 tháng",
    "BoNuoiThitBCT18_20": "Bò nuôi thịt BCT >18-20 tháng",
    "BoChoPhoi": "Bò chờ phối",
    "BoMoiPhoi": "Bò mới phối",
    "BoMangThaiNho": "Bò mang thai 2-7 tháng",
    "BoMangThaiLon": "Bò mang thai 8-9 tháng",
    "BoChoDe": "Bò chờ đẻ >9 tháng",
    "BoMeNuoiConNho": "Bò mẹ nuôi con 0-2 tháng",
    "BoMeNuoiConLon": "Bò mẹ nuôi con >2-4 tháng",
    "BoVoBeoNho": "Bò vỗ béo nhỏ",
    "BoVoBeoLon": "Bò vỗ béo lớn",
    "BoDucChoBanThuongPham": "Bò vỗ béo thương phẩm",
    "BoCaiChoBanThuongPham": "Bò vỗ béo thương phẩm",
    "BoXuLySinhSan": "Bò xử lý sinh sản",
    "BoCachLy": "Bò cách ly",
    "BoDucGiong": "Đực giống",
    "KhongXacDinh": "Không xác định"
}

# ====== Streamlit App ======
st.set_page_config(page_title="🐄 Giai đoạn bò", layout="wide")
st.title("🐄 Kiểm tra giai đoạn bò")
st.markdown("Tool kiểm tra dữ liệu bò theo rule.")

# limit = st.number_input("Số lượng records lấy từ DB:", min_value=1, max_value=150000, value=10)

# ====== Selectbox chọn trại ======
trai_options = {
    "Trại IA PUCH": "BoNhapTrai",
    "Trại EA H'LEO": "BoNhapTrai_1",
    "Trại AD1": "BoNhapTrai_2",
    "Trại ERC": "BoNhapTrai_3",
    "Trại BSA": "BoNhapTrai_4",
}
selected_trai = st.selectbox("Chọn trại:", list(trai_options.keys()))

# ====== Chọn nhóm bò ======
group_options = ["Bo", "Be", "BoChuyenVoBeo", "BoDucGiong"]
selected_group = st.selectbox("Chọn nhóm bò:", group_options)

# ====== Chọn phân loại bò ======
phanloai_options = [
    "BeSinh", "BeTheoMe", "BeCaiSua", "BoHauBi",
    "BoNuoiThitBCT", "BoNuoiThitBCT8_12", "BoNuoiThitBCT18_20",
    "BoHauBiChoPhoi", "BoChoPhoi", "BoMoiPhoi",
    "BoMangThaiNho", "BoMangThaiLon", "BoChoDe",
    "BoMeNuoiConNho", "BoMeNuoiConLon",
    "BoVoBeoNho", "BoVoBeoLon", "BoDucChoBanThuongPham", "BoCaiChoBanThuongPham",
    "BoXuLySinhSan", "BoCachLy", "BoDucGiong"
]
selected_phanloai = st.selectbox("Chọn phân loại bò:", ["Tất cả"] + phanloai_options)

# ====== Query DB ======
if st.button("Kiểm tra dữ liệu"):
    with st.spinner("Đang lấy dữ liệu từ MongoDB..."):
        cows = get_mongo_collection(trai_options[selected_trai]) 

        query = {"NhomBo": selected_group}
        if selected_phanloai != "Tất cả":
            query["PhanLoaiBo"] = selected_phanloai

        docs = list(cows.find(query)) 


    results = []
    for d in docs:
        expected = classify_cow(d)
        actual = d.get("PhanLoaiBo")
        is_ok = (expected == actual)

        results.append({
    "_id": str(d.get("_id")),
    "SoTai": d.get("SoTai", ""),
    "NgaySinh": str(d.get("NgaySinh")),
    "GioiTinhBe": d.get("GioiTinhBe", ""),
    "SoNgayMangThai": d.get("SoNgayMangThai", ""),
    "NhomBo": d.get("NhomBo", ""),
    "PhanLoaiBo (DB)": actual,
    "TinhTrangSS (DB)": d.get("TinhTrangSinhSan", ""),
    "Tên giai đoạn (DB)": stage_map.get(actual, "Không rõ"),
    "PhanLoaiBo (Expected)": expected,
    "Tên giai đoạn (Expected)": stage_map.get(expected, "Không rõ"),
    "✅ Đúng/❌ Sai": "✅ Đúng" if expected == actual else "❌ Sai"
})


    st.subheader("📋 Kết quả kiểm tra")
    st.dataframe(results)
