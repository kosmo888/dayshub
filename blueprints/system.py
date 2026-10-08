"""
DaysHub 基础系统与外设生态蓝图 v2.0.0
- Web 前端页面主入口 (/)、大屏看板视图 (/board)、健康检查与 PWA Manifest
- 系统公开元数据、通知推送配置 (WeCom/SMTP/Telegram) 与手动检测
- 数据库在线热备份管理与快照文件下载
- iCal 日历规范订阅生成与多用户独立 Token
"""
import os
import glob
from flask import (
    Blueprint, request, jsonify, render_template, Response,
    send_from_directory, g, current_app
)
from config import Config, VERSION
from auth_middleware import require_auth, require_admin, log_action
from logger import logger
from calendar_gen import generate_ics

system_bp = Blueprint("system", __name__)


# ========== 页面与前端静态支持 ==========

@system_bp.route("/")
def index():
    """主页看板"""
    return render_template("index.html", version=VERSION, board_mode=False)


@system_bp.route("/board")
def board():
    """大屏全屏看板模式"""
    return render_template("index.html", version=VERSION, board_mode=True)


@system_bp.route("/manifest.json")
def manifest():
    """PWA 清单文件"""
    return jsonify({
        "name": "DaysHub · 时光看板",
        "short_name": "DaysHub",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#667eea",
        "icons": [
            {
                "src": "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📅</text></svg>",
                "sizes": "192x192 512x512",
                "type": "image/svg+xml"
            }
        ]
    })


@system_bp.route("/health")
def health():
    """服务健康检查接口"""
    return jsonify({"status": "ok", "app": "DaysHub", "version": VERSION})


@system_bp.route("/api/system/public-info", methods=["GET"])
def api_public_info():
    """获取公开系统配置（是否开放访客注册）"""
    from config import is_registration_allowed
    return jsonify({
        "ok": True,
        "allow_registration": is_registration_allowed(),
        "version": VERSION
    })


# ========== 推送与通知设置 ==========

@system_bp.route("/api/settings/push", methods=["GET"])
@require_auth
def api_get_push_settings():
    """获取推送通道配置（脱敏密码）"""
    from config import load_push_config
    cfg = load_push_config()
    safe = dict(cfg)
    if safe.get("smtp_pass"):
        safe["smtp_pass"] = "******"
    return jsonify(safe)


@system_bp.route("/api/settings/push", methods=["PUT"])
@require_auth
def api_save_push_settings():
    """更新推送通道配置"""
    from config import save_push_config, load_push_config
    data = request.get_json() or {}
    if data.get("smtp_pass") == "******":
        data.pop("smtp_pass")
    save_push_config(data)
    log_action("push_config", "system", "修改系统推送配置")
    new_cfg = load_push_config()
    safe = dict(new_cfg)
    if safe.get("smtp_pass"):
        safe["smtp_pass"] = "******"
    return jsonify({"ok": True, "config": safe})


@system_bp.route("/api/notify/test", methods=["POST"])
@require_auth
def api_notify_test():
    """触发测试通知推送"""
    from notifier import test_push
    results = test_push()
    all_ok = all(v for v in results.values() if v is not None)
    msgs = []
    for channel, status in results.items():
        if status is True:
            msgs.append(f"✅ {channel}: 成功")
        elif status is False:
            msgs.append(f"❌ {channel}: 失败")
    if not msgs:
        log_action("push_test", "system", "触发测试推送: 未配置任何有效通道", status="fail")
        return jsonify({"ok": False, "msg": "未配置任何推送通道，请先在推送设置中配置"})
    log_action("push_test", "system", f"触发测试推送: {'; '.join(msgs)}", status="ok" if all_ok else "fail")
    if all_ok:
        return jsonify({"ok": True, "msg": "\n".join(msgs)})
    return jsonify({"ok": False, "msg": "\n".join(msgs)}), 500


@system_bp.route("/api/notify/check", methods=["POST"])
@require_auth
def api_notify_check():
    """手动扫描并触发当日到期与提前提醒"""
    from notifier import check_and_notify
    check_and_notify()
    log_action("notify_check", "system", "手动触发提醒检查扫描")
    return jsonify({"ok": True, "msg": "提醒检查完成"})


# ========== 数据备份与热备份文件下载 ==========

@system_bp.route("/api/backup", methods=["POST"])
@require_auth
def api_backup():
    """手动执行全量数据库与 JSON 快照在线热备份"""
    from models import backup_database
    from config import load_backup_config
    cfg = load_backup_config()
    max_b = int(cfg.get("backup_count", 30))
    btype = str(cfg.get("backup_type", "both"))
    res = backup_database(max_backups=max_b, backup_type=btype)
    if res:
        log_action("backup_create", "system", f"创建数据库热备份: {res.get('filename')}")
        return jsonify({"ok": True, "msg": "全量备份创建完成", "data": res})
    log_action("backup_create", "system", "数据库热备份失败", status="fail")
    return jsonify({"ok": False, "msg": "备份失败"}), 500


@system_bp.route("/api/settings/backup", methods=["GET"])
@require_auth
def api_get_backup_settings():
    """获取定时备份配置"""
    from config import load_backup_config
    return jsonify({"ok": True, "config": load_backup_config()})


@system_bp.route("/api/settings/backup", methods=["PUT"])
@require_auth
def api_save_backup_settings():
    """保存定时备份配置并重新调度定时器"""
    from config import save_backup_config, load_backup_config
    data = request.get_json() or {}
    save_backup_config(data)
    interval = data.get("backup_interval_days", 1)
    log_action("backup_config", "system", f"修改定时备份策略配置 (保留份数: {data.get('backup_count', 30)}, 时间: {data.get('backup_time', '03:00')}, 间隔: 每{interval}天一次)")
    try:
        from scheduler import reschedule_backup
        reschedule_backup(current_app)
    except Exception as e:
        logger.warning(f"重新调度备份任务失败: {e}")
    return jsonify({"ok": True, "config": load_backup_config(), "msg": "备份配置已保存"})


@system_bp.route("/api/backup/list", methods=["GET"])
@require_admin
def api_backup_list():
    """获取历史快照备份文件列表"""
    backup_dir = os.path.join(Config.DATA_DIR, "backup")
    os.makedirs(backup_dir, exist_ok=True)
    files = []
    for f in glob.glob(os.path.join(backup_dir, "*.*")):
        fname = os.path.basename(f)
        try:
            sz = os.path.getsize(f)
            mtime = os.path.getmtime(f)
            files.append({
                "filename": fname,
                "size": sz,
                "created_at": mtime,
                "is_db": fname.endswith(".db"),
                "is_json": fname.endswith(".json")
            })
        except Exception:
            pass
    files.sort(key=lambda x: x["created_at"], reverse=True)
    return jsonify({"ok": True, "files": files})


@system_bp.route("/api/backup/download/<path:filename>", methods=["GET"])
@require_admin
def api_backup_download(filename):
    """安全下载指定的备份历史文件"""
    backup_dir = os.path.join(Config.DATA_DIR, "backup")
    clean_name = os.path.basename(filename)
    full_path = os.path.join(backup_dir, clean_name)
    if not os.path.exists(full_path):
        return jsonify({"ok": False, "error": "文件不存在"}), 404
    return send_from_directory(backup_dir, clean_name, as_attachment=True)


# ========== iCal 订阅管理与导出 ==========

@system_bp.route("/api/settings/ical_token", methods=["GET"])
@require_auth
def api_get_ical_token():
    """获取当前用户的专属 iCal 订阅 Token"""
    from config import get_ical_token
    user = getattr(g, "current_user", None)
    uid = user["id"] if user else None
    return jsonify({"ok": True, "token": get_ical_token(uid)})


@system_bp.route("/api/settings/ical_token/reset", methods=["POST"])
@require_auth
def api_reset_ical_token():
    """重置当前用户的专属 iCal 订阅 Token"""
    from config import reset_ical_token
    user = getattr(g, "current_user", None)
    uid = user["id"] if user else None
    new_token = reset_ical_token(uid)
    return jsonify({"ok": True, "token": new_token, "msg": "专属日历订阅 Token 已重置"})


@system_bp.route("/api/calendar.ics")
@system_bp.route("/ical/events.ics")
def api_ics():
    """输出 RFC-5545 标准 iCal 日历订阅流"""
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
