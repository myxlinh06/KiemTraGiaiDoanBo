import os
from urllib.parse import quote_plus
from pymongo import MongoClient
import streamlit as st
from datetime import datetime

# ====== Kết nối MongoDB ======
def get_mongo_collection():
    """Kết nối tới MongoDB"""
    uri = "mongodb://root:tgx2025@103.48.84.200:27017/"
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    db = client["QuanLyTrangTraiDb"]
    return db["BoNhapTrai_1"]

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
    weight = doc.get("TrongLuongNhap", 0) or 0
    pregnant_months = doc.get("SoThangMangThai", 0) or 0
    group = doc.get("NhomBo", "")
    current_stage = doc.get("PhanLoaiBo", "")
    calf_age_days = doc.get("SoNgayTuoiBeCon", None)  # số ngày tuổi bê con (cho bò mẹ)

    # --- Tính số ngày tuổi ---
    age_days = ((now - birth_date).days + 1) if birth_date else None
    pregnant_days = pregnant_months * 30  # số ngày mang thai

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
            elif gender == "cái":
                return "BoHauBiChoPhoi"

        if 540 < age_days <= 600 and gender == "đực":
            return "BoNuoiThitBCT18_20"

        if age_days > 540 and gender == "cái":
            # Mang thai
            if pregnant_days > 0:
                if pregnant_days <= 210:
                    return "BoMangThaiNho"
                elif pregnant_days <= 270:
                    return "BoMangThaiLon"
                else:
                    return "BoChoDe"

            # Bò mẹ nuôi con
            if calf_age_days is not None:
                if calf_age_days <= 60:
                    return "BoMeNuoiConNho"
                elif 60 < calf_age_days <= 120:
                    return "BoMeNuoiConLon"

            # Nếu không phải bò mẹ nuôi con -> bò chờ phối
            return "BoChoPhoi"

        # ==== VỖ BÉO ====
        if 600 < age_days <= 690:
            if gender == "đực" and 430 <= weight <= 510:
                return "BoVoBeoNho"
            if gender == "cái" and 380 <= weight <= 450:
                return "BoVoBeoNho"

        if 690 < age_days <= 720:
            if gender == "đực" and 510 < weight <= 550:
                return "BoVoBeoLon"
            if gender == "cái" and 450 < weight <= 480:
                return "BoVoBeoLon"

        if age_days > 720:
            if gender == "đực" and weight > 550:
                return "BoDucChoBanThuongPham"
            if gender == "cái" and weight > 480:
                return "BoCaiChoBanThuongPham"

    # ==== NHÓM ĐẶC BIỆT ====
    if group == "BoXuLySinhSan":
        return "BoXuLySinhSan"
    if group == "BoCachLy":
        return "BoCachLy"
    if group == "BoDucGiong":
        return "BoDucGiong"
    return "KhongXacDinh"

# ====== Streamlit App ======
st.set_page_config(page_title="🐄 Giai đoạn bò", layout="wide")
st.title("🐄 Kiểm tra giai đoạn bò")
st.markdown("Tool kiểm tra dữ liệu bò theo rule.")

limit = st.number_input("Số lượng records lấy từ DB:", min_value=1, max_value=150000, value=10)

if st.button("Kiểm tra dữ liệu"):
    with st.spinner("Đang lấy dữ liệu từ MongoDB..."):
        cows = get_mongo_collection()
        allowed_groups = ["Be", "Bo", "BoChuyenVoBeo", "BoDucGiong"]
        docs = list(cows.find({"NhomBo": {"$in": allowed_groups}}).limit(limit))

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
            "TrongLuongNhap": d.get("TrongLuongNhap", ""),
            "SoThangMangThai": d.get("SoThangMangThai", ""),
            "NhomBo": d.get("NhomBo", ""),
            "PhanLoaiBo (DB)": actual,
            "PhanLoaiBo (Expected)": expected,
            "✅ Đúng/❌ Sai": "✅ Đúng" if is_ok else "❌ Sai"
        })

    st.subheader("📋 Kết quả kiểm tra")
    st.dataframe(results)
