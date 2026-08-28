"""
DaysHub 数据库模型与 CRUD 操作
SQLite + 手写 SQL（零 ORM 依赖，极致轻量）
"""
import sqlite3
import json
import os
import hashlib
import secrets
import time
from datetime import date, datetime
from config import Config
from lunar_engine import (
    get_next_lunar_birthday, lunar_to_solar, days_until, days_since,
    get_next_milestone, get_milestones
)

# 事件类型
EVENT_TYPES = {
    "countdown": "倒数日",      # 未来某天，倒计时
    "accumulate": "累计日",     # 过去某天起，累计天数
    "recurring": "循环日",      # 每年重复（公历或农历）
}

# 分类
CATEGORIES = {
    "family": {"name": "家庭", "color": "#FF6B6B", "icon": "🏠"},
    "anniversary": {"name": "纪念日", "color": "#FF8E53", "icon": "💝"},
    "work": {"name": "工作/考试", "color": "#4ECDC4", "icon": "💼"},
    "habit": {"name": "习惯打卡", "color": "#95E1D3", "icon": "🎯"},
    "life": {"name": "生活/资产", "color": "#A8DADC", "icon": "📋"},
    "holiday": {"name": "节假日", "color": "#F4A261", "icon": "🎉"},
    "other": {"name": "其他", "color": "#B0BEC5", "icon": "📌"},
}


def get_db():
    """获取数据库连接"""
    import os
    os.makedirs(Config.DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """初始化数据库表"""
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',   -- 'admin' 或 'user'
        display_name TEXT DEFAULT '',
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now', 'localtime')),
        updated_at TEXT DEFAULT (datetime('now', 'localtime'))
    );

    CREATE TABLE IF NOT EXISTS user_tokens (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        expires_at INTEGER NOT NULL,
        created_at TEXT DEFAULT (datetime('now', 'localtime')),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        event_type TEXT NOT NULL DEFAULT 'countdown',
        category TEXT NOT NULL DEFAULT 'other',
        date TEXT NOT NULL,           -- ISO 格式 YYYY-MM-DD（公历）
        lunar_month INTEGER,          -- 农历月（1-12），为空表示公历事件
        lunar_day INTEGER,            -- 农历日（1-30）
        is_leap INTEGER DEFAULT 0,    -- 是否闰月
        is_recurring INTEGER DEFAULT 0, -- 是否每年重复
        note TEXT DEFAULT '',         -- 备注/备忘
        color TEXT DEFAULT '',        -- 自定义颜色（空则用分类颜色）
        icon TEXT DEFAULT '',         -- 自定义图标
        is_pinned INTEGER DEFAULT 0,  -- 是否置顶
        is_active INTEGER DEFAULT 1,  -- 是否启用
        created_at TEXT DEFAULT (datetime('now', 'localtime')),
        updated_at TEXT DEFAULT (datetime('now', 'localtime'))
    );

    CREATE TABLE IF NOT EXISTS notification_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER,
        notify_date TEXT NOT NULL,
        advance_days INTEGER DEFAULT 0,
        channel TEXT DEFAULT 'email',
        status TEXT DEFAULT 'sent',
        FOREIGN KEY (event_id) REFERENCES events(id)
    );

    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    );

    CREATE TABLE IF NOT EXISTS event_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER,
        action TEXT NOT NULL,
        old_data TEXT,
        new_data TEXT,
        changed_at TEXT DEFAULT (datetime('now', 'localtime')),
        FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE SET NULL
    );
    CREATE INDEX IF NOT EXISTS idx_event_history_eid ON event_history(event_id);
    """)

    # 迁移：添加 advance_days 列（每个事件单独的提前推送天数，默认3天）
    try:
        conn.execute("ALTER TABLE events ADD COLUMN advance_days INTEGER DEFAULT 3")
        conn.commit()
    except Exception:
        pass  # 列已存在

    # 迁移：添加 user_id 列关联用户
    try:
        conn.execute("ALTER TABLE events ADD COLUMN user_id INTEGER REFERENCES users(id)")
        conn.commit()
    except Exception:
        pass

    # 默认初始化内置管理员用户
    _seed_default_admin(conn)

    conn.commit()
    conn.close()
    print(f"[DB] 初始化完成: {Config.DB_PATH}")


# ========== 用户与认证模型 ==========

def hash_password(password: str, salt: str = "") -> str:
    """使用 PBKDF2-SHA256 安全哈希密码"""
    if not salt:
        salt = secrets.token_hex(16)
    pw_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
    return f"{salt}${pw_hash}"

def verify_password(password: str, stored_hash: str) -> bool:
    """验证密码哈希，兼容旧明文密码"""
    if not stored_hash:
        return False
    if "$" in stored_hash:
        try:
            salt, pw_hash = stored_hash.split("$", 1)
            check = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
            return hmac_compare(check, pw_hash)
        except Exception:
            return False
    return hmac_compare(password, stored_hash)

def hmac_compare(a: str, b: str) -> bool:
    import hmac
    return hmac.compare_digest(str(a), str(b))

def _seed_default_admin(conn):
    """初始化默认管理员账号 admin"""
    row = conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()
    if not row:
        init_pass = Config.API_TOKEN or "dayshub_admin_123"
        h = hash_password(init_pass)
        conn.execute(
            "INSERT INTO users (username, password_hash, role, display_name, is_active) VALUES (?, ?, 'admin', '管理员', 1)",
            ("admin", h)
        )
        conn.commit()
    # 将无归属历史事件绑定到管理员 (user_id=1)
    conn.execute("UPDATE events SET user_id = (SELECT id FROM users WHERE username = 'admin') WHERE user_id IS NULL")
    conn.commit()


def create_user(username: str, password: str, role: str = "user", display_name: str = "") -> dict | None:
    """创建新用户"""
    conn = get_db()
    h = hash_password(password)
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, role, display_name, is_active) VALUES (?, ?, ?, ?, 1)",
        (username.strip(), h, role, display_name.strip() or username.strip())
    )
    conn.commit()
    uid = cur.lastrowid
    conn.close()
    return get_user_by_id(uid) if uid is not None else None


def get_user_by_id(uid: int) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT id, username, role, display_name, is_active, created_at, updated_at FROM users WHERE id = ?", (uid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_username(username: str) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username.strip(),)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_users() -> list:
    conn = get_db()
    rows = conn.execute("SELECT id, username, role, display_name, is_active, created_at, updated_at FROM users ORDER BY id ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_user(uid: int, data: dict) -> dict | None:
    conn = get_db()
    fields = []
    vals = []
    if "display_name" in data:
        fields.append("display_name = ?")
        vals.append(data["display_name"])
    if "role" in data:
        fields.append("role = ?")
        vals.append(data["role"])
    if "is_active" in data:
        fields.append("is_active = ?")
        vals.append(int(data["is_active"]))
    if "password" in data and data["password"]:
        fields.append("password_hash = ?")
        vals.append(hash_password(data["password"]))
    if not fields:
        conn.close()
        return get_user_by_id(uid)
    fields.append("updated_at = datetime('now', 'localtime')")
    vals.append(uid)
    conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", vals)
    conn.commit()
    conn.close()
    return get_user_by_id(uid)


def delete_user(uid: int) -> bool:
    """删除用户（管理员账号不能被删除）"""
    user = get_user_by_id(uid)
    if not user or user["username"] == "admin":
        return False
    conn = get_db()
    conn.execute("DELETE FROM user_tokens WHERE user_id = ?", (uid,))
    conn.execute("DELETE FROM events WHERE user_id = ?", (uid,))
    conn.execute("DELETE FROM users WHERE id = ?", (uid,))
    conn.commit()
    conn.close()
    return True


def create_user_token(user_id: int, expiry_days: int = 365) -> str:
    """为用户颁发 Bearer Token，记录在 user_tokens 表"""
    token = secrets.token_urlsafe(32)
    expires_at = int(time.time()) + (expiry_days * 86400)
    conn = get_db()
    conn.execute("INSERT INTO user_tokens (token, user_id, expires_at) VALUES (?, ?, ?)", (token, user_id, expires_at))
    conn.commit()
    conn.close()
    return token


def verify_user_token(token: str) -> dict | None:
    """验证 Token 并返回对应的用户对象，过期自动失效"""
    if not token:
        return None
    now = int(time.time())
    conn = get_db()
    row = conn.execute("""
        SELECT u.id, u.username, u.role, u.display_name, u.is_active
        FROM user_tokens t
        JOIN users u ON t.user_id = u.id
        WHERE t.token = ? AND t.expires_at > ? AND u.is_active = 1
    """, (token, now)).fetchone()
    conn.close()
    return dict(row) if row else None


def revoke_user_token(token: str):
    conn = get_db()
    conn.execute("DELETE FROM user_tokens WHERE token = ?", (token,))
    conn.commit()
    conn.close()


# ========== 事件 CRUD ==========

def create_event(data: dict, user_id: int | None = None) -> dict | None:
    """创建事件"""
    conn = get_db()
    cur = conn.execute("""
        INSERT INTO events (title, event_type, category, date, lunar_month, lunar_day,
            is_leap, is_recurring, note, color, icon, is_pinned, is_active, advance_days, user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["title"],
        data.get("event_type", "countdown"),
        data.get("category", "other"),
        data["date"],
        data.get("lunar_month"),
        data.get("lunar_day"),
        int(data.get("is_leap", 0)),
        int(data.get("is_recurring", 0)),
        data.get("note", ""),
        data.get("color", ""),
        data.get("icon", ""),
        int(data.get("is_pinned", 0)),
        int(data.get("is_active", 1)),
        int(data.get("advance_days", 3)),
        user_id or data.get("user_id", 1),
    ))
    conn.commit()
    eid = cur.lastrowid
    _log_history(conn, eid, "created", None, data)
    conn.commit()
    conn.close()
    return get_event(eid)


def get_event(eid: int) -> dict | None:
    """获取单个事件"""
    conn = get_db()
    row = conn.execute("SELECT * FROM events WHERE id = ?", (eid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_events(active_only: bool = True) -> list:
    """获取所有事件列表"""
    conn = get_db()
    sql = "SELECT * FROM events"
    if active_only:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY is_pinned DESC, date ASC"
    rows = conn.execute(sql).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_event(eid: int, data: dict) -> dict | None:
    """更新事件"""
    old_ev = get_event(eid)
    conn = get_db()
    fields = []
    vals = []
    for k in ["title", "event_type", "category", "date", "lunar_month", "lunar_day",
              "is_leap", "is_recurring", "note", "color", "icon", "is_pinned", "is_active", "advance_days"]:
        if k in data:
            fields.append(f"{k} = ?")
            v = data[k]
            if v is None:
                vals.append(None)
            elif k in ("is_leap", "is_recurring", "is_pinned", "is_active", "advance_days"):
                vals.append(int(v))
            else:
                vals.append(v)
    if not fields:
        conn.close()
        return get_event(eid)
    fields.append("updated_at = datetime('now', 'localtime')")
    vals.append(eid)
    conn.execute(f"UPDATE events SET {', '.join(fields)} WHERE id = ?", vals)
    _log_history(conn, eid, "updated", old_ev, data)
    conn.commit()
    conn.close()
    return get_event(eid)


def delete_event(eid: int) -> bool:
    """删除事件（历史记录保留，event_id 被 SET NULL）"""
    old_ev = get_event(eid)
    conn = get_db()
    if old_ev:
        _log_history(conn, eid, "deleted", old_ev, None)
    # notification_log 外键也需要解除
    conn.execute("UPDATE notification_log SET event_id = NULL WHERE event_id = ?", (eid,))
    cur = conn.execute("DELETE FROM events WHERE id = ?", (eid,))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted


# ========== 事件计算（核心：给每个事件附加动态计算结果） ==========

def compute_event(ev: dict, base_date: date = None) -> dict:
    """
    为事件附加计算字段：
    - days_remaining / days_passed
    - next_date（循环事件的下一个日期）
    - is_today
    - milestone（累计日的下一个里程碑）
    - category_info
    """
    if base_date is None:
        base_date = date.today()

    ev_date = date.fromisoformat(ev["date"])
    ev["category_info"] = CATEGORIES.get(ev["category"], CATEGORIES["other"])
    ev["color"] = ev["color"] or ev["category_info"]["color"]
    ev["icon"] = ev["icon"] or ev["category_info"]["icon"]

    if ev["event_type"] == "accumulate":
        ev["days_passed"] = days_since(ev_date, base_date)
        ev["days_remaining"] = None
        ev["is_today"] = (ev_date == base_date)
        ev["next_date"] = None
        ev["next_milestone"] = get_next_milestone(ev_date, base_date)
        ev["milestones"] = get_milestones(ev_date, base_date)

    elif ev["event_type"] == "recurring" or ev["is_recurring"]:
        # 循环事件：计算下一个出现日期
        if ev["lunar_month"] and ev["lunar_day"]:
            next_d = get_next_lunar_birthday(
                ev["lunar_month"], ev["lunar_day"],
                bool(ev["is_leap"]), base_date
            )
            ev["next_date"] = next_d.isoformat() if next_d else None
            ev["lunar_str"] = f"农历{ev['lunar_month']}月{ev['lunar_day']}日"
        else:
            # 公历循环
            next_d = _next_solar_anniversary(ev_date, base_date)
            ev["next_date"] = next_d.isoformat() if next_d else None

        if next_d:
            ev["days_remaining"] = days_until(next_d, base_date)
            ev["is_today"] = (next_d == base_date)
            ev["age"] = next_d.year - ev_date.year  # 第几个生日/周年
        else:
            ev["days_remaining"] = None
            ev["is_today"] = False
            ev["age"] = None
        ev["days_passed"] = None

    else:
        # 普通倒数日
        ev["days_remaining"] = days_until(ev_date, base_date)
        ev["days_passed"] = days_since(ev_date, base_date)
        ev["is_today"] = (ev_date == base_date)
        ev["next_date"] = None
        ev["age"] = None

    return ev


def _next_solar_anniversary(orig: date, base: date) -> date:
    """计算公历循环事件的下一个周年日"""
    for y in range(base.year, base.year + 2):
        try:
            d = date(y, orig.month, orig.day)
            if d >= base:
                return d
        except ValueError:
            # 2月29日非闰年取2月28日
            if orig.month == 2 and orig.day == 29:
                d = date(y, 2, 28)
                if d >= base:
                    return d
    return None


def get_today_events(base_date: date = None) -> list:
    """获取今天到期的事件"""
    if base_date is None:
        base_date = date.today()
    all_events = list_events()
    today_list = []
    for ev in all_events:
        ev = compute_event(ev, base_date)
        if ev.get("is_today"):
            today_list.append(ev)
    return today_list


def get_upcoming_events(days: int = 7, base_date: date = None) -> list:
    """获取未来 N 天内的事件"""
    if base_date is None:
        base_date = date.today()
    all_events = list_events()
    upcoming = []
    for ev in all_events:
        ev = compute_event(ev, base_date)
        dr = ev.get("days_remaining")
        if dr is not None and 0 <= dr <= days:
            upcoming.append(ev)
    upcoming.sort(key=lambda x: x.get("days_remaining", 9999))
    return upcoming


def get_dashboard_data(base_date: date = None) -> dict:
    """获取完整看板数据（前端主页 + API 用）"""
    from lunar_engine import (
        year_progress, month_progress, life_progress,
        solar_to_lunar, get_today_solar_term, get_shengxiao, get_ganzhi
    )
    if base_date is None:
        base_date = date.today()

    all_events = list_events()
    computed = [compute_event(ev, base_date) for ev in all_events]

    # 分类
    countdown_list = [e for e in computed if e["event_type"] == "countdown"]
    accumulate_list = [e for e in computed if e["event_type"] == "accumulate"]
    recurring_list = [e for e in computed if e["event_type"] == "recurring" or e["is_recurring"]]

    # 排序
    countdown_list.sort(key=lambda x: (not x["is_pinned"], x.get("days_remaining", 9999)))
    recurring_list.sort(key=lambda x: (not x["is_pinned"], x.get("days_remaining", 9999)))
    accumulate_list.sort(key=lambda x: (not x["is_pinned"], -x.get("days_passed", 0)))

    # 今日
    today_events = [e for e in computed if e.get("is_today")]

    return {
        "date": base_date.isoformat(),
        "lunar": solar_to_lunar(base_date),
        "shengxiao": get_shengxiao(base_date.year),
        "ganzhi": get_ganzhi(base_date.year),
        "solar_term": get_today_solar_term(base_date),
        "year_progress": year_progress(base_date),
        "month_progress": month_progress(base_date),
        "today_events": today_events,
        "countdown": countdown_list,
        "accumulate": accumulate_list,
        "recurring": recurring_list,
        "all_events": computed,
        "categories": CATEGORIES,
    }


# ========== 设置 ==========

def get_setting(key: str, default=None):
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key: str, value: str):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


# ========== 导入导出与备份 ==========

def export_data() -> dict:
    """导出全部数据为 JSON"""
    events = list_events(active_only=False)
    return {"events": events, "exported_at": datetime.now().isoformat()}


def import_data(data: dict, replace: bool = False) -> int:
    """从 JSON 导入数据"""
    if replace:
        conn = get_db()
        conn.execute("DELETE FROM events")
        conn.commit()
        conn.close()
    count = 0
    for ev in data.get("events", []):
        try:
            create_event(ev)
            count += 1
        except Exception as e:
            print(f"[IMPORT] 跳过失败项: {e}")
    return count


def backup_database(max_backups: int = 30) -> dict | None:
    """自动备份数据库和 JSON 导出文件至 data/backup 目录，保留最近 N 份备份"""
    import shutil
    import glob
    backup_dir = os.path.join(Config.DATA_DIR, "backup")
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    db_backup_path = os.path.join(backup_dir, f"dayshub_{ts}.db")
    json_backup_path = os.path.join(backup_dir, f"dayshub_{ts}.json")

    try:
        # 1. 备份 SQLite 文件 (使用 VACUUM INTO 或安全拷贝)
        if os.path.exists(Config.DB_PATH):
            conn = get_db()
            try:
                conn.execute(f"VACUUM INTO '{db_backup_path}'")
            except Exception:
                shutil.copy2(Config.DB_PATH, db_backup_path)
            finally:
                conn.close()

        # 2. 备份 JSON
        data = export_data()
        with open(json_backup_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # 3. 轮转清理旧备份
        db_files = sorted(glob.glob(os.path.join(backup_dir, "dayshub_*.db")))
        if len(db_files) > max_backups:
            for old_f in db_files[:-max_backups]:
                try:
                    os.remove(old_f)
                    json_f = old_f.replace(".db", ".json")
                    if os.path.exists(json_f):
                        os.remove(json_f)
                except Exception:
                    pass

        return {"status": "ok", "db": db_backup_path, "json": json_backup_path}
    except Exception as e:
        print(f"[BACKUP] 备份失败: {e}")
        return None


def cleanup_old_logs(retention_days: int = 90) -> int:
    """清理 N 天前的通知日志记录"""
    from datetime import timedelta
    cutoff = (date.today() - timedelta(days=retention_days)).isoformat()
    conn = get_db()
    cur = conn.execute("DELETE FROM notification_log WHERE notify_date < ?", (cutoff,))
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    return deleted


# ========== 示例数据 ==========

def seed_example_data():
    """首次启动加载示例数据（基于用户截图）"""
    from datetime import date as D
    examples = [
        # 循环事件 — 农历生日
        {"title": "母亲生日", "event_type": "recurring", "category": "family",
         "date": "1965-10-15", "lunar_month": 9, "lunar_day": 10, "is_recurring": 1,
         "note": "记得提前订鲜花和蛋糕", "is_pinned": 1},
        {"title": "父亲生日", "event_type": "recurring", "category": "family",
         "date": "1963-08-20", "lunar_month": 7, "lunar_day": 2, "is_recurring": 1,
         "note": ""},
        {"title": "刘鑫生日", "event_type": "recurring", "category": "family",
         "date": "1995-11-28", "lunar_month": 11, "lunar_day": 12, "is_recurring": 1,
         "note": ""},
        # 循环事件 — 公历
        {"title": "结婚纪念日", "event_type": "recurring", "category": "anniversary",
         "date": "2020-05-20", "is_recurring": 1, "note": "每年5月20日", "is_pinned": 1},
        {"title": "新年", "event_type": "recurring", "category": "holiday",
         "date": "2026-01-01", "is_recurring": 1, "note": "元旦"},
        # 累计事件
        {"title": "润润出生日", "event_type": "accumulate", "category": "family",
         "date": "2026-03-21", "note": "宝宝出生", "is_pinned": 1},
        {"title": "学习缠论", "event_type": "accumulate", "category": "habit",
         "date": "2024-10-26", "note": "开始学习缠论"},
        # 倒数事件
        {"title": "春节", "event_type": "recurring", "category": "holiday",
         "date": "2027-02-06", "lunar_month": 1, "lunar_day": 1, "is_recurring": 1,
         "note": "农历正月初一"},
    ]
    for ev in examples:
        create_event(ev)
    print(f"[SEED] 已加载 {len(examples)} 条示例数据")


# ========== 事件历史 ==========

def _log_history(conn, eid: int, action: str, old_data: dict | None, new_data: dict | None):
    """记录事件变更历史"""
    old_json = json.dumps(old_data, ensure_ascii=False, default=str) if old_data else None
    new_json = json.dumps(new_data, ensure_ascii=False, default=str) if new_data else None
    conn.execute(
        "INSERT INTO event_history (event_id, action, old_data, new_data) VALUES (?,?,?,?)",
        (eid, action, old_json, new_json)
    )


def get_event_history(eid: int) -> list:
    """获取事件变更历史"""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM event_history WHERE event_id = ? ORDER BY changed_at DESC",
        (eid,)
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        item = dict(r)
        if item.get("old_data"):
            try:
                item["old_data"] = json.loads(item["old_data"])
            except Exception:
                pass
        if item.get("new_data"):
            try:
                item["new_data"] = json.loads(item["new_data"])
            except Exception:
                pass
        result.append(item)
    return result