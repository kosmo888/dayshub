"""
DaysHub 认证中间件与审计辅助模块 v2.0.0
- 统一 API Token / User Token 鉴权装饰器
- 管理员权限守门器
- 真实客户端 IP 解析
- 系统操作日志记录器
"""
from functools import wraps
from flask import request, jsonify, g
from config import Config
from logger import logger


def get_client_ip() -> str:
    """提取客户端真实 IP 地址（兼容反向代理）"""
    xff = request.headers.get("X-Forwarded-For") or request.environ.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    xri = request.headers.get("X-Real-IP") or request.environ.get("HTTP_X_REAL_IP")
    if xri:
        return xri.strip()
    return request.remote_addr or "unknown"


def log_action(action: str, module: str = "system", details: str = "", status: str = "ok", user=None):
    """统一记录系统操作/审计日志"""
    try:
        from models import log_system_action
        u = user or getattr(g, "current_user", None)
        uid = u["id"] if u and isinstance(u, dict) and "id" in u else None
        uname = u["username"] if u and isinstance(u, dict) and "username" in u else ""
        ip = get_client_ip()
        ua = request.headers.get("User-Agent", "")
        log_system_action(
            user_id=uid, username=uname, action=action, module=module,
            details=details, ip=ip, user_agent=ua, status=status
        )
    except Exception as e:
        logger.warning(f"记录操作日志失败: {e}")


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
