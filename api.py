from fastapi import FastAPI, Query
from pymongo import MongoClient
from giaidoanbo import classify_cow, stage_map, get_age_days
from datetime import datetime

app = FastAPI(title="🐄 API Phân loại giai đoạn bò")

def get_mongo_collection(collection_name: str):
    # uri = "mongodb://root:tgx2025@103.48.84.200:27017/"
    uri = "mongodb://admin:tgx2025@103.48.84.199:27017/?authSource=admin"
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    db = client["QuanLyTrangTraiDb"]
    return db[collection_name]

@app.get("/giaidoanbo")
def classify(
    trai: str,
    nhom_bo: str,
    phan_loai: str = "Tất cả",
    limit: int = 10
):
    cows = get_mongo_collection(trai)

    query = {"NhomBo": nhom_bo}
    if phan_loai != "Tất cả":
        query["PhanLoaiBo"] = phan_loai

    docs = list(cows.find(query).limit(limit))

    results = []
    for d in docs:
        expected = classify_cow(d)
        actual = d.get("PhanLoaiBo")
        is_ok = (expected == actual)

        bd = d.get("NgaySinh")
        age_days = get_age_days(bd)

        results.append({
            "_id": str(d.get("_id")),
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
