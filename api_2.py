# dudoangiaidoanbo.py
from fastapi import FastAPI, Query
from pydantic import BaseModel
from typing import Optional, List
from pymongo import MongoClient
from datetime import datetime, date
from dudoangiaidoanbo import simulate_lifecycle, stage_map, parse_date
import os

app = FastAPI(title="API Dự đoán giai đoạn bò")

# CONFIG - chỉnh lại cho môi trường của bạn
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://root:tgx2025@103.48.84.200:27017/")
DB_NAME = os.environ.get("DB_NAME", "QuanLyTrangTraiDb")

TRAi_TO_COLLECTION = {
    "BoNhapTrai": "BoNhapTrai",
    "BoNhapTrai_1": "BoNhapTrai_1",
    "BoNhapTrai_2": "BoNhapTrai_2",
    "BoNhapTrai_3": "BoNhapTrai_3",
    "BoNhapTrai_4": "BoNhapTrai_4",
}

def get_collection(collection_key: str):
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client[DB_NAME]
    coll_name = TRAi_TO_COLLECTION.get(collection_key, collection_key)
    return db[coll_name]

@app.get("/dudoangiaidoanbo")
def predict(
    trai: str = Query(..., description="Tên key trại (ví dụ BoNhapTrai)"),
    nhom_bo: Optional[str] = Query(None),
    phan_loai: Optional[str] = Query("Tất cả"),
    limit: int = Query(100, ge=1),
    so_tai: Optional[str] = Query(None),
    # ngày đích trong format YYYY-MM-DD (nếu không set -> +6 months default)
    target_date: Optional[str] = Query(None)
):
    """
    Trả về dữ liệu bò và dự đoán vòng đời theo tháng tới target_date.
    """
    # pick collection
    coll = get_collection(trai)

    query = {}
    if nhom_bo:
        query["NhomBo"] = nhom_bo
    if phan_loai and phan_loai != "Tất cả":
        query["PhanLoaiBo"] = phan_loai
    if so_tai:
        # so_tai có thể là "A,B,C" -> $in list
        lst = [s.strip() for s in so_tai.split(",") if s.strip()]
        if lst:
            query["SoTai"] = {"$in": lst}

    # fetch docs
    docs = list(coll.find(query).limit(limit))

    # target_date
    if target_date:
        try:
            td = parse_date(target_date)
            if td is None:
                td = datetime.now()
        except:
            td = datetime.now()
    else:
        # default 6 months ahead
        td = datetime.now().replace(day=1)
        # add 6 months
        from dateutil.relativedelta import relativedelta
        td = (td + relativedelta(months=6))

    # simulate for each doc
    res = []
    for d in docs:
        try:
            # start month = now month
            start = datetime.now().date().replace(day=1)
            end = td.date().replace(day=1)
            lifecycle = simulate_lifecycle(d, start, end, base_now=datetime.now())
        except Exception as e:
            lifecycle = {"error": str(e)}

        # flatten doc for output (choose fields)
        out = {
            "_id": str(d.get("_id")),
            "SoTai": d.get("SoTai"),
            "NgaySinh": str(d.get("NgaySinh")),
            "GioiTinhBe": d.get("GioiTinhBe"),
            "TrongLuongNhap": d.get("TrongLuongNhap"),
            "SoNgayMangThai": d.get("SoNgayMangThai"),
            "NhomBo": d.get("NhomBo"),
            "PhanLoaiBo": d.get("PhanLoaiBo"),
            "TenGiaiDoan_DB": stage_map.get(d.get("PhanLoaiBo"), d.get("PhanLoaiBo")),
            "Prediction": lifecycle
        }
        res.append(out)

    return {"count": len(res), "data": res}
