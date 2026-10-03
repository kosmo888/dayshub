"""
DaysHub 桌面小组件与看板数据聚合蓝图 v2.0.0
- 专属极简小组件接口 (/api/widget/summary)，适配 iOS Scriptable / Widgy / Android 挂件
- 看板主页聚合数据 (/api/dashboard)、今日信息 (/api/today) 与时间进度 (/api/progress)
- 农历公历双向精确换算 (/api/lunar, /api/lunar_to_solar)
"""
from datetime import date
from flask import Blueprint, request, jsonify, g
from auth_middleware import require_auth
from models import get_dashboard_data, list_events, compute_event
from lunar_engine import (
    solar_to_lunar, lunar_to_solar, year_progress, month_progress
)

widget_bp = Blueprint("widget", __name__)


@widget_bp.route("/api/dashboard", methods=["GET"])
@require_auth
def api_dashboard():
    """获取看板主页聚合数据"""
    d = request.args.get("date")
    base = date.fromisoformat(d) if d else date.today()
    user = getattr(g, "current_user", None)
    uid = user["id"] if user and user.get("role") != "admin" else None
    return jsonify(get_dashboard_data(base, user_id=uid))


@widget_bp.route("/api/today", methods=["GET"])
@require_auth
def api_today():
    """获取今日关键数据"""
    user = getattr(g, "current_user", None)
    uid = user["id"] if user and user.get("role") != "admin" else None
    dash = get_dashboard_data(user_id=uid)
    result = {
        "date": dash["date"],
        "lunar": dash["lunar"]["chinese_str"],
        "shengxiao": dash["shengxiao"],
        "ganzhi": dash["ganzhi"],
        "solar_term": dash["solar_term"],
        "year_progress": dash["year_progress"],
        "month_progress": dash["month_progress"],
        "today_events": [
            {"title": e["title"], "icon": e["icon"], "note": e["note"],
             "category": e["category"], "age": e.get("age")}
            for e in dash["today_events"]
        ]
    }
    return jsonify(result)


@widget_bp.route("/api/progress", methods=["GET"])
@require_auth
def api_progress():
    """获取年度与月度时间流逝进度"""
    return jsonify({"year": year_progress(), "month": month_progress()})


@widget_bp.route("/api/lunar/<date_str>", methods=["GET"])
@require_auth
def api_lunar(date_str):
    """公历转农历"""
    try:
        d = date.fromisoformat(date_str)
        return jsonify(solar_to_lunar(d))
    except Exception as e:
        return jsonify({"error": f"无效日期格式: {e}"}), 400


@widget_bp.route("/api/lunar_to_solar/<int:year>/<int:month>/<int:day>", methods=["GET"])
@require_auth
def api_l2s(year, month, day):
    """农历转公历（支持 ?is_leap=1 闰月精准转换）"""
    try:
        is_leap = request.args.get("is_leap", "0") in ("1", "true", "True")
        solar = lunar_to_solar(year, month, day, is_leap=is_leap)
        return jsonify({"date": solar.isoformat()})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@widget_bp.route("/api/widget/summary", methods=["GET"])
@require_auth
def api_widget_summary():
    """专为桌面小组件 (iOS Scriptable, Widgy, Android) 打造的极简一站式 JSON 接口"""
    user = getattr(g, "current_user", None)
    uid = user["id"] if user and user.get("role") != "admin" else None
    base_date = date.today()
    dash = get_dashboard_data(base_date=base_date, user_id=uid)

    today_evs = [
        {
            "id": e["id"],
            "title": e["title"],
            "icon": e.get("icon") or "📅",
            "category": e.get("category", "other"),
            "note": e.get("note", ""),
            "age": e.get("age"),
            "event_type": e.get("event_type")
        }
        for e in dash.get("today_events", [])
    ]

    all_evs = dash.get("all_events", [])
    valid_upcoming = [
        e for e in all_evs
        if e.get("event_type") != "accumulate" and not e.get("is_today") and (e.get("days_remaining") is not None and e.get("days_remaining") >= 0)
    ]
    # 置顶优先，距离今天最近优先
    valid_upcoming.sort(key=lambda x: (not x.get("is_pinned"), 9999 if x.get("days_remaining") is None else x["days_remaining"]))

    next_ev = None
    if valid_upcoming:
        ne = valid_upcoming[0]
        next_ev = {
            "id": ne["id"],
            "title": ne["title"],
            "days": ne.get("days_remaining"),
            "direction": "countdown",
            "date": ne.get("next_date") or ne.get("date"),
            "sub": ne.get("lunar_str") or ne.get("note") or "",
            "icon": ne.get("icon") or "⏳",
            "category": ne.get("category", "other"),
            "is_pinned": bool(ne.get("is_pinned"))
        }

    top_list = []
    for e in valid_upcoming[:5]:
        top_list.append({
            "id": e["id"],
            "title": e["title"],
            "days": e.get("days_remaining"),
            "direction": "countdown",
            "date": e.get("next_date") or e.get("date"),
            "sub": e.get("lunar_str") or e.get("note") or "",
            "icon": e.get("icon") or "⏳",
            "category": e.get("category", "other"),
            "is_pinned": bool(e.get("is_pinned"))
        })

    accum_list = [e for e in all_evs if e.get("event_type") == "accumulate" and not e.get("is_today")]
    accum_list.sort(key=lambda x: (not x.get("is_pinned"), -(0 if x.get("days_passed") is None else x["days_passed"])))
    accum_top = None
    if accum_list:
        ae = accum_list[0]
        accum_top = {
            "id": ae["id"],
            "title": ae["title"],
            "days_passed": ae.get("days_passed"),
            "icon": ae.get("icon") or "💝",
            "category": ae.get("category", "other"),
            "is_pinned": bool(ae.get("is_pinned"))
        }

    res = {
        "ok": True,
        "date": dash["date"],
        "weekday": ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][base_date.weekday()],
        "lunar": dash["lunar"]["chinese_str"],
        "shengxiao": dash["shengxiao"],
        "ganzhi": dash["ganzhi"],
        "solar_term": dash["solar_term"],
        "progress": {
            "year_percent": dash["year_progress"]["percent"],
            "year_remaining_days": dash["year_progress"]["remaining"],
            "month_percent": dash["month_progress"]["percent"],
            "month_remaining_days": dash["month_progress"]["remaining"]
        },
        "today_count": len(today_evs),
        "today_events": today_evs,
        "next_event": next_ev,
        "top_events": top_list,
        "accumulate_highlight": accum_top,
        "user": {
            "username": user.get("username", "admin") if user else "admin",
            "display_name": user.get("display_name", "") if user else ""
        }
    }
    return jsonify(res)
