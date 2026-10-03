"""
DaysHub 配置文件 v1.1.0 — 所有配置通过环境变量注入，适配 Docker 部署
"""
import os
import secrets
import hmac
import time

VERSION = "2.0.0"

class Config:
    # ========== 基础 ==========
    SECRET_KEY = os.environ.get("DAYSHUB_SECRET_KEY", "dayshub-dev-key-change-me")
    # API 认证 Token（为空则不启用认证；生产环境务必设置）
    API_TOKEN = os.environ.get("DAYSHUB_API_TOKEN", "")
    DATA_DIR = os.environ.get("DAYSHUB_DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
    DB_PATH = os.path.join(DATA_DIR, "dayshub.db")
    TIMEZONE = os.environ.get("DAYSHUB_TZ", "Asia/Shanghai")
    # 推送重试次数
    PUSH_RETRY_COUNT = int(os.environ.get("PUSH_RETRY_COUNT", "3"))
    PUSH_RETRY_DELAY = int(os.environ.get("PUSH_RETRY_DELAY", "5"))

    # ========== 邮件推送 (SMTP) ==========
    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASS = os.environ.get("SMTP_PASS", "")
    SMTP_FROM = os.environ.get("SMTP_FROM", "")
    SMTP_TO = os.environ.get("SMTP_TO", "")
    SMTP_SSL = os.environ.get("SMTP_SSL", "true").lower() == "true"

    # ========== 企业微信 Webhook ==========
    WECOM_WEBHOOK = os.environ.get("WECOM_WEBHOOK", "")

    # ========== Telegram Bot ==========
    TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
    TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "")

    # ========== 通用自定义 Webhook ==========
    CUSTOM_WEBHOOK_URLS = os.environ.get("CUSTOM_WEBHOOK_URLS", "")
    CUSTOM_WEBHOOK_HEADERS = os.environ.get("CUSTOM_WEBHOOK_HEADERS", "")
    CUSTOM_WEBHOOK_EVENTS = os.environ.get("CUSTOM_WEBHOOK_EVENTS", "morning,reminder,event_created,event_updated,event_deleted")

    # ========== 通知策略 ==========
    ADVANCE_DAYS = [int(x) for x in os.environ.get("ADVANCE_DAYS", "7,3,1,0").split(",")]
    MORNING_REPORT_TIME = os.environ.get("MORNING_REPORT_TIME", "08:00")

    # ========== iCal 订阅 ==========
    BASE_URL = os.environ.get("DAYSHUB_BASE_URL", "http://localhost:5217")

    # ========== 预置数据 ==========
    SEED_EXAMPLES = os.environ.get("SEED_EXAMPLES", "true").lower() == "true"

    @classmethod
    def auth_enabled(cls):
        # 现代 DaysHub 拥有完整的多用户与权限隔离体系，认证默认常开
        # 仅当显式设置 DAYSHUB_DISABLE_AUTH=true 时才允许关闭（例如完全免密内网无用户模式）
        return os.environ.get("DAYSHUB_DISABLE_AUTH", "").lower() != "true"

    @classmethod
    def mail_enabled(cls):
        return bool(cls.SMTP_HOST and cls.SMTP_USER and Config.SMTP_PASS and Config.SMTP_TO)

    @classmethod
    def wecom_enabled(cls):
        return bool(cls.WECOM_WEBHOOK)

    @classmethod
    def tg_enabled(cls):
        return bool(cls.TG_BOT_TOKEN and cls.TG_CHAT_ID)

    @classmethod
    def webhook_enabled(cls):
        return bool(cls.CUSTOM_WEBHOOK_URLS)

    @classmethod
    def webhook_event_enabled(cls, event_type: str) -> bool:
        allowed = [e.strip() for e in cls.CUSTOM_WEBHOOK_EVENTS.split(",")]
        return event_type in allowed

    @classmethod
    def webhook_urls(cls) -> list:
        return [u.strip() for u in cls.CUSTOM_WEBHOOK_URLS.split(",") if u.strip()]

    @classmethod
    def webhook_headers(cls) -> dict:
        if not cls.CUSTOM_WEBHOOK_HEADERS:
            return {}
        try:
            import json
            return json.loads(cls.CUSTOM_WEBHOOK_HEADERS)
        except Exception:
            return {}

    @classmethod
    def is_production(cls):
        """检查是否生产环境（SECRET_KEY 非默认值且 API_TOKEN 已设置）"""
        return cls.SECRET_KEY != "dayshub-dev-key-change-me"


# ========== 系统公开设置（注册等） ==========

def is_registration_allowed() -> bool:
    """检查是否允许公开注册新账号（默认开放）"""
    try:
        from models import get_setting
        val = get_setting("allow_registration", "true")
        return str(val).lower() == "true"
    except Exception:
        return True

def set_registration_allowed(allowed: bool):
    """设置是否允许公开注册"""
    from models import set_setting
    set_setting("allow_registration", "true" if allowed else "false")


# ========== 自动备份与维护配置 ==========

def load_backup_config() -> dict:
    """从 DB settings 表读取自动备份配置"""
    try:
        from models import get_setting
        en = str(get_setting("backup_enabled", "true") or "true")
        bt = str(get_setting("backup_time", "03:00") or "03:00")
        bc = int(get_setting("backup_count", "30") or 30)
        return {
            "backup_enabled": en.lower() == "true",
            "backup_time": bt,
            "backup_count": bc,
        }
    except Exception:
        return {
            "backup_enabled": True,
            "backup_time": "03:00",
            "backup_count": 30,
        }

def save_backup_config(data: dict):
    """保存备份配置至 DB settings 表"""
    from models import set_setting
    if "backup_enabled" in data:
        set_setting("backup_enabled", "true" if data["backup_enabled"] else "false")
    if "backup_time" in data and data["backup_time"]:
        set_setting("backup_time", str(data["backup_time"]).strip())
    if "backup_count" in data and data["backup_count"]:
        try:
            cnt = max(1, int(data["backup_count"]))
            set_setting("backup_count", str(cnt))
        except ValueError:
            pass


# ========== 推送配置（从DB动态读取，覆盖环境变量） ==========
_push_cache = {}
_push_cache_ts = 0

def load_push_config():
    """从DB settings表读取推送配置，覆盖环境变量"""
    global _push_cache, _push_cache_ts
    import time
    now = time.time()
    if _push_cache and now - _push_cache_ts < 5:  # 5秒缓存
        return _push_cache
    try:
        from models import get_setting
        def gs(key):
            v = get_setting(key)
            return v if v is not None else ""
        cfg = {
            "smtp_host": gs("push_smtp_host") or Config.SMTP_HOST,
            "smtp_port": gs("push_smtp_port") or str(Config.SMTP_PORT),
            "smtp_user": gs("push_smtp_user") or Config.SMTP_USER,
            "smtp_pass": gs("push_smtp_pass") or Config.SMTP_PASS,
            "smtp_from": gs("push_smtp_from") or Config.SMTP_FROM,
            "smtp_to": gs("push_smtp_to") or Config.SMTP_TO,
            "smtp_ssl": gs("push_smtp_ssl") or ("true" if Config.SMTP_SSL else "false"),
            "wecom_webhook": gs("push_wecom_webhook") or Config.WECOM_WEBHOOK,
            "tg_bot_token": gs("push_tg_bot_token") or Config.TG_BOT_TOKEN,
            "tg_chat_id": gs("push_tg_chat_id") or Config.TG_CHAT_ID,
            "custom_webhook_urls": gs("push_custom_webhook_urls") or Config.CUSTOM_WEBHOOK_URLS,
            "custom_webhook_headers": gs("push_custom_webhook_headers") or Config.CUSTOM_WEBHOOK_HEADERS,
            "custom_webhook_events": gs("push_custom_webhook_events") or Config.CUSTOM_WEBHOOK_EVENTS,
            "advance_days": gs("push_advance_days") or ",".join(str(d) for d in Config.ADVANCE_DAYS),
            "morning_report_time": gs("push_morning_report_time") or Config.MORNING_REPORT_TIME,
        }
        _push_cache = cfg
        _push_cache_ts = now
        return cfg
    except Exception:
        return {
            "smtp_host": Config.SMTP_HOST, "smtp_port": str(Config.SMTP_PORT),
            "smtp_user": Config.SMTP_USER, "smtp_pass": Config.SMTP_PASS,
            "smtp_from": Config.SMTP_FROM, "smtp_to": Config.SMTP_TO,
            "smtp_ssl": "true" if Config.SMTP_SSL else "false",
            "wecom_webhook": Config.WECOM_WEBHOOK,
            "tg_bot_token": Config.TG_BOT_TOKEN, "tg_chat_id": Config.TG_CHAT_ID,
            "custom_webhook_urls": Config.CUSTOM_WEBHOOK_URLS,
            "custom_webhook_headers": Config.CUSTOM_WEBHOOK_HEADERS,
            "custom_webhook_events": Config.CUSTOM_WEBHOOK_EVENTS,
            "advance_days": ",".join(str(d) for d in Config.ADVANCE_DAYS),
            "morning_report_time": Config.MORNING_REPORT_TIME,
        }

def save_push_config(data: dict):
    """保存推送配置到DB settings表"""
    global _push_cache, _push_cache_ts
    from models import set_setting
    key_map = {
        "smtp_host": "push_smtp_host", "smtp_port": "push_smtp_port",
        "smtp_user": "push_smtp_user", "smtp_pass": "push_smtp_pass",
        "smtp_from": "push_smtp_from", "smtp_to": "push_smtp_to",
        "smtp_ssl": "push_smtp_ssl",
        "wecom_webhook": "push_wecom_webhook",
        "tg_bot_token": "push_tg_bot_token", "tg_chat_id": "push_tg_chat_id",
        "custom_webhook_urls": "push_custom_webhook_urls",
        "custom_webhook_headers": "push_custom_webhook_headers",
        "custom_webhook_events": "push_custom_webhook_events",
        "advance_days": "push_advance_days",
        "morning_report_time": "push_morning_report_time",
    }
    for k, sk in key_map.items():
        if k in data and data[k] is not None:
            set_setting(sk, str(data[k]))
    _push_cache = {}
    _push_cache_ts = 0


def change_password(old_pass: str, new_pass: str) -> bool:
    """修改访问密码，存DB settings表，验证旧密码"""
    current_pass = get_current_password()
    if not hmac.compare_digest(str(old_pass), str(current_pass)):
        return False
    if not new_pass or len(new_pass) < 4:
        return False
    from models import set_setting
    set_setting("api_token", new_pass)
    # 更新内存中的 Config.API_TOKEN
    Config.API_TOKEN = new_pass
    return True


def get_current_password() -> str:
    """获取当前密码（优先DB，其次环境变量）"""
    try:
        from models import get_setting
        db_token = get_setting("api_token")
        if db_token:
            return db_token
    except Exception:
        pass
    return Config.API_TOKEN


def get_ical_token(user_id: int | None = None) -> str:
    """获取独立的 iCal 订阅 Token（支持多用户独立只读 Token）"""
    try:
        from models import get_setting, set_setting
        key = f"ical_token_{user_id}" if user_id else "ical_token"
        tok = get_setting(key)
        if tok:
            return tok
        tok = secrets.token_urlsafe(24)
        set_setting(key, tok)
        return tok
    except Exception:
        return f"dayshub-ical-{user_id or 'default'}"


def reset_ical_token(user_id: int | None = None) -> str:
    """重置 iCal 订阅 Token"""
    from models import set_setting
    key = f"ical_token_{user_id}" if user_id else "ical_token"
    tok = secrets.token_urlsafe(24)
    set_setting(key, tok)
    return tok


def verify_ical_token(token: str) -> tuple[bool, int | None]:
    """验证 ical_token，返回 (is_valid, user_id)"""
    if not token:
        return False, None
    import hmac
    from models import get_db, list_users
    # 1. 验证全局/管理员旧版 token
    global_tok = get_ical_token(None)
    if hmac.compare_digest(token, global_tok):
        return True, 1

    # 2. 验证各个用户的专属 ical_token
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM settings WHERE key LIKE 'ical_token_%'").fetchall()
    conn.close()
    for r in rows:
        stored_tok = r["value"]
        if stored_tok and hmac.compare_digest(token, stored_tok):
            try:
                uid = int(r["key"].replace("ical_token_", ""))
                return True, uid
            except ValueError:
                return True, None

    # 3. 兼容管理密码直通
    cur_pass = str(get_current_password())
    if hmac.compare_digest(token, cur_pass):
        return True, 1
    return False, None


# ========== 登录防爆破频控 (5次失败锁10分钟) ==========
_login_failures = {}  # {ip: [fail_timestamp, ...]}
_login_locks = {}     # {ip: unlock_timestamp}
MAX_FAILURES = 5
LOCK_SECONDS = 600    # 10 分钟

def check_login_rate_limit(ip: str) -> tuple[bool, int]:
    """检查是否被锁定。返回 (is_allowed, remaining_lock_seconds)"""
    now = time.time()
    # 清理过期锁
    if ip in _login_locks:
        if now < _login_locks[ip]:
            return False, int(_login_locks[ip] - now)
        else:
            del _login_locks[ip]
            if ip in _login_failures:
                del _login_failures[ip]

    # 清理 10 分钟前的历史失败
    if ip in _login_failures:
        _login_failures[ip] = [ts for ts in _login_failures[ip] if now - ts < LOCK_SECONDS]
    return True, 0

def record_login_failure(ip: str) -> tuple[bool, int]:
    """记录一次登录失败。返回 (is_locked, remaining_seconds)"""
    now = time.time()
    if ip not in _login_failures:
        _login_failures[ip] = []
    _login_failures[ip].append(now)
    # 保留窗口内失败
    _login_failures[ip] = [ts for ts in _login_failures[ip] if now - ts < LOCK_SECONDS]
    if len(_login_failures[ip]) >= MAX_FAILURES:
        _login_locks[ip] = now + LOCK_SECONDS
        return True, LOCK_SECONDS
    return False, 0

def reset_login_failure(ip: str):
    """登录成功，重置计数"""
    if ip in _login_failures:
        del _login_failures[ip]
    if ip in _login_locks:
        del _login_locks[ip]