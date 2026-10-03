"""
DaysHub 农历引擎
- 公历/农历双向换算（基于 zhdate）
- 24节气查询
- 里程碑计算（100天/1000天/周年）
- 进度条计算（年/月/人生）
- 法定节假日内置
"""
from datetime import date, datetime, timedelta
from zhdate import ZhDate

# ========== 24节气名称（2026年前后常用，动态计算不现实，内置近5年数据） ==========
# 节气时间表 {年份: [(月, 日, 节气名), ...]}
SOLAR_TERMS_2024_2030 = {
    2024: [
        (1,6,"小寒"),(1,20,"大寒"),(2,4,"立春"),(2,19,"雨水"),(3,5,"惊蛰"),(3,20,"春分"),
        (4,4,"清明"),(4,19,"谷雨"),(5,5,"立夏"),(5,20,"小满"),(6,5,"芒种"),(6,21,"夏至"),
        (7,6,"小暑"),(7,22,"大暑"),(8,7,"立秋"),(8,22,"处暑"),(9,7,"白露"),(9,22,"秋分"),
        (10,8,"寒露"),(10,23,"霜降"),(11,7,"立冬"),(11,22,"小雪"),(12,7,"大雪"),(12,21,"冬至"),
    ],
    2025: [
        (1,5,"小寒"),(1,20,"大寒"),(2,3,"立春"),(2,18,"雨水"),(3,5,"惊蛰"),(3,20,"春分"),
        (4,4,"清明"),(4,20,"谷雨"),(5,5,"立夏"),(5,21,"小满"),(6,5,"芒种"),(6,21,"夏至"),
        (7,7,"小暑"),(7,22,"大暑"),(8,7,"立秋"),(8,23,"处暑"),(9,7,"白露"),(9,23,"秋分"),
        (10,8,"寒露"),(10,23,"霜降"),(11,7,"立冬"),(11,22,"小雪"),(12,7,"大雪"),(12,21,"冬至"),
    ],
    2026: [
        (1,5,"小寒"),(1,20,"大寒"),(2,4,"立春"),(2,18,"雨水"),(3,5,"惊蛰"),(3,20,"春分"),
        (4,5,"清明"),(4,20,"谷雨"),(5,5,"立夏"),(5,21,"小满"),(6,5,"芒种"),(6,21,"夏至"),
        (7,7,"小暑"),(7,22,"大暑"),(8,7,"立秋"),(8,23,"处暑"),(9,7,"白露"),(9,23,"秋分"),
        (10,8,"寒露"),(10,23,"霜降"),(11,7,"立冬"),(11,22,"小雪"),(12,7,"大雪"),(12,22,"冬至"),
    ],
    2027: [
        (1,5,"小寒"),(1,20,"大寒"),(2,4,"立春"),(2,19,"雨水"),(3,6,"惊蛰"),(3,21,"春分"),
        (4,5,"清明"),(4,20,"谷雨"),(5,6,"立夏"),(5,21,"小满"),(6,6,"芒种"),(6,21,"夏至"),
        (7,7,"小暑"),(7,23,"大暑"),(8,8,"立秋"),(8,23,"处暑"),(9,8,"白露"),(9,23,"秋分"),
        (10,8,"寒露"),(10,24,"霜降"),(11,7,"立冬"),(11,22,"小雪"),(12,7,"大雪"),(12,22,"冬至"),
    ],
    2028: [
        (1,6,"小寒"),(1,20,"大寒"),(2,4,"立春"),(2,19,"雨水"),(3,5,"惊蛰"),(3,20,"春分"),
        (4,4,"清明"),(4,19,"谷雨"),(5,5,"立夏"),(5,20,"小满"),(6,5,"芒种"),(6,21,"夏至"),
        (7,7,"小暑"),(7,22,"大暑"),(8,7,"立秋"),(8,22,"处暑"),(9,7,"白露"),(9,22,"秋分"),
        (10,8,"寒露"),(10,23,"霜降"),(11,7,"立冬"),(11,22,"小雪"),(12,7,"大雪"),(12,21,"冬至"),
    ],
    2029: [
        (1,5,"小寒"),(1,20,"大寒"),(2,3,"立春"),(2,18,"雨水"),(3,5,"惊蛰"),(3,20,"春分"),
        (4,4,"清明"),(4,20,"谷雨"),(5,5,"立夏"),(5,21,"小满"),(6,5,"芒种"),(6,21,"夏至"),
        (7,7,"小暑"),(7,22,"大暑"),(8,7,"立秋"),(8,23,"处暑"),(9,7,"白露"),(9,23,"秋分"),
        (10,8,"寒露"),(10,23,"霜降"),(11,7,"立冬"),(11,22,"小雪"),(12,7,"大雪"),(12,22,"冬至"),
    ],
    2030: [
        (1,5,"小寒"),(1,20,"大寒"),(2,4,"立春"),(2,18,"雨水"),(3,5,"惊蛰"),(3,20,"春分"),
        (4,5,"清明"),(4,20,"谷雨"),(5,5,"立夏"),(5,21,"小满"),(6,5,"芒种"),(6,21,"夏至"),
        (7,7,"小暑"),(7,22,"大暑"),(8,7,"立秋"),(8,23,"处暑"),(9,7,"白露"),(9,23,"秋分"),
        (10,8,"寒露"),(10,23,"霜降"),(11,7,"立冬"),(11,22,"小雪"),(12,7,"大雪"),(12,22,"冬至"),
    ],
    2031: [
        (1,5,"小寒"),(1,20,"大寒"),(2,4,"立春"),(2,19,"雨水"),(3,6,"惊蛰"),(3,21,"春分"),
        (4,5,"清明"),(4,20,"谷雨"),(5,6,"立夏"),(5,21,"小满"),(6,6,"芒种"),(6,21,"夏至"),
        (7,7,"小暑"),(7,23,"大暑"),(8,8,"立秋"),(8,23,"处暑"),(9,8,"白露"),(9,23,"秋分"),
        (10,8,"寒露"),(10,24,"霜降"),(11,7,"立冬"),(11,22,"小雪"),(12,7,"大雪"),(12,22,"冬至"),
    ],
    2032: [
        (1,6,"小寒"),(1,21,"大寒"),(2,4,"立春"),(2,19,"雨水"),(3,5,"惊蛰"),(3,20,"春分"),
        (4,4,"清明"),(4,19,"谷雨"),(5,5,"立夏"),(5,20,"小满"),(6,5,"芒种"),(6,21,"夏至"),
        (7,6,"小暑"),(7,22,"大暑"),(8,7,"立秋"),(8,22,"处暑"),(9,7,"白露"),(9,22,"秋分"),
        (10,8,"寒露"),(10,23,"霜降"),(11,7,"立冬"),(11,22,"小雪"),(12,6,"大雪"),(12,21,"冬至"),
    ],
    2033: [
        (1,5,"小寒"),(1,20,"大寒"),(2,3,"立春"),(2,18,"雨水"),(3,5,"惊蛰"),(3,20,"春分"),
        (4,4,"清明"),(4,20,"谷雨"),(5,5,"立夏"),(5,21,"小满"),(6,5,"芒种"),(6,21,"夏至"),
        (7,7,"小暑"),(7,22,"大暑"),(8,7,"立秋"),(8,23,"处暑"),(9,7,"白露"),(9,23,"秋分"),
        (10,8,"寒露"),(10,23,"霜降"),(11,7,"立冬"),(11,22,"小雪"),(12,7,"大雪"),(12,22,"冬至"),
    ],
    2034: [
        (1,5,"小寒"),(1,20,"大寒"),(2,4,"立春"),(2,19,"雨水"),(3,5,"惊蛰"),(3,20,"春分"),
        (4,5,"清明"),(4,20,"谷雨"),(5,5,"立夏"),(5,21,"小满"),(6,5,"芒种"),(6,21,"夏至"),
        (7,7,"小暑"),(7,22,"大暑"),(8,7,"立秋"),(8,23,"处暑"),(9,7,"白露"),(9,23,"秋分"),
        (10,8,"寒露"),(10,23,"霜降"),(11,7,"立冬"),(11,22,"小雪"),(12,7,"大雪"),(12,22,"冬至"),
    ],
    2035: [
        (1,5,"小寒"),(1,20,"大寒"),(2,4,"立春"),(2,18,"雨水"),(3,5,"惊蛰"),(3,20,"春分"),
        (4,5,"清明"),(4,20,"谷雨"),(5,5,"立夏"),(5,21,"小满"),(6,5,"芒种"),(6,21,"夏至"),
        (7,7,"小暑"),(7,22,"大暑"),(8,7,"立秋"),(8,23,"处暑"),(9,7,"白露"),(9,23,"秋分"),
        (10,8,"寒露"),(10,23,"霜降"),(11,7,"立冬"),(11,22,"小雪"),(12,7,"大雪"),(12,22,"冬至"),
    ],
}

# ========== 中国法定节假日（固定日期） ==========
LEGAL_HOLIDAYS = [
    (1, 1, "元旦"),
    (5, 1, "劳动节"),
    (10, 1, "国庆节"),
    (10, 2, "国庆节"),
    (10, 3, "国庆节"),
]


def lunar_to_solar(year: int, lunar_month: int, lunar_day: int, is_leap: bool = False) -> date:
    """农历转公历（遇到小月无30日时，自动容错降级至29日）"""
    try:
        zh = ZhDate(year, lunar_month, lunar_day, leap_month=is_leap)
        return zh.to_datetime().date()
    except Exception as e:
        if lunar_day == 30:
            try:
                zh = ZhDate(year, lunar_month, 29, leap_month=is_leap)
                return zh.to_datetime().date()
            except Exception:
                pass
        raise e


def solar_to_lunar(d: date) -> dict:
    """公历转农历，返回 {year, month, day, is_leap, month_name, gz_year}"""
    zh = ZhDate.from_datetime(datetime(d.year, d.month, d.day))
    gz = zh.ganzhi_year() if hasattr(zh, 'ganzhi_year') else ""
    return {
        "lunar_year": zh.lunar_year,
        "lunar_month": zh.lunar_month,
        "lunar_day": zh.lunar_day,
        "is_leap": getattr(zh, 'leap_month', False),
        "chinese_str": str(zh),
        "gz_year": gz,
    }


def get_next_lunar_birthday(lunar_month: int, lunar_day: int, is_leap: bool = False,
                            base_date: date = None) -> date:
    """
    给定农历月日，计算下一个生日/纪念日的公历日期
    从 base_date 起算，找到最近的农历(lunar_month, lunar_day)对应的公历日
    """
    if base_date is None:
        base_date = date.today()

    for y in range(base_date.year, base_date.year + 3):
        try:
            solar = lunar_to_solar(y, lunar_month, lunar_day, is_leap)
            if solar >= base_date:
                return solar
        except Exception:
            continue
    return None


def get_solar_terms(year: int) -> list:
    """获取指定年份的24节气列表"""
    return SOLAR_TERMS_2024_2030.get(year, [])


def get_today_solar_term(d: date = None) -> str:
    """获取指定日期的节气（如果有）"""
    if d is None:
        d = date.today()
    terms = get_solar_terms(d.year)
    for (m, day, name) in terms:
        if d.month == m and d.day == day:
            return name
    return None


def get_legal_holidays(year: int) -> list:
    """获取法定节假日列表（仅固定日期，不含调休）"""
    return [(date(year, m, d), name) for (m, d, name) in LEGAL_HOLIDAYS]


# ========== 里程碑计算 ==========
MILESTONE_DAYS = [100, 200, 300, 500, 666, 888, 1000, 2000, 3000, 5000, 10000]

def get_milestones(start_date: date, end_date: date = None) -> list:
    """
    计算从 start_date 到 end_date（默认今天）之间的里程碑
    返回 [(milestone_day, reached_date, is_passed), ...]
    """
    if end_date is None:
        end_date = date.today()
    delta = (end_date - start_date).days
    result = []
    for ms in MILESTONE_DAYS:
        ms_date = start_date + timedelta(days=ms)
        is_passed = ms_date <= end_date
        result.append({
            "milestone": ms,
            "date": ms_date.isoformat(),
            "is_passed": is_passed,
            "days_from_now": (ms_date - end_date).days,
        })
    return result


def get_next_milestone(start_date: date, end_date: date = None) -> dict:
    """获取下一个未到达的里程碑"""
    if end_date is None:
        end_date = date.today()
    for ms in get_milestones(start_date, end_date):
        if not ms["is_passed"]:
            return ms
    return None


# ========== 进度条计算 ==========
def year_progress(d: date = None) -> dict:
    """年度进度"""
    if d is None:
        d = date.today()
    year_start = date(d.year, 1, 1)
    year_end = date(d.year, 12, 31)
    total = (year_end - year_start).days + 1
    passed = (d - year_start).days + 1
    pct = round(passed / total * 100, 1)
    remaining = total - passed
    return {"total": total, "passed": passed, "remaining": remaining, "percent": pct}


def month_progress(d: date = None) -> dict:
    """月度进度"""
    if d is None:
        d = date.today()
    import calendar
    _, last_day = calendar.monthrange(d.year, d.month)
    month_start = date(d.year, d.month, 1)
    month_end = date(d.year, d.month, last_day)
    total = last_day
    passed = d.day
    pct = round(passed / total * 100, 1)
    remaining = total - passed
    return {"total": total, "passed": passed, "remaining": remaining, "percent": pct}


def life_progress(birth_date: date, life_expectancy: int = 80, d: date = None) -> dict:
    """人生进度条"""
    if d is None:
        d = date.today()
    end = date(birth_date.year + life_expectancy, birth_date.month, birth_date.day)
    total_days = (end - birth_date).days
    passed_days = (d - birth_date).days
    if total_days <= 0:
        return {"total": 0, "passed": 0, "remaining": 0, "percent": 100.0}
    pct = round(passed_days / total_days * 100, 1)
    remaining = total_days - passed_days
    return {"total": total_days, "passed": passed_days, "remaining": remaining, "percent": pct}


# ========== 生肖与天干地支 ==========
SHENGXIAO = ["鼠","牛","虎","兔","龙","蛇","马","羊","猴","鸡","狗","猪"]
TIANGAN = ["甲","乙","丙","丁","戊","己","庚","辛","壬","癸"]
DIZHI = ["子","丑","寅","卯","辰","巳","午","未","申","酉","戌","亥"]

def get_shengxiao(year: int) -> str:
    """根据年份获取生肖"""
    return SHENGXIAO[(year - 4) % 12]

def get_ganzhi(year: int) -> str:
    """根据年份获取天干地支"""
    return TIANGAN[(year - 4) % 10] + DIZHI[(year - 4) % 12]


# ========== 工具函数 ==========
def days_until(target: date, base: date = None) -> int:
    """计算距离目标日期还有多少天"""
    if base is None:
        base = date.today()
    return (target - base).days


def days_since(start: date, base: date = None) -> int:
    """计算从起始日期已过去多少天"""
    if base is None:
        base = date.today()
    return (base - start).days


if __name__ == "__main__":
    # 快速测试
    today = date.today()
    print(f"今天: {today}")
    print(f"农历: {solar_to_lunar(today)}")
    print(f"年进度: {year_progress()}")
    print(f"月进度: {month_progress()}")
    print(f"今日节气: {get_today_solar_term()}")
    # 测试农历转公历：2026年农历九月初十
    solar = lunar_to_solar(2026, 9, 10)
    print(f"2026年农历九月初十 = 公历 {solar}")
    print(f"生肖(2026): {get_shengxiao(2026)}")
    print(f"干支(2026): {get_ganzhi(2026)}")