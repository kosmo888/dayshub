"""
DaysHub Flask 主应用 v1.1.0
- Web 页面路由
- RESTful API（带 Token 认证）
- iCal 订阅源
- 事件历史时间线
- 后台定时任务
"""
from flask import Flask, jsonify, request, render_template, Response, g, send_from_directory
from functools import wraps
from datetime import date, datetime
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
    """统一认证 — 支持多用户 User Token 及管理员 API Token"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not Config.auth_enabled():
            g.current_user = {"id": 1, "username": "admin", "role": "admin", "display_name": "管理员"}
            return f(*args, **kwargs)
        token = request.headers.get("Authorization", "")
        if token.startswith("Bearer "):
            token = token[7:]
        elif request.args.get("token"):
            token = request.args.get("token") or ""

        token = str(token).strip()
        if not token:
            return jsonify({"error": "Unauthorized"}), 401

        # 1. 验证用户颁发的 Token
        from models import verify_user_token
        user = verify_user_token(token)
        if user:
            g.current_user = user
            return f(*args, **kwargs)

        # 2. 兼容全局 API_TOKEN / 管理员密码直通
        from config import get_current_password
        import hmac
        current_pass = str(get_current_password())
        if hmac.compare_digest(token, current_pass):
            from models import get_user_by_username
            admin_user = get_user_by_username("admin") or {"id": 1, "username": "admin", "role": "admin", "display_name": "管理员"}
            g.current_user = admin_user
            return f(*args, **kwargs)

        logger.warning(f"API 认证失败: {request.remote_addr} {request.path}")
        return jsonify({"error": "Unauthorized"}), 401
    return decorated


def require_admin(f):
    """管理员专用权限拦截器"""
    @wraps(f)
    @require_auth
    def decorated(*args, **kwargs):
        user = getattr(g, "current_user", None)
        if not user or user.get("role") != "admin":
            return jsonify({"ok": False, "error": "需要管理员权限"}), 403
        return f(*args, **kwargs)
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

    @app.after_request
    def add_header(response):
        # 禁用 HTML / 静态资源浏览器强制缓存，确保版本更新即时呈现
        if "text/html" in response.headers.get("Content-Type", "") or "javascript" in response.headers.get("Content-Type", "") or "css" in response.headers.get("Content-Type", ""):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

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

    # ========== 注册与登录验证（带防爆破频控） ==========

    def _get_client_ip():
        xff = request.headers.get("X-Forwarded-For") or request.environ.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0].strip()
        xri = request.headers.get("X-Real-IP") or request.environ.get("HTTP_X_REAL_IP")
        if xri:
            return xri.strip()
        return request.remote_addr or "unknown"

    def _log(action: str, module: str = "system", details: str = "", status: str = "ok", user=None):
        try:
            from models import log_system_action
            u = user or getattr(g, "current_user", None)
            uid = u["id"] if u and isinstance(u, dict) and "id" in u else None
            uname = u["username"] if u and isinstance(u, dict) and "username" in u else ""
            ip = _get_client_ip()
            ua = request.headers.get("User-Agent", "")
            log_system_action(user_id=uid, username=uname, action=action, module=module,
                              details=details, ip=ip, user_agent=ua, status=status)
        except Exception as e:
            logger.warning(f"记录操作日志失败: {e}")

    @app.route("/api/system/public-info", methods=["GET"])
    def api_public_info():
        """获取公开系统配置（如是否开放注册）"""
        from config import is_registration_allowed
        return jsonify({
            "ok": True,
            "allow_registration": is_registration_allowed(),
            "version": VERSION
        })

    @app.route("/api/register", methods=["POST"])
    def api_register():
        """用户注册接口"""
        from config import is_registration_allowed, check_login_rate_limit, record_login_failure
        from models import get_user_by_username, create_user, create_user_token
        import re

        client_ip = _get_client_ip()

        # 1. 检查注册开关
        if not is_registration_allowed():
            return jsonify({"ok": False, "error": "管理员已关闭新用户自主注册"}), 403

        # 2. 频控检查
        allowed, remaining_sec = check_login_rate_limit(client_ip)
        if not allowed:
            mins = max(1, (remaining_sec + 59) // 60)
            return jsonify({"ok": False, "error": f"操作过于频繁，请 {mins} 分钟后再试"}), 429

        data = request.get_json() or {}
        username = str(data.get("username", "")).strip()
        password = str(data.get("password", ""))
        display_name = str(data.get("display_name", "")).strip()

        # 3. 校验参数
        if not username or not password:
            return jsonify({"ok": False, "error": "用户名和密码不能为空"}), 400
        if len(username) < 2 or len(username) > 30:
            return jsonify({"ok": False, "error": "用户名长度需在 2 到 30 个字符之间"}), 400
        if not re.match(r'^[a-zA-Z0-9_\u4e00-\u9fa5]+$', username):
            return jsonify({"ok": False, "error": "用户名仅支持中英文、数字和下划线"}), 400
        if len(password) < 4:
            return jsonify({"ok": False, "error": "密码长度至少 4 位"}), 400
        if get_user_by_username(username):
            return jsonify({"ok": False, "error": "该用户名已被注册，请更换"}), 400

        # 4. 创建用户并颁发 Token
        user = create_user(username, password, role="user", display_name=display_name)
        if not user:
            _log("register", "auth", f"用户注册失败(数据库错误): {username}", status="fail")
            return jsonify({"ok": False, "error": "注册失败，请稍后重试"}), 500

        token = create_user_token(user["id"])
        logger.info(f"新用户注册成功: {username} (IP: {client_ip})")
        _log("register", "auth", f"新用户注册成功: {username} ({display_name})", user=user)

        return jsonify({
            "ok": True,
            "token": token,
            "user": {
                "id": user["id"],
                "username": user["username"],
                "role": user["role"],
                "display_name": user["display_name"]
            },
            "msg": "注册成功！"
        }), 201

    @app.route("/api/login", methods=["POST"])
    def api_login():
        from config import (
            get_current_password, check_login_rate_limit,
            record_login_failure, reset_login_failure
        )
        from models import get_user_by_username, verify_password, create_user_token
        import hmac

        client_ip = _get_client_ip()

        # 检查是否处于锁定状态
        allowed, remaining_sec = check_login_rate_limit(client_ip)
        if not allowed:
            mins = max(1, (remaining_sec + 59) // 60)
            logger.warning(f"登录被频控拦截: {client_ip}, 剩余锁定时间 {remaining_sec}s")
            _log("login", "auth", f"登录拦截(频控锁定): {client_ip}", status="fail")
            return jsonify({
                "ok": False,
                "error": f"连续登录失败次数过多，已被锁定，请 {mins} 分钟后再试"
            }), 429

        data = request.get_json() or {}
        username = str(data.get("username", "")).strip()
        password = str(data.get("password", ""))

        if not Config.auth_enabled():
            return jsonify({
                "ok": True, "token": "",
                "user": {"username": "admin", "role": "admin", "display_name": "管理员"}
            })

        # 1. 尝试账号 + 密码登录
        if username:
            user = get_user_by_username(username)
            if user and user.get("is_active"):
                if verify_password(password, user["password_hash"]):
                    reset_login_failure(client_ip)
                    token = create_user_token(user["id"])
                    _log("login", "auth", f"用户登录成功: {username}", user=user)
                    return jsonify({
                        "ok": True,
                        "token": token,
                        "user": {
                            "id": user["id"],
                            "username": user["username"],
                            "role": user["role"],
                            "display_name": user["display_name"]
                        }
                    })

        # 2. 兼容单密码快捷登录（直接匹配 admin 密码 / 全局 API_TOKEN）
        current_admin_pass = str(get_current_password())
        if hmac.compare_digest(password, current_admin_pass):
            reset_login_failure(client_ip)
            admin_user = get_user_by_username("admin")
            token = create_user_token(admin_user["id"]) if admin_user else current_admin_pass
            admin_info = {
                "id": admin_user["id"] if admin_user else 1,
                "username": "admin",
                "role": "admin",
                "display_name": "管理员"
            }
            _log("login", "auth", "管理员通过独立密码登录成功", user=admin_info)
            return jsonify({
                "ok": True,
                "token": token,
                "user": admin_info
            })

        is_locked, lock_sec = record_login_failure(client_ip)
        logger.warning(f"登录失败: {client_ip} (用户: {username or 'admin'})")
        _log("login", "auth", f"密码验证失败 (用户: {username or 'admin'})", status="fail")
        if is_locked:
            mins = max(1, (lock_sec + 59) // 60)
            return jsonify({
                "ok": False,
                "error": f"账号或密码错误。连续失败已被锁定 {mins} 分钟"
            }), 429
        return jsonify({"ok": False, "error": "用户名或密码错误"}), 401

    @app.route("/api/logout", methods=["POST"])
    def api_logout():
        _log("logout", "auth", "用户退出登录")
        return jsonify({"ok": True, "msg": "已安全退出"})


    # ========== 用户与后台管理 API ==========

    @app.route("/api/user/profile", methods=["GET"])
    @require_auth
    def api_user_profile():
        user = getattr(g, "current_user", None)
        return jsonify({"ok": True, "user": user})

    @app.route("/api/admin/users", methods=["GET"])
    @require_admin
    def api_admin_list_users():
        from models import list_users
        return jsonify({"ok": True, "users": list_users()})

    @app.route("/api/admin/users", methods=["POST"])
    @require_admin
    def api_admin_create_user():
        from models import create_user, get_user_by_username
        data = request.get_json() or {}
        username = str(data.get("username", "")).strip()
        password = str(data.get("password", ""))
        role = str(data.get("role", "user")).strip()
        display_name = str(data.get("display_name", "")).strip()

        if not username or not password:
            return jsonify({"ok": False, "error": "用户名和密码不能为空"}), 400
        if len(password) < 4:
            return jsonify({"ok": False, "error": "密码长度至少 4 位"}), 400
        if get_user_by_username(username):
            return jsonify({"ok": False, "error": "该用户名已存在"}), 400

        user = create_user(username, password, role, display_name)
        _log("user_create", "user", f"创建用户: {username} (角色: {role}, 昵称: {display_name})")
        return jsonify({"ok": True, "user": user, "msg": "用户创建成功"}), 201

    @app.route("/api/admin/users/<int:uid>", methods=["PUT"])
    @require_admin
    def api_admin_update_user(uid):
        from models import update_user, get_user_by_id
        user = get_user_by_id(uid)
        if not user:
            return jsonify({"ok": False, "error": "用户不存在"}), 404
        data = request.get_json() or {}
        updated = update_user(uid, data)
        _log("user_update", "user", f"更新用户信息: {user['username']} (ID: {uid})")
        return jsonify({"ok": True, "user": updated, "msg": "用户信息已更新"})

    @app.route("/api/admin/users/<int:uid>", methods=["DELETE"])
    @require_admin
    def api_admin_delete_user(uid):
        from models import delete_user, get_user_by_id
        user = get_user_by_id(uid)
        if not user:
            return jsonify({"ok": False, "error": "用户不存在"}), 404
        if user["username"] == "admin":
            return jsonify({"ok": False, "error": "初始管理员账号不能删除"}), 400
        if delete_user(uid):
            _log("user_delete", "user", f"删除用户: {user['username']} (ID: {uid})")
            return jsonify({"ok": True, "msg": "用户已删除"})
        return jsonify({"ok": False, "error": "删除失败"}), 500

    @app.route("/api/admin/system", methods=["GET"])
    @require_admin
    def api_admin_get_system():
        from config import is_registration_allowed
        return jsonify({
            "ok": True,
            "allow_registration": is_registration_allowed()
        })

    @app.route("/api/admin/system", methods=["PUT"])
    @require_admin
    def api_admin_save_system():
        from config import set_registration_allowed, is_registration_allowed
        data = request.get_json() or {}
        if "allow_registration" in data:
            set_registration_allowed(bool(data["allow_registration"]))
        _log("system_config", "system", f"修改系统配置: 允许注册={is_registration_allowed()}")
        return jsonify({
            "ok": True,
            "allow_registration": is_registration_allowed(),
            "msg": "系统设置已更新"
        })

    @app.route("/api/admin/logs", methods=["GET"])
    @require_admin
    def api_admin_list_logs():
        from models import list_system_logs
        user_id_param = request.args.get("user_id")
        try:
            target_user_id = int(user_id_param) if user_id_param else None
        except (ValueError, TypeError):
            target_user_id = None
        module = request.args.get("module") or None
        action = request.args.get("action") or None
        keyword = request.args.get("keyword") or None
        try:
            limit = int(request.args.get("limit", 50))
        except (ValueError, TypeError):
            limit = 50
        try:
            offset = int(request.args.get("offset", 0))
        except (ValueError, TypeError):
            offset = 0

        res = list_system_logs(user_id=target_user_id, module=module, action=action, keyword=keyword, limit=limit, offset=offset)
        return jsonify({
            "ok": True,
            "total": res["total"],
            "logs": res["logs"],
            "limit": limit,
            "offset": offset
        })

    @app.route("/api/user/logs", methods=["GET"])
    @require_auth
    def api_user_list_logs():
        """普通用户查看自己的个人操作审计日志"""
        from models import list_system_logs
        user = getattr(g, "current_user", None)
        uid = user["id"] if user and isinstance(user, dict) else None
        if not uid:
            return jsonify({"ok": False, "error": "无法获取当前用户信息"}), 401
        module = request.args.get("module") or None
        action = request.args.get("action") or None
        keyword = request.args.get("keyword") or None
        try:
            limit = int(request.args.get("limit", 50))
        except (ValueError, TypeError):
            limit = 50
        try:
            offset = int(request.args.get("offset", 0))
        except (ValueError, TypeError):
            offset = 0

        res = list_system_logs(user_id=uid, module=module, action=action, keyword=keyword, limit=limit, offset=offset)
        return jsonify({
            "ok": True,
            "total": res["total"],
            "logs": res["logs"],
            "limit": limit,
            "offset": offset
        })

    @app.route("/api/admin/runtime_logs", methods=["GET"])
    @require_admin
    def api_admin_runtime_logs():
        """获取后端服务实时运行日志 (dayshub.log) 最新 N 行"""
        import os
        from config import Config
        try:
            lines_count = int(request.args.get("lines", 100))
        except (ValueError, TypeError):
            lines_count = 100
        lines_count = max(10, min(lines_count, 1000))

        log_path = os.path.join(Config.DATA_DIR, "dayshub.log")
        if not os.path.exists(log_path):
            return jsonify({
                "ok": True,
                "lines": ["(暂无日志文件或日志服务尚未写入)"],
                "total_lines": 0,
                "file_size": 0,
                "path": log_path
            })

        try:
            file_size = os.path.getsize(log_path)
            lines = []
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                if file_size < 2 * 1024 * 1024:
                    all_lines = f.readlines()
                    lines = [ln.rstrip("\r\n") for ln in all_lines[-lines_count:]]
                else:
                    f.seek(max(0, file_size - 100 * 1024))
                    all_lines = f.readlines()
                    lines = [ln.rstrip("\r\n") for ln in all_lines[-lines_count:]]

            return jsonify({
                "ok": True,
                "lines": lines,
                "returned_count": len(lines),
                "file_size": file_size,
                "path": log_path
            })
        except Exception as e:
            return jsonify({"ok": False, "error": f"读取运行日志失败: {e}"}), 500

    @app.route("/api/admin/logs", methods=["DELETE"])
    @require_admin
    def api_admin_clear_logs():
        from models import clear_system_logs
        data = request.get_json(silent=True) or {}
        days = data.get("days_to_keep")
        try:
            days = int(days) if days is not None else None
        except (ValueError, TypeError):
            days = None
        count = clear_system_logs(days_to_keep=days)
        _log("clear_logs", "system", f"清理系统日志: 共清除 {count} 条 (保留天数: {days if days else '全部'})")
        return jsonify({"ok": True, "deleted_count": count, "msg": f"已成功清理 {count} 条日志"})


    # ========== RESTful API（全部需要认证） ==========

    @app.route("/api/dashboard")
    @require_auth
    def api_dashboard():
        d = request.args.get("date")
        base = date.fromisoformat(d) if d else date.today()
        user = getattr(g, "current_user", None)
        uid = user["id"] if user and user.get("role") != "admin" else None
        return jsonify(get_dashboard_data(base, user_id=uid))

    @app.route("/api/today")
    @require_auth
    def api_today():
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
                 "age": e.get("age")}
                for e in dash["today_events"]
            ],
            "upcoming_7d": [
                {"title": e["title"], "icon": e["icon"], "days_remaining": e.get("days_remaining"),
                 "next_date": e.get("next_date")}
                for e in get_upcoming_events(7, user_id=uid)
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
        user = getattr(g, "current_user", None)
        uid = user["id"] if user and user.get("role") != "admin" else None
        events = list_events(active_only=False, user_id=uid)
        return jsonify([compute_event(ev) for ev in events])

    @app.route("/api/events/search")
    @require_auth
    def api_search_events():
        """搜索事件（关键词 + 分类筛选）"""
        q = request.args.get("q", "").strip()
        cat = request.args.get("category", "").strip()
        user = getattr(g, "current_user", None)
        uid = user["id"] if user and user.get("role") != "admin" else None
        events = list_events(active_only=False, user_id=uid)
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
    @app.route("/api/events/<int:eid>/history")
    @require_auth
    def api_event_timeline(eid):
        """事件历史时间线与里程碑"""
        ev = get_event(eid)
        if not ev:
            return jsonify({"error": "事件不存在"}), 404
        history = get_event_history(eid)
        milestones = ev.get("milestones", [])
        return jsonify({"event": ev, "history": history, "milestones": milestones})

    @app.route("/api/lunar/<date_str>")
    @require_auth
    def api_lunar(date_str):
        d = date.fromisoformat(date_str)
        return jsonify(solar_to_lunar(d))

    @app.route("/api/lunar_to_solar/<int:year>/<int:month>/<int:day>")
    @require_auth
    def api_l2s(year, month, day):
        try:
            is_leap = request.args.get("is_leap", "0") in ("1", "true", "True")
            solar = lunar_to_solar(year, month, day, is_leap=is_leap)
            return jsonify({"date": solar.isoformat()})
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @app.route("/api/widget/summary")
    @require_auth
    def api_widget_summary():
        """专属极简小组件接口 (适配 iOS Scriptable / Widgy / 桌面卡片)"""
        user = getattr(g, "current_user", None)
        uid = user["id"] if user and user.get("role") != "admin" else None
        base = date.today()
        dash = get_dashboard_data(base, user_id=uid)

        weekday_map = ["一", "二", "三", "四", "五", "六", "日"]
        weekday_str = f"星期{weekday_map[base.weekday()]}"

        today_evs = [
            {"id": e["id"], "title": e["title"], "icon": e.get("icon") or "🎉", "note": e.get("note", ""), "category": e.get("category")}
            for e in dash.get("today_events", [])
        ]

        upcoming = dash.get("countdown", []) + dash.get("recurring", [])
        valid_upcoming = [e for e in upcoming if e.get("days_remaining") is not None and e.get("days_remaining") >= 0]
        valid_upcoming.sort(key=lambda x: (not x.get("is_pinned"), 9999 if x.get("days_remaining") is None else x["days_remaining"]))

        next_ev = None
        if valid_upcoming:
            ne = valid_upcoming[0]
            next_ev = {
                "id": ne["id"],
                "title": ne["title"],
                "days": ne.get("days_remaining"),
                "direction": "countdown",
                "sub": ne.get("lunar_str") or ne.get("next_date") or ne.get("date"),
                "date": ne.get("next_date") or ne.get("date"),
                "icon": ne.get("icon") or "⏳",
                "category": ne.get("category"),
                "is_pinned": bool(ne.get("is_pinned"))
            }

        top_list = []
        for e in valid_upcoming[:5]:
            top_list.append({
                "id": e["id"],
                "title": e["title"],
                "days": e.get("days_remaining"),
                "direction": "countdown",
                "sub": e.get("lunar_str") or e.get("next_date") or e.get("date"),
                "icon": e.get("icon") or "⏳",
                "is_pinned": bool(e.get("is_pinned"))
            })

        accumulate_list = dash.get("accumulate", [])
        accum_top = None
        if accumulate_list:
            ae = accumulate_list[0]
            accum_top = {
                "id": ae["id"],
                "title": ae["title"],
                "days_passed": ae.get("days_passed", 0),
                "next_milestone": ae.get("next_milestone"),
                "icon": ae.get("icon") or "📈"
            }

        res = {
            "ok": True,
            "date": base.isoformat(),
            "weekday": weekday_str,
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
        user = getattr(g, "current_user", None)
        uid = user["id"] if user and user.get("role") != "admin" else None
        res_data = export_data(user_id=uid)
        _log("export", "event", f"导出数据备份: 共 {len(res_data.get('events', []))} 条事件")
        return jsonify(res_data)

    # ========== RESTful API（写操作需认证） ==========

    @app.route("/api/events", methods=["POST"])
    @require_auth
    def api_create_event():
        data = request.get_json()
        if not data or not data.get("title") or not data.get("date"):
            return jsonify({"error": "title 和 date 为必填"}), 400
        cur_user = getattr(g, "current_user", None)
        uid = cur_user["id"] if cur_user else 1
        ev = create_event(data, user_id=uid)
        if not ev:
            return jsonify({"error": "创建失败"}), 500
        logger.info(f"事件创建: {ev['title']} (id={ev['id']})")
        _log("event_create", "event", f"创建事件: {ev['title']} (ID: {ev['id']})")
        from notifier import send_webhook
        send_webhook("event_created", ev)
        return jsonify(ev), 201

    @app.route("/api/events/<int:eid>", methods=["PUT"])
    @require_auth
    def api_update_event(eid):
        data = request.get_json()
        ev_existing = get_event(eid)
        if not ev_existing:
            return jsonify({"error": "事件不存在"}), 404
        user = getattr(g, "current_user", None)
        if user and user.get("role") != "admin":
            if ev_existing.get("user_id") is not None and ev_existing.get("user_id") != user.get("id"):
                return jsonify({"error": "无权修改其他用户的事件"}), 403
        ev = update_event(eid, data)
        if not ev:
            return jsonify({"error": "更新失败"}), 500
        logger.info(f"事件更新: {ev['title']} (id={ev['id']})")
        _log("event_update", "event", f"更新事件: {ev['title']} (ID: {ev['id']})")
        from notifier import send_webhook
        send_webhook("event_updated", ev)
        return jsonify(ev)

    @app.route("/api/events/<int:eid>", methods=["DELETE"])
    @require_auth
    def api_delete_event(eid):
        ev_existing = get_event(eid)
        if not ev_existing:
            return jsonify({"error": "事件不存在"}), 404
        user = getattr(g, "current_user", None)
        if user and user.get("role") != "admin":
            if ev_existing.get("user_id") is not None and ev_existing.get("user_id") != user.get("id"):
                return jsonify({"error": "无权删除其他用户的事件"}), 403
        ev_title = ev_existing.get("title", f"ID {eid}")
        if delete_event(eid):
            logger.info(f"事件删除: id={eid}")
            _log("event_delete", "event", f"删除事件: {ev_title} (ID: {eid})")
            from notifier import send_webhook
            send_webhook("event_deleted", {"id": eid})
            return jsonify({"ok": True})
        return jsonify({"error": "删除失败"}), 500

    @app.route("/api/import", methods=["POST"])
    @require_auth
    def api_import():
        data = request.get_json()
        replace = request.args.get("replace", "false").lower() == "true"
        user = getattr(g, "current_user", None)
        uid = user["id"] if user and user.get("role") != "admin" else None
        count = import_data(data, replace, user_id=uid)
        logger.info(f"数据导入: {count} 条 (replace={replace}, user_id={uid})")
        _log("import", "event", f"导入数据: 共 {count} 条 (覆盖原有={replace})")
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
            _log("push_test", "system", "触发测试推送: 未配置任何有效通道", status="fail")
            return jsonify({"ok": False, "msg": "未配置任何推送通道，请先在推送设置中配置"})
        _log("push_test", "system", f"触发测试推送: {'; '.join(msgs)}", status="ok" if all_ok else "fail")
        if all_ok:
            return jsonify({"ok": True, "msg": "\n".join(msgs)})
        return jsonify({"ok": False, "msg": "\n".join(msgs)}), 500

    @app.route("/api/notify/check", methods=["POST"])
    @require_auth
    def api_notify_check():
        from notifier import check_and_notify
        check_and_notify()
        _log("notify_check", "system", "手动触发提醒检查扫描")
        return jsonify({"ok": True, "msg": "提醒检查完成"})

    @app.route("/api/backup", methods=["POST"])
    @require_auth
    def api_backup():
        from models import backup_database
        from config import load_backup_config
        cfg = load_backup_config()
        max_b = int(cfg.get("backup_count", 30))
        res = backup_database(max_backups=max_b)
        if res:
            _log("backup_create", "system", f"创建数据库热备份: {res.get('filename')}")
            return jsonify({"ok": True, "msg": "全量备份创建完成", "data": res})
        _log("backup_create", "system", "数据库热备份失败", status="fail")
        return jsonify({"ok": False, "msg": "备份失败"}), 500

    @app.route("/api/settings/backup", methods=["GET"])
    @require_auth
    def api_get_backup_settings():
        from config import load_backup_config
        return jsonify({"ok": True, "config": load_backup_config()})

    @app.route("/api/settings/backup", methods=["PUT"])
    @require_auth
    def api_save_backup_settings():
        from config import save_backup_config, load_backup_config
        data = request.get_json() or {}
        save_backup_config(data)
        _log("backup_config", "system", f"修改定时备份策略配置 (保留份数: {data.get('backup_count', 30)}, 时间: {data.get('backup_time', '03:00')})")
        # 动态更新调度器中备份任务的时间
        try:
            from scheduler import reschedule_backup
            reschedule_backup(app)
        except Exception as e:
            logger.warning(f"重新调度备份任务失败: {e}")
        return jsonify({"ok": True, "config": load_backup_config(), "msg": "备份配置已保存"})

    @app.route("/api/backup/list", methods=["GET"])
    @require_admin
    def api_backup_list():
        import glob
        backup_dir = os.path.join(Config.DATA_DIR, "backup")
        os.makedirs(backup_dir, exist_ok=True)
        files = []
        for path in sorted(glob.glob(os.path.join(backup_dir, "*.*")), reverse=True):
            fname = os.path.basename(path)
            if fname.endswith(".db") or fname.endswith(".json"):
                stat = os.stat(path)
                files.append({
                    "filename": fname,
                    "size": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                })
        return jsonify({"ok": True, "files": files})

    @app.route("/api/backup/download/<path:filename>", methods=["GET"])
    @require_admin
    def api_backup_download(filename):
        from flask import send_from_directory
        backup_dir = os.path.join(Config.DATA_DIR, "backup")
        # 安全过滤文件名防目录遍历
        safe_name = os.path.basename(filename)
        return send_from_directory(backup_dir, safe_name, as_attachment=True)

    @app.route("/manifest.json")
    def manifest():
        return jsonify({
            "name": "DaysHub 时光看板",
            "short_name": "DaysHub",
            "description": "农历+公历双轨纪念日与时光倒数看板",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#f0f2f5",
            "theme_color": "#667eea",
            "icons": [
                {
                    "src": "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📅</text></svg>",
                    "sizes": "192x192 512x512",
                    "type": "image/svg+xml"
                }
            ]
        })

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
        _log("push_config", "system", "修改系统推送配置")
        new_cfg = load_push_config()
        safe = dict(new_cfg)
        if safe.get("smtp_pass"):
            safe["smtp_pass"] = "******"
        return jsonify({"ok": True, "config": safe})

    # ========== 密码修改 ==========

    @app.route("/api/settings/password", methods=["PUT"])
    @require_auth
    def api_change_password():
        from models import get_user_by_id, verify_password, update_user
        from config import change_password
        data = request.get_json() or {}
        old_pass = str(data.get("old_password", ""))
        new_pass = str(data.get("new_password", ""))
        if not old_pass or not new_pass:
            return jsonify({"ok": False, "error": "旧密码和新密码不能为空"}), 400
        if len(new_pass) < 4:
            return jsonify({"ok": False, "error": "新密码至少4位"}), 400

        user = getattr(g, "current_user", None)
        if user and user.get("id"):
            u_db = get_user_by_id(user["id"])
            if u_db:
                # 校验当前用户密码
                from models import get_user_by_username
                full_u = get_user_by_username(u_db["username"])
                if full_u and verify_password(old_pass, full_u.get("password_hash", "")):
                    update_user(user["id"], {"password": new_pass})
                    # 如果是 admin 用户，同步全局 API_TOKEN
                    if u_db["username"] == "admin":
                        change_password(old_pass, new_pass)
                    _log("change_password", "auth", f"用户成功修改密码: {u_db['username']}")
                    return jsonify({"ok": True, "msg": "密码修改成功"})

        # 兼容旧逻辑
        if change_password(old_pass, new_pass):
            _log("change_password", "auth", "管理员通过独立密码模式修改密码成功")
            return jsonify({"ok": True, "msg": "密码修改成功"})
        _log("change_password", "auth", "修改密码失败(旧密码错误)", status="fail")
        return jsonify({"ok": False, "error": "旧密码错误"}), 401

    # ========== iCal 订阅与 Token 管理 ==========

    @app.route("/api/settings/ical_token", methods=["GET"])
    @require_auth
    def api_get_ical_token():
        from config import get_ical_token
        user = getattr(g, "current_user", None)
        uid = user["id"] if user else None
        return jsonify({"ok": True, "token": get_ical_token(uid)})

    @app.route("/api/settings/ical_token/reset", methods=["POST"])
    @require_auth
    def api_reset_ical_token():
        from config import reset_ical_token
        user = getattr(g, "current_user", None)
        uid = user["id"] if user else None
        new_token = reset_ical_token(uid)
        return jsonify({"ok": True, "token": new_token, "msg": "专属日历订阅 Token 已重置"})

    @app.route("/api/calendar.ics")
    @app.route("/ical/events.ics")
    def api_ics():
        from config import verify_ical_token
        token = request.headers.get("Authorization", "")
        if token.startswith("Bearer "):
            token = token[7:]
        elif request.args.get("token"):
            token = request.args.get("token") or ""
        token = str(token).strip()

        target_user_id = None
        if Config.auth_enabled():
            valid, user_id = verify_ical_token(token)
            if not valid:
                return jsonify({"error": "Unauthorized"}), 401
            target_user_id = user_id

        ics = generate_ics(user_id=target_user_id)
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
    is_dev = os.environ.get("FLASK_ENV") == "development"
    if is_dev:
        app.run(host="0.0.0.0", port=port, debug=False)
    else:
        try:
            from waitress import serve
            logger.info(f"以 Waitress 生产模式运行在端口 {port}...")
            serve(app, host="0.0.0.0", port=port, threads=6, clear_untrusted_proxy_headers=False)
        except ImportError:
            logger.warning("Waitress 未安装，回退至 Flask 内置服务器")
            app.run(host="0.0.0.0", port=port, debug=False)