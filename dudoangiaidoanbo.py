from datetime import datetime, timedelta
import math, random

# ---------- Helpers ----------
def safe_ceil(value, default=0):
    try:
        if value is None or value == "":
            return default
        return math.ceil(float(value))
    except (ValueError, TypeError):
        return default

def parse_date(val):
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(val, fmt)
            except Exception:
                continue
        try:
            return datetime.fromisoformat(val)
        except Exception:
            return None
    return None

def days_between(d1, d2):
    return (d2.date() - d1.date()).days

# ---------- Stage map ----------
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
    "BoMangThaiNho": "Bò mang thai 2-7 tháng",
    "BoMangThaiLon": "Bò mang thai 8-9 tháng",
    "BoChoDe": "Bò chờ đẻ >9 tháng",
    "BoMeNuoiConNho": "Bò mẹ nuôi con 0-2 tháng",
    "BoMeNuoiConLon": "Bò mẹ nuôi con >2-4 tháng",
    "BoVoBeoNho": "Bò vỗ béo nhỏ",
    "BoVoBeoLon": "Bò vỗ béo lớn",
    "BoDucChoBanThuongPham": "Bò vỗ béo thương phẩm (đực)",
    "BoCaiChoBanThuongPham": "Bò vỗ béo thương phẩm (cái)",
    "BoCachLy": "Bò cách ly",
    "BoDucGiong": "Đực giống",
    "KhongXacDinh": "Không xác định"
}

# ---------- Core classify ----------
def classify_cow(doc, now=None, gestation_days=280):
    if now is None:
        now = datetime.now()

    bd_raw = doc.get("NgaySinh")
    birth_date = parse_date(bd_raw)
    gender = str(doc.get("GioiTinhBe", "")).strip().lower()
    if gender in ("nam", "male", "duc"): gender = "đực"
    if gender in ("nu", "female", "cai"): gender = "cái"

    age_days = days_between(birth_date, now) + 1 if birth_date else None
    preg_days = safe_ceil(doc.get("SoNgayMangThai", 0))
    calf_age = safe_ceil(doc.get("SoNgayTuoiBeCon"), 0) if doc.get("SoNgayTuoiBeCon") not in (None, "") else None
    group = doc.get("NhomBo", "")

    # Đực giống / cách ly
    if group == "BoDucGiong": return "BoDucGiong"
    if group == "BoCachLy": return "BoCachLy"

    # Bê (cả đực & cái đều qua giai đoạn bê)
    if age_days is not None:
        if age_days <= 60: return "BeSinh"
        if age_days <= 120: return "BeTheoMe"
        if age_days <= 210: return "BeCaiSua"
        if age_days <= 360: return "BoNuoiThitBCT8_12" if gender == "đực" else "BoHauBi"
        if 360 < age_days <= 540: return "BoNuoiThitBCT" if gender == "đực" else "BoHauBiChoPhoi"

    # Đực → nuôi thịt, vỗ béo
    if gender == "đực" and age_days is not None:
        if 540 < age_days <= 600: return "BoNuoiThitBCT18_20"
        if 600 < age_days <= 690: return "BoVoBeoNho"
        if 690 < age_days <= 720: return "BoVoBeoLon"
        if age_days > 720: return "BoDucChoBanThuongPham"

    # Cái → sinh sản / vỗ béo
    if gender == "cái":
        if age_days and group == "BoChuyenVoBeo":
            if 600 < age_days <= 690: return "BoVoBeoNho"
            if 690 < age_days <= 720: return "BoVoBeoLon"
            if age_days > 720: return "BoCaiChoBanThuongPham"

        # Sinh sản
        if preg_days > 0:
            if preg_days <= 210: return "BoMangThaiNho"
            if preg_days <= 270: return "BoMangThaiLon"
            if preg_days > 270: return "BoChoDe"
        if calf_age is not None:
            if calf_age <= 60: return "BoMeNuoiConNho"
            if calf_age <= 120: return "BoMeNuoiConLon"
            if calf_age > 120: return "BoChoPhoi"
        if age_days and age_days > 540: return "BoChoPhoi"
        return "BoMoiPhoi"

    return "KhongXacDinh"

# ---------- Xác định giai đoạn bò hiện tại ----------
def get_real_current_stage(doc, now=None, gestation_days=280):
    """
    Trả về giai đoạn hiện tại chính xác (tính theo ngày hôm nay hoặc 'now' truyền vào).
    """
    if now is None:
        now = datetime.now()
    stage_code = classify_cow(doc, now=now, gestation_days=gestation_days)
    return {
        "StageCode": stage_code,
        "StageName": stage_map.get(stage_code, "Không xác định"),
        "NgayKiemTra": now.strftime("%d/%m/%Y")
    }

# ---------- Simulation lifecycle ----------
def simulate_lifecycle(doc, start_date, end_date, base_now=None, gestation_days=280):
    from copy import deepcopy
    if base_now is None: base_now = datetime.now()

    cur = start_date.replace(day=1)
    end = end_date.replace(day=1)

    preg_days = safe_ceil(doc.get("SoNgayMangThai", 0))
    calf_age = safe_ceil(doc.get("SoNgayTuoiBeCon"), 0) if doc.get("SoNgayTuoiBeCon") not in (None, "") else None

    result = {}
    while cur <= end:
        temp = deepcopy(doc)
        temp["SoNgayMangThai"] = preg_days
        if calf_age is not None: temp["SoNgayTuoiBeCon"] = calf_age

        # nếu là tháng hiện tại → tính theo ngày hôm nay
        if cur.year == base_now.year and cur.month == base_now.month:
            check_date = base_now
        else:
            check_date = datetime(cur.year, cur.month, 1)

        stage = classify_cow(temp, now=check_date, gestation_days=gestation_days)
        result[cur.strftime("%m/%Y")] = stage

        # tiến tới tháng kế
        if cur.month == 12: next_cur = cur.replace(year=cur.year+1, month=1)
        else: next_cur = cur.replace(month=cur.month+1)
        delta_days = (next_cur - cur).days

        # cập nhật trạng thái theo hành vi sinh sản
        if preg_days > 0:
            preg_days += delta_days
            if preg_days >= gestation_days:
                # đẻ → reset thai, bắt đầu nuôi con
                preg_days = 0
                calf_age = 1
        else:
            if stage == "BoMoiPhoi":
                # sau khi phối 45 ngày → coi như có thai
                preg_days = 45
            elif stage == "BoChoPhoi":
                # kiểm tra lịch khám
                if random.random() < 0.5:
                    preg_days = 10  # có thai nhỏ
            if calf_age is not None:
                calf_age += delta_days
                if calf_age > 120:
                    calf_age = None  # cai sữa, quay lại chờ phối
                elif calf_age <= 60 and random.random() < 0.05:
                    # 5% mẹ đang nuôi con <2 tháng → mới phối
                    preg_days = 10
                elif 60 < calf_age <= 120 and random.random() < 0.95:
                    # 95% mẹ 2-4 tháng → chờ phối
                    calf_age = 121  

        cur = next_cur

    return result

def simulate_lifecycle_with_change_dates(doc, start_date, end_date,
                                         base_now=None,
                                         gestation_days=280,
                                         preg_test_prob=0.5):
    """
    Mô phỏng vòng đời bò theo bảng giai đoạn & hành vi sinh sản.
    Trả về dict { "dd/mm/YYYY": stage_code } khi stage thay đổi.
    """

    from copy import deepcopy
    from datetime import datetime, timedelta
    import random

    if base_now is None:
        base_now = datetime.now()

    # chuẩn hóa start_date / end_date
    if isinstance(start_date, datetime):
        cur = start_date
    else:
        cur = datetime.combine(start_date, datetime.min.time())
    if not isinstance(end_date, datetime):
        end = datetime.combine(end_date, datetime.min.time())
    else:
        end = end_date

    # trạng thái ban đầu
    initial_preg_days = safe_ceil(doc.get("SoNgayMangThai", 0))
    if initial_preg_days > 0:
        preg_start_date = cur - timedelta(days=initial_preg_days)
    else:
        preg_start_date = None

    calf_age = safe_ceil(doc.get("SoNgayTuoiBeCon", 0)) if doc.get("SoNgayTuoiBeCon") not in (None, "") else None

    last_breed_date = None   # ngày phối gần nhất
    last_wait_date = None    # ngày bắt đầu chờ phối
    last_stage = None
    result = {}

    while cur <= end:
        temp = deepcopy(doc)

        # cập nhật số ngày mang thai hôm nay (nếu có)
        if preg_start_date:
            temp["SoNgayMangThai"] = (cur - preg_start_date).days
        else:
            temp["SoNgayMangThai"] = 0

        # cập nhật tuổi bê con
        if calf_age is not None:
            temp["SoNgayTuoiBeCon"] = calf_age

        # phân loại stage hiện tại
        stage = classify_cow(temp, now=cur, gestation_days=gestation_days)

        # khi stage thay đổi → ghi nhận
        if stage != last_stage:
            result[cur.strftime("%d/%m/%Y")] = stage
            last_stage = stage
            if stage == "BoChoPhoi":
                last_wait_date = cur
            if stage == "BoMoiPhoi":
                last_breed_date = cur

        # ====== XỬ LÝ HÀNH VI SỰ KIỆN ======

        # 1) Bò chờ phối → sau 30 ngày thì sang "Bò mới phối"
        if last_wait_date and not last_breed_date and not preg_start_date:
            days_wait = (cur - last_wait_date).days
            if days_wait >= 30:
                last_breed_date = cur
                stage = "BoMoiPhoi"
                result[cur.strftime("%d/%m/%Y")] = stage
                last_stage = stage
                last_wait_date = None

        # 2) Bò mới phối → sau 50 ngày chắc chắn thành mang thai
        if last_breed_date and not preg_start_date:
            days_since_breed = (cur - last_breed_date).days
            if days_since_breed >= 50:
                preg_start_date = last_breed_date
                last_breed_date = None
                stage = "BoMangThaiNho"
                result[cur.strftime("%d/%m/%Y")] = stage
                last_stage = stage

        # 3) Nếu đang có thai → đến ngày đẻ
        if preg_start_date:
            preg_days_now = (cur - preg_start_date).days
            if preg_days_now >= gestation_days:
                # đẻ: reset thai, tạo bê con
                preg_start_date = None
                last_breed_date = None
                calf_age = 1  # bê sơ sinh
                stage = "BoMeNuoiConNho"
                result[cur.strftime("%d/%m/%Y")] = stage
                last_stage = stage

        # 4) Nếu đang nuôi con → tăng tuổi bê con
        if calf_age is not None:
            calf_age += 1
            if calf_age > 120:
                calf_age = None
                stage = "BoChoPhoi"
                result[cur.strftime("%d/%m/%Y")] = stage
                last_stage = stage
                last_wait_date = cur
            elif 61 <= calf_age <= 120:
                # 5% cơ hội được phối ngay
                if random.random() < 0.05 and not preg_start_date and not last_breed_date:
                    calf_age = None
                    last_breed_date = cur
                    stage = "BoMoiPhoi"
                    result[cur.strftime("%d/%m/%Y")] = stage
                    last_stage = stage

        # advance 1 ngày
        cur += timedelta(days=1)

    return result
