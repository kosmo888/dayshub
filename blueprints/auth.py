"""
DaysHub 认证与用户账号蓝图 v2.0.0
- 用户登录、登出、自主注册
- 个人信息查询与密码修改
"""
import re
import hmac
from flask import Blueprint, request, jsonify, g
from config import Config
from logger import logger
from auth_middleware import require_auth, log_action, get_client_ip
from models import (
    get_user_by_username, create_user, create_user_token,
    verify_password, get_user_by_id, update_user
)

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/api/register", methods=["POST"])
def api_register():
    """用户注册接口"""
    from config import is_registration_allowed, check_login_rate_limit, record_login_failure

    client_ip = get_client_ip()

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
        log_action("register", "auth", f"用户注册失败(数据库错误): {username}", status="fail")
        return jsonify({"ok": False, "error": "注册失败，请稍后重试"}), 500

    token = create_user_token(user["id"])
    logger.info(f"新用户注册成功: {username} (IP: {client_ip})")
    log_action("register", "auth", f"新用户注册成功: {username} ({display_name})", user=user)

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


@auth_bp.route("/api/login", methods=["POST"])
def api_login():
    """用户登录接口"""
    from config import (
        get_current_password, check_login_rate_limit,
        record_login_failure, reset_login_failure
    )

    client_ip = get_client_ip()

    # 检查是否处于锁定状态
    allowed, remaining_sec = check_login_rate_limit(client_ip)
    if not allowed:
        mins = max(1, (remaining_sec + 59) // 60)
        logger.warning(f"登录被频控拦截: {client_ip}, 剩余锁定时间 {remaining_sec}s")
        log_action("login", "auth", f"登录拦截(频控锁定): {client_ip}", status="fail")
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
                log_action("login", "auth", f"用户登录成功: {username}", user=user)
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
        log_action("login", "auth", "管理员通过独立密码登录成功", user=admin_info)
        return jsonify({
            "ok": True,
            "token": token,
            "user": admin_info
        })

    is_locked, lock_sec = record_login_failure(client_ip)
    logger.warning(f"登录失败: {client_ip} (用户: {username or 'admin'})")
    log_action("login", "auth", f"密码验证失败 (用户: {username or 'admin'})", status="fail")
    if is_locked:
        mins = max(1, (lock_sec + 59) // 60)
        return jsonify({
            "ok": False,
            "error": f"账号或密码错误。连续失败已被锁定 {mins} 分钟"
        }), 429
    return jsonify({"ok": False, "error": "用户名或密码错误"}), 401


@auth_bp.route("/api/logout", methods=["POST"])
def api_logout():
    """退出登录"""
    log_action("logout", "auth", "用户退出登录")
    return jsonify({"ok": True, "msg": "已安全退出"})


@auth_bp.route("/api/user/profile", methods=["GET"])
@require_auth
def api_user_profile():
    """获取当前已登录用户信息"""
    user = getattr(g, "current_user", None)
    return jsonify({"ok": True, "user": user})


@auth_bp.route("/api/settings/password", methods=["PUT"])
@require_auth
def api_change_password():
    """修改当前用户登录密码"""
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
            full_u = get_user_by_username(u_db["username"])
            if full_u and verify_password(old_pass, full_u.get("password_hash", "")):
                update_user(user["id"], {"password": new_pass})
                if u_db["username"] == "admin":
                    change_password(old_pass, new_pass)
                log_action("change_password", "auth", f"用户成功修改密码: {u_db['username']}")
                return jsonify({"ok": True, "msg": "密码修改成功"})

    # 兼容旧逻辑
    if change_password(old_pass, new_pass):
        log_action("change_password", "auth", "管理员通过独立密码模式修改密码成功")
        return jsonify({"ok": True, "msg": "密码修改成功"})
    log_action("change_password", "auth", "修改密码失败(旧密码错误)", status="fail")
    return jsonify({"ok": False, "error": "旧密码错误"}), 401
