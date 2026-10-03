"""
DaysHub 系统管理与审计日志蓝图 v2.0.0
- 多用户管理（列表、增删改查、停用与角色）
- 全局系统策略（访客注册开关控制）
- 操作审计日志（管理员全局多维筛选、普通用户只读隔离）
- 后端服务实时运行日志调阅 (dayshub.log) 与过期日志清理
"""
import os
from flask import Blueprint, request, jsonify, g
from auth_middleware import require_admin, require_auth, log_action
from config import Config
from models import (
    list_users, create_user, get_user_by_username,
    get_user_by_id, update_user, delete_user,
    list_system_logs, clear_system_logs
)

admin_bp = Blueprint("admin", __name__)


# ========== 用户管理 API ==========

@admin_bp.route("/api/admin/users", methods=["GET"])
@require_admin
def api_admin_list_users():
    """获取所有系统用户列表"""
    return jsonify({"ok": True, "users": list_users()})


@admin_bp.route("/api/admin/users", methods=["POST"])
@require_admin
def api_admin_create_user():
    """管理员手动创建新用户"""
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
    log_action("user_create", "user", f"创建用户: {username} (角色: {role}, 昵称: {display_name})")
    return jsonify({"ok": True, "user": user, "msg": "用户创建成功"}), 201


@admin_bp.route("/api/admin/users/<int:uid>", methods=["PUT"])
@require_admin
def api_admin_update_user(uid):
    """更新用户信息或重置密码"""
    user = get_user_by_id(uid)
    if not user:
        return jsonify({"ok": False, "error": "用户不存在"}), 404
    data = request.get_json() or {}
    updated = update_user(uid, data)
    log_action("user_update", "user", f"更新用户信息: {user['username']} (ID: {uid})")
    return jsonify({"ok": True, "user": updated, "msg": "用户信息已更新"})


@admin_bp.route("/api/admin/users/<int:uid>", methods=["DELETE"])
@require_admin
def api_admin_delete_user(uid):
    """删除指定用户"""
    user = get_user_by_id(uid)
    if not user:
        return jsonify({"ok": False, "error": "用户不存在"}), 404
    if user["username"] == "admin":
        return jsonify({"ok": False, "error": "初始管理员账号不能删除"}), 400
    if delete_user(uid):
        log_action("user_delete", "user", f"删除用户: {user['username']} (ID: {uid})")
        return jsonify({"ok": True, "msg": "用户已删除"})
    return jsonify({"ok": False, "error": "删除失败"}), 500


# ========== 全局系统策略 ==========

@admin_bp.route("/api/admin/system", methods=["GET"])
@require_admin
def api_admin_get_system():
    """获取当前系统策略配置"""
    from config import is_registration_allowed
    return jsonify({
        "ok": True,
        "allow_registration": is_registration_allowed()
    })


@admin_bp.route("/api/admin/system", methods=["PUT"])
@require_admin
def api_admin_save_system():
    """更新系统策略配置"""
    from config import set_registration_allowed, is_registration_allowed
    data = request.get_json() or {}
    if "allow_registration" in data:
        set_registration_allowed(bool(data["allow_registration"]))
    log_action("system_config", "system", f"修改系统配置: 允许注册={is_registration_allowed()}")
    return jsonify({
        "ok": True,
        "allow_registration": is_registration_allowed(),
        "msg": "系统设置已更新"
    })


# ========== 系统操作与审计日志 ==========

@admin_bp.route("/api/admin/logs", methods=["GET"])
@require_admin
def api_admin_list_logs():
    """管理员查询全量系统操作审计日志"""
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


@admin_bp.route("/api/user/logs", methods=["GET"])
@require_auth
def api_user_list_logs():
    """普通用户查看个人专属操作审计日志"""
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


@admin_bp.route("/api/admin/runtime_logs", methods=["GET"])
@require_admin
def api_admin_runtime_logs():
    """获取后端服务实时运行日志 (dayshub.log) 最新 N 行"""
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


@admin_bp.route("/api/admin/logs", methods=["DELETE"])
@require_admin
def api_admin_clear_logs():
    """清理系统操作审计日志"""
    data = request.get_json(silent=True) or {}
    days = data.get("days_to_keep")
    try:
        days = int(days) if days is not None else None
    except (ValueError, TypeError):
        days = None
    count = clear_system_logs(days_to_keep=days)
    log_action("clear_logs", "system", f"清理系统日志: 共清除 {count} 条 (保留天数: {days if days else '全部'})")
    return jsonify({"ok": True, "deleted_count": count, "msg": f"已成功清理 {count} 条日志"})
