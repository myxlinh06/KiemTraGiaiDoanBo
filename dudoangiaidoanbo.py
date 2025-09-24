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

def simulate_lifecycle_with_change_dates(doc, start_date, end_date, base_now=None, gestation_days=280, preg_test_prob=0.5):
    """
    Mô phỏng hàng ngày và trả về dict { "dd/mm/YYYY": stage_code } mỗi khi stage thay đổi.
    - last_breed_date: ngày phối (ngày bắt đầu đếm 45 ngày chờ test)
    - preg_start_date: ngày xác nhận có thai (nếu test dương)
    - preg_test_prob: xác suất test dương tại mốc >=45 ngày (mặc định 0.5)
    """
    from copy import deepcopy
    if base_now is None:
        base_now = datetime.now()

    # chuẩn hóa start_date/end_date thành datetime (nếu người gọi truyền date)
    if isinstance(start_date, datetime):
        cur = start_date
    else:
        cur = datetime.combine(start_date, datetime.min.time())
    if not isinstance(end_date, datetime):
        end = datetime.combine(end_date, datetime.min.time())
    else:
        end = end_date

    # khởi tạo từ doc
    # nếu trong doc đã có SoNgayMangThai (>0), suy ra preg_start_date = cur - preg_days
    initial_preg_days = safe_ceil(doc.get("SoNgayMangThai", 0))
    if initial_preg_days > 0:
        # assume thai bắt đầu initial_preg_days trước start
        preg_start_date = cur - timedelta(days=initial_preg_days)
    else:
        preg_start_date = None

    calf_age = safe_ceil(doc.get("SoNgayTuoiBeCon"), 0) if doc.get("SoNgayTuoiBeCon") not in (None, "") else None

    last_breed_date = None   # ngày phối gần nhất (chưa confirm)
    last_stage = None
    result = {}

    while cur <= end:
        temp = deepcopy(doc)

        # cập nhật số ngày mang thai hôm nay (nếu đã xác nhận)
        if preg_start_date:
            preg_days_today = (cur - preg_start_date).days
            temp["SoNgayMangThai"] = preg_days_today
        else:
            temp["SoNgayMangThai"] = 0

        # cập nhật tuổi bê con hôm nay (nếu có)
        if calf_age is not None:
            temp["SoNgayTuoiBeCon"] = calf_age

        # phân loại tại ngày cur
        stage = classify_cow(temp, now=cur, gestation_days=gestation_days)

        # nếu chuyển stage so với ngày trước → ghi ngày cur (ngày chuyển)
        if stage != last_stage:
            result[cur.strftime("%d/%m/%Y")] = stage
            last_stage = stage

            # nếu vừa chuyển **sang** BoMoiPhoi → gán ngay ngày phối (chỉ khi chưa có last_breed_date)
            if stage == "BoMoiPhoi" and last_breed_date is None and preg_start_date is None:
                last_breed_date = cur

        # --- xử lý sự kiện sinh sản hàng ngày ---
        # 1) Nếu đang chờ kết quả sau phối (last_breed_date set, chưa có preg_start_date)
        if last_breed_date and not preg_start_date:
            days_since_breed = (cur - last_breed_date).days
            if days_since_breed >= 45:
                # tới ngày test --> test kết quả
                if random.random() < preg_test_prob:
                    # test dương -> bắt đầu tính thai từ ngày phối
                    preg_start_date = last_breed_date
                    # clear last_breed_date vì đã confirm
                    last_breed_date = None
                else:
                    # test âm -> reset last_breed_date, coi như chưa có thai
                    last_breed_date = None

        # 2) Nếu đang mang thai, tăng ngày mang thai; nếu vượt gestation -> đẻ
        if preg_start_date:
            preg_days_now = (cur - preg_start_date).days
            if preg_days_now >= gestation_days:
                # đẻ: reset thai, khởi tạo bê con tuổi = 1 ngày
                preg_start_date = None
                last_breed_date = None
                calf_age = 1
                # stage ở vòng lặp tiếp theo sẽ là "BoMeNuoiConNho" do calf_age =1

        # 3) Nếu đang nuôi con → tăng tuổi bê con
        if calf_age is not None:
            calf_age += 1
            if calf_age > 120:
                calf_age = None  # cai sữa xong

        # advance one day
        cur += timedelta(days=1)

    return result
