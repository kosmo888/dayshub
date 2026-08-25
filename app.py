"""
DaysHub Flask 主应用 v1.1.0
- Web 页面路由
- RESTful API（带 Token 认证）
- iCal 订阅源
- 事件历史时间线
- 后台定时任务
"""
from flask import Flask, jsonify, request, render_template, Response, g
from functools import wraps
from datetime import date
import json
import os

from config import Config, VERSION
from logger import logger
from models import (
    init_db, create_event, get_event, list_events, update_event, delete_event,
    compute_event, get_dashboard_data, get_today_events, get_upcoming_events,
    export_data, import_data, seed_example_data, CATEGORIES, EVENT_TYPES,
    get_setting, set_setting, get_event_history
)
from calendar_gen import generate_ics
from lunar_engine import (
    solar_to_lunar, lunar_to_solar, year_progress, month_progress,
    get_today_solar_term, get_shengxiao, get_ganzhi,
)


# ========== API 认证装饰器 ==========

def require_auth(f):
    """统一认证 — 所有 API 操作都需要密码"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not Config.auth_enabled():
            return f(*args, **kwargs)
        token = request.headers.get("Authorization", "")
        if token.startswith("Bearer "):
            token = token[7:]
        elif request.args.get("token"):
            token = request.args.get("token")
        from config import get_current_password
        if token == get_current_password():
            return f(*args, **kwargs)
        logger.warning(f"API 认证失败: {request.remote_addr} {request.path}")
        return jsonify({"error": "Unauthorized"}), 401
    return decorated


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(Config)

    # 启动警告
    if not Config.auth_enabled():
        logger.warning("API_TOKEN 未设置 — API 写操作无认证保护！生产环境请务必设置 DAYSHUB_API_TOKEN")
    if Config.SECRET_KEY == "dayshub-dev-key-change-me":
        logger.warning("SECRET_KEY 使用默认值 — 生产环境请修改 DAYSHUB_SECRET_KEY")

    # 初始化数据库
    init_db()

    # 首次加载示例数据
    if Config.SEED_EXAMPLES and get_setting("seeded") != "1":
        seed_example_data()
        set_setting("seeded", "1")

    # ========== 页面路由（无需认证，前端 JS 控制访问） ==========

    @app.route("/")
    def index():
        return render_template("index.html", version=VERSION)

    @app.route("/board")
    def board():
        return render_template("index.html", board_mode=True, version=VERSION)

    # ========== 登录验证 ==========

    @app.route("/api/login", methods=["POST"])
    def api_login():
        from config import get_current_password
        data = request.get_json() or {}
        password = data.get("password", "")
        current = get_current_password()
        if not Config.auth_enabled():
            return jsonify({"ok": True, "token": ""})
        if password == current:
            return jsonify({"ok": True, "token": current})
        logger.warning(f"登录失败: {request.remote_addr}")
        return jsonify({"ok": False, "error": "密码错误"}), 401

    # ========== RESTful API（全部需要认证） ==========

    @app.route("/api/dashboard")
    @require_auth
    def api_dashboard():
        d = request.args.get("date")
        base = date.fromisoformat(d) if d else date.today()
        return jsonify(get_dashboard_data(base))

    @app.route("/api/today")
    @require_auth
    def api_today():
        dash = get_dashboard_data()
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
                 "age": e.get("age")}
                for e in dash["today_events"]
            ],
            "upcoming_7d": [
                {"title": e["title"], "icon": e["icon"], "days_remaining": e.get("days_remaining"),
                 "next_date": e.get("next_date")}
                for e in get_upcoming_events(7)
            ],
            "accumulate": [
                {"title": e["title"], "icon": e["icon"], "days_passed": e.get("days_passed")}
                for e in dash["accumulate"][:5]
            ],
        }
        return jsonify(result)

    @app.route("/api/events")
    @require_auth
    def api_list_events():
        events = list_events(active_only=False)
        return jsonify([compute_event(ev) for ev in events])

    @app.route("/api/events/search")
    @require_auth
    def api_search_events():
        """搜索事件（关键词 + 分类筛选）"""
        q = request.args.get("q", "").strip()
        cat = request.args.get("category", "").strip()
        events = list_events(active_only=False)
        result = []
        for ev in events:
            if q and q.lower() not in ev["title"].lower() and q.lower() not in (ev.get("note") or "").lower():
                continue
            if cat and ev["category"] != cat:
                continue
            result.append(compute_event(ev))
        return jsonify(result)

    @app.route("/api/upcoming")
    @require_auth
    def api_upcoming():
        days = int(request.args.get("days", 7))
        return jsonify(get_upcoming_events(days))

    @app.route("/api/events/<int:eid>/timeline")
    @require_auth
    def api_event_timeline(eid):
        """事件历史时间线"""
        ev = get_event(eid)
        if not ev:
            return jsonify({"error": "事件不存在"}), 404
        history = get_event_history(eid)
        return jsonify({"event": ev, "history": history})

    @app.route("/api/lunar/<date_str>")
    @require_auth
    def api_lunar(date_str):
        d = date.fromisoformat(date_str)
        return jsonify(solar_to_lunar(d))

    @app.route("/api/lunar_to_solar/<int:year>/<int:month>/<int:day>")
    @require_auth
    def api_l2s(year, month, day):
        try:
            solar = lunar_to_solar(year, month, day)
            return jsonify({"date": solar.isoformat()})
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @app.route("/api/progress")
    @require_auth
    def api_progress():
        return jsonify({"year": year_progress(), "month": month_progress()})

    @app.route("/api/categories")
    @require_auth
    def api_categories():
        return jsonify(CATEGORIES)

    @app.route("/api/export")
    @require_auth
    def api_export():
        return jsonify(export_data())

    # ========== RESTful API（写操作需认证） ==========

    @app.route("/api/events", methods=["POST"])
    @require_auth
    def api_create_event():
        data = request.get_json()
        if not data or not data.get("title") or not data.get("date"):
            return jsonify({"error": "title 和 date 为必填"}), 400
        ev = create_event(data)
        logger.info(f"事件创建: {ev['title']} (id={ev['id']})")
        from notifier import send_webhook
        send_webhook("event_created", ev)
        return jsonify(ev), 201

    @app.route("/api/events/<int:eid>", methods=["PUT"])
    @require_auth
    def api_update_event(eid):
        data = request.get_json()
        ev = update_event(eid, data)
        if not ev:
            return jsonify({"error": "事件不存在"}), 404
        logger.info(f"事件更新: {ev['title']} (id={ev['id']})")
        from notifier import send_webhook
        send_webhook("event_updated", ev)
        return jsonify(ev)

    @app.route("/api/events/<int:eid>", methods=["DELETE"])
    @require_auth
    def api_delete_event(eid):
        if delete_event(eid):
            logger.info(f"事件删除: id={eid}")
            from notifier import send_webhook
            send_webhook("event_deleted", {"id": eid})
            return jsonify({"ok": True})
        return jsonify({"error": "事件不存在"}), 404

    @app.route("/api/import", methods=["POST"])
    @require_auth
    def api_import():
        data = request.get_json()
        replace = request.args.get("replace", "false").lower() == "true"
        count = import_data(data, replace)
        logger.info(f"数据导入: {count} 条 (replace={replace})")
        return jsonify({"imported": count})

    @app.route("/api/notify/test", methods=["POST"])
    @require_auth
    def api_notify_test():
        from notifier import test_push
        results = test_push()
        all_ok = all(v for v in results.values() if v is not None)
        msgs = []
        for channel, status in results.items():
            if status is True:
                msgs.append(f"✅ {channel}: 成功")
            elif status is False:
                msgs.append(f"❌ {channel}: 失败")
            # None = 未配置，不显示
        if not msgs:
            return jsonify({"ok": False, "msg": "未配置任何推送通道，请先在推送设置中配置"})
        if all_ok:
            return jsonify({"ok": True, "msg": "\n".join(msgs)})
        return jsonify({"ok": False, "msg": "\n".join(msgs)}), 500

    @app.route("/api/notify/check", methods=["POST"])
    @require_auth
    def api_notify_check():
        from notifier import check_and_notify
        check_and_notify()
        return jsonify({"ok": True, "msg": "提醒检查完成"})

    # ========== 推送设置 ==========

    @app.route("/api/settings/push", methods=["GET"])
    @require_auth
    def api_get_push_settings():
        from config import load_push_config
        cfg = load_push_config()
        safe = dict(cfg)
        if safe.get("smtp_pass"):
            safe["smtp_pass"] = "******"
        return jsonify(safe)

    @app.route("/api/settings/push", methods=["PUT"])
    @require_auth
    def api_save_push_settings():
        from config import save_push_config, load_push_config
        data = request.get_json() or {}
        if data.get("smtp_pass") == "******":
            data.pop("smtp_pass")
        save_push_config(data)
        new_cfg = load_push_config()
        safe = dict(new_cfg)
        if safe.get("smtp_pass"):
            safe["smtp_pass"] = "******"
        return jsonify({"ok": True, "config": safe})

    # ========== 密码修改 ==========

    @app.route("/api/settings/password", methods=["PUT"])
    @require_auth
    def api_change_password():
        from config import change_password
        data = request.get_json() or {}
        old_pass = data.get("old_password", "")
        new_pass = data.get("new_password", "")
        if not old_pass or not new_pass:
            return jsonify({"ok": False, "error": "旧密码和新密码不能为空"}), 400
        if len(new_pass) < 4:
            return jsonify({"ok": False, "error": "新密码至少4位"}), 400
        if change_password(old_pass, new_pass):
            return jsonify({"ok": True, "msg": "密码修改成功"})
        return jsonify({"ok": False, "error": "旧密码错误"}), 401

    # ========== iCal 订阅 ==========

    @app.route("/api/calendar.ics")
    @require_auth
    def api_ics():
        ics = generate_ics()
        return Response(ics, mimetype="text/calendar", headers={
            "Content-Disposition": "attachment; filename=dayshub.ics",
            "Cache-Control": "max-age=3600",
        })

    # ========== 健康检查 ==========

    @app.route("/health")
    def health():
        return jsonify({"status": "ok", "app": "DaysHub", "version": VERSION})

    # ========== 启动定时任务 ==========

    from scheduler import create_scheduler
    create_scheduler(app)

    logger.info(f"DaysHub v{VERSION} 启动完成 — 端口 {os.environ.get('DAYSHUB_PORT', '5217')}")
    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("DAYSHUB_PORT", "5217"))
    app.run(host="0.0.0.0", port=port, debug=False)