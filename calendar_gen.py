"""
DaysHub iCal 日历生成器
- 将所有事件转为 iCalendar (.ics) 格式
- 农历循环事件自动展开为未来 3 年的公历日期
- 支持 Google Calendar / Apple Calendar 订阅
"""
from datetime import date, timedelta
from models import list_events, CATEGORIES
from lunar_engine import get_next_lunar_birthday, lunar_to_solar
from config import Config


def generate_ics(years_ahead: int = 3, user_id: int | None = None) -> str:
    """
    生成完整的 iCalendar 字符串
    - 支持按用户隔离只导出自己的日历事件
    - 循环事件展开为未来 years_ahead 年
    - 倒数日和累计日各生成一个事件
    """
    events = list_events(user_id=user_id)
    today = date.today()
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//DaysHub//Time Dashboard//CN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:DaysHub 时光看板",
        "X-WR-TIMEZONE:Asia/Shanghai",
    ]

    for ev in events:
        title = ev["title"]
        cat_info = CATEGORIES.get(ev["category"], CATEGORIES["other"])
        color = ev["color"] or cat_info["color"]
        icon = ev["icon"] or cat_info["icon"]
        note = ev["note"] or ""
        ev_date = date.fromisoformat(ev["date"])

        if ev["event_type"] == "monthly":
            # 每月重复事件：展开未来 12 个月
            import calendar
            for m_offset in range(12):
                y = today.year + (today.month - 1 + m_offset) // 12
                m = (today.month - 1 + m_offset) % 12 + 1
                _, max_d = calendar.monthrange(y, m)
                d = date(y, m, min(ev_date.day, max_d))
                summary = f"{icon} {title}"
                desc = f"每月重复日（每逢 {ev_date.day} 日）"
                if note:
                    desc += f"\\n备注: {note}"
                lines.extend(_make_vevent(d, summary, desc, f"{ev['id']}_{y}_{m}"))

        elif ev["event_type"] == "recurring" or ev["is_recurring"]:
            # 循环事件：展开未来 N 年
            if ev["lunar_month"] and ev["lunar_day"]:
                # 农历循环
                for y in range(today.year, today.year + years_ahead):
                    try:
                        solar = lunar_to_solar(y, ev["lunar_month"], ev["lunar_day"], bool(ev["is_leap"]))
                        if solar >= today - timedelta(days=365):
                            age = y - ev_date.year
                            summary = f"{icon} {title}" + (f"（{age}岁）" if age > 0 and ev["category"] == "family" else f"（第{age}年）")
                            desc = f"农历{ev['lunar_month']}月{ev['lunar_day']}日"
                            if note:
                                desc += f"\\n备注: {note}"
                            lines.extend(_make_vevent(solar, summary, desc, ev["id"]))
                    except Exception:
                        continue
            else:
                # 公历循环
                for y in range(today.year, today.year + years_ahead):
                    try:
                        d = date(y, ev_date.month, ev_date.day)
                        if d >= today - timedelta(days=365):
                            age = y - ev_date.year
                            summary = f"{icon} {title}" + (f"（第{age}年）" if age > 0 else "")
                            desc = note if note else f"每年{ev_date.month}月{ev_date.day}日"
                            lines.extend(_make_vevent(d, summary, desc, ev["id"]))
                    except ValueError:
                        continue

        elif ev["event_type"] == "accumulate":
            # 累计日：生成起始事件 + 里程碑事件
            summary = f"{icon} {title}（起始日）"
            desc = f"起始日期: {ev_date.isoformat()}"
            if note:
                desc += f"\\n{note}"
            lines.extend(_make_vevent(ev_date, summary, desc, ev["id"]))

            # 里程碑
            from lunar_engine import MILESTONE_DAYS
            for ms in MILESTONE_DAYS:
                ms_date = ev_date + timedelta(days=ms)
                if ms_date >= today - timedelta(days=30):
                    ms_summary = f"{icon} {title} · {ms}天"
                    ms_desc = f"从 {ev_date} 起，已满 {ms} 天"
                    lines.extend(_make_vevent(ms_date, ms_summary, ms_desc, ev["id"] * 1000 + ms))

        else:
            # 普通倒数日
            summary = f"{icon} {title}"
            desc = note if note else ""
            lines.extend(_make_vevent(ev_date, summary, desc, ev["id"]))

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


def _make_vevent(d: date, summary: str, desc: str, uid: int) -> list:
    """生成单个 VEVENT"""
    dtstr = d.strftime("%Y%m%d")
    return [
        "BEGIN:VEVENT",
        f"UID:{uid}@dayshub",
        f"DTSTAMP:{date.today().strftime('%Y%m%d')}T000000Z",
        f"DTSTART;VALUE=DATE:{dtstr}",
        f"DTEND;VALUE=DATE:{dtstr}",
        f"SUMMARY:{_escape_ics(summary)}",
        f"DESCRIPTION:{_escape_ics(desc)}",
        "STATUS:CONFIRMED",
        "TRANSP:TRANSPARENT",
        "BEGIN:VALARM",
        "TRIGGER:-P1D",
        "ACTION:DISPLAY",
        f"DESCRIPTION:{_escape_ics(summary)}",
        "END:VALARM",
        "END:VEVENT",
    ]


def _escape_ics(text: str) -> str:
    """转义 iCal 特殊字符"""
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


if __name__ == "__main__":
    ics = generate_ics()
    print(f"生成 {len(ics)} 字符的 iCal 日历")
    print("\n".join(ics.split("\r\n")[:30]))