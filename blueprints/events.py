"""
DaysHub 事件管理与数据导入导出蓝图 v2.0.0
- 事件列表查询、高级搜索、即将到来事件
- 事件增删改查 CRUD、历史追溯与时间线里程碑
- JSON 全量导出与增量/覆盖导入
"""
from flask import Blueprint, request, jsonify, g
from auth_middleware import require_auth, log_action
from logger import logger
from models import (
    create_event, get_event, list_events, update_event, delete_event,
    compute_event, get_upcoming_events, get_event_history,
    export_data, import_data, get_all_categories, save_category, delete_category
)

events_bp = Blueprint("events", __name__)


@events_bp.route("/api/events", methods=["GET"])
@require_auth
def api_list_events():
    """获取事件列表（带用户严格数据隔离）"""
    user = getattr(g, "current_user", None)
    uid = user["id"] if user and user.get("role") != "admin" else None
    events = list_events(active_only=False, user_id=uid)
    return jsonify([compute_event(ev) for ev in events])


@events_bp.route("/api/events/search", methods=["GET"])
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


@events_bp.route("/api/upcoming", methods=["GET"])
@require_auth
def api_upcoming():
    """获取即将到来的事件"""
    try:
        days = int(request.args.get("days", 7))
    except (ValueError, TypeError):
        days = 7
    return jsonify(get_upcoming_events(days))


@events_bp.route("/api/events/<int:eid>/timeline", methods=["GET"])
@events_bp.route("/api/events/<int:eid>/history", methods=["GET"])
@require_auth
def api_event_timeline(eid):
    """事件历史时间线与里程碑"""
    ev = get_event(eid)
    if not ev:
        return jsonify({"error": "事件不存在"}), 404
    history = get_event_history(eid)
    milestones = ev.get("milestones", [])
    return jsonify({"event": ev, "history": history, "milestones": milestones})


@events_bp.route("/api/categories", methods=["GET"])
@require_auth
def api_categories():
    """获取所有可用分类字典"""
    return jsonify(get_all_categories())


@events_bp.route("/api/categories", methods=["POST", "PUT"])
@require_auth
def api_save_category():
    """新增或修改分类"""
    data = request.get_json() or {}
    slug = str(data.get("slug", "")).strip().lower()
    name = str(data.get("name", "")).strip()
    color = str(data.get("color", "#6366f1")).strip()
    icon = str(data.get("icon", "📌")).strip()
    try:
        sort_order = int(data.get("sort_order", 0))
    except (ValueError, TypeError):
        sort_order = 0

    if not slug or not name:
        return jsonify({"ok": False, "error": "分类标识(slug)和显示名称不能为空"}), 400

    cats = save_category(slug, name, color, icon, sort_order)
    log_action("category_save", "category", f"保存分类: {name} ({slug})")
    return jsonify({"ok": True, "categories": cats, "msg": f"分类「{name}」已保存"})


@events_bp.route("/api/categories/<slug>", methods=["DELETE"])
@require_auth
def api_delete_category(slug):
    """删除分类"""
    slug = str(slug).strip().lower()
    ok, msg = delete_category(slug)
    if not ok:
        return jsonify({"ok": False, "error": msg}), 400
    log_action("category_delete", "category", f"删除分类: {slug}")
    return jsonify({"ok": True, "categories": get_all_categories(), "msg": msg})


@events_bp.route("/api/export", methods=["GET"])
@require_auth
def api_export():
    """导出事件数据（用户数据隔离）"""
    user = getattr(g, "current_user", None)
    uid = user["id"] if user and user.get("role") != "admin" else None
    res_data = export_data(user_id=uid)
    log_action("export", "event", f"导出数据备份: 共 {len(res_data.get('events', []))} 条事件")
    return jsonify(res_data)


@events_bp.route("/api/events", methods=["POST"])
@require_auth
def api_create_event():
    """创建新事件"""
    data = request.get_json()
    if not data or not data.get("title") or not data.get("date"):
        return jsonify({"error": "title 和 date 为必填"}), 400
    cur_user = getattr(g, "current_user", None)
    uid = cur_user["id"] if cur_user else 1
    ev = create_event(data, user_id=uid)
    if not ev:
        return jsonify({"error": "创建失败"}), 500
    logger.info(f"事件创建: {ev['title']} (id={ev['id']})")
    log_action("event_create", "event", f"创建事件: {ev['title']} (ID: {ev['id']})")
    from notifier import send_webhook
    send_webhook("event_created", ev)
    return jsonify(ev), 201


@events_bp.route("/api/events/<int:eid>", methods=["PUT"])
@require_auth
def api_update_event(eid):
    """更新事件"""
    data = request.get_json()
    ev_existing = get_event(eid, compute=False)
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
    log_action("event_update", "event", f"更新事件: {ev['title']} (ID: {ev['id']})")
    from notifier import send_webhook
    send_webhook("event_updated", ev)
    return jsonify(ev)


@events_bp.route("/api/events/<int:eid>", methods=["DELETE"])
@require_auth
def api_delete_event(eid):
    """删除事件"""
    ev_existing = get_event(eid, compute=False)
    if not ev_existing:
        return jsonify({"error": "事件不存在"}), 404
    user = getattr(g, "current_user", None)
    if user and user.get("role") != "admin":
        if ev_existing.get("user_id") is not None and ev_existing.get("user_id") != user.get("id"):
            return jsonify({"error": "无权删除其他用户的事件"}), 403
    ev_title = ev_existing.get("title", f"ID {eid}")
    if delete_event(eid):
        logger.info(f"事件删除: id={eid}")
        log_action("event_delete", "event", f"删除事件: {ev_title} (ID: {eid})")
        from notifier import send_webhook
        send_webhook("event_deleted", {"id": eid})
        return jsonify({"ok": True})
    return jsonify({"error": "删除失败"}), 500


@events_bp.route("/api/import", methods=["POST"])
@require_auth
def api_import():
    """导入事件数据（兼容纯数组及标准 dict 封装）"""
    data = request.get_json()
    replace = request.args.get("replace", "false").lower() in ("true", "1")
    user = getattr(g, "current_user", None)
    uid = user["id"] if user and user.get("role") != "admin" else None
    count = import_data(data, replace, user_id=uid)
    logger.info(f"数据导入: {count} 条 (replace={replace}, user_id={uid})")
    log_action("import", "event", f"导入数据: 共 {count} 条 (覆盖原有={replace})")
    return jsonify({"imported": count})
