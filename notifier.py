"""
DaysHub 通知推送模块 v1.3.0
- 企业微信 Webhook
- SMTP 邮件推送（HTML + 纯文本回退）
- Telegram Bot
- 通用自定义 Webhook
- 事件级提醒推送 + 重试机制
"""
import smtplib
import requests
import json
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date
from config import Config, load_push_config
from logger import logger


# ========== 推送重试 ==========

def _retry(fn, max_attempts=None, delay=None):
    """通用重试包装"""
    if max_attempts is None:
        max_attempts = Config.PUSH_RETRY_COUNT
    if delay is None:
        delay = Config.PUSH_RETRY_DELAY
    last_err = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as e:
            last_err = e
            logger.warning(f"推送重试 {attempt}/{max_attempts}: {e}")
            if attempt < max_attempts:
                time.sleep(delay)
    logger.error(f"推送失败（已重试 {max_attempts} 次）: {last_err}")
    return False


# ========== 邮件发送（HTML + 纯文本回退） ==========

def send_email(subject: str, html_body: str, text_body: str = None, to_addrs: list = None) -> bool:
    """发送邮件（HTML + 纯文本回退）"""
    cfg = load_push_config()
    if not (cfg["smtp_host"] and cfg["smtp_user"] and cfg["smtp_pass"] and cfg["smtp_to"]):
        logger.debug("邮件未配置，跳过")
        return False
    if to_addrs is None:
        to_addrs = [t.strip() for t in cfg["smtp_to"].split(",") if t.strip()]

    if text_body is None:
        text_body = "请使用支持 HTML 的邮件客户端查看此邮件。"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg["smtp_from"] or cfg["smtp_user"]
    msg["To"] = ", ".join(to_addrs)
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    smtp_host = cfg["smtp_host"]
    smtp_port = int(cfg["smtp_port"])
    smtp_user = cfg["smtp_user"]
    smtp_pass = cfg["smtp_pass"]
    use_ssl = cfg["smtp_ssl"].lower() == "true"
    smtp_from = cfg["smtp_from"] or cfg["smtp_user"]

    def _send():
        if use_ssl:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
            server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_from, to_addrs, msg.as_string())
        server.quit()
        return True

    ok = _retry(_send)
    if ok:
        logger.info(f"邮件发送成功 -> {to_addrs}")
    else:
        logger.error(f"邮件发送失败（已重试）-> {to_addrs}")
    return bool(ok)


# ========== 企业微信 Webhook ==========

def send_wecom(text: str) -> bool:
    cfg = load_push_config()
    webhook = cfg["wecom_webhook"]
    if not webhook:
        return False
    def _send():
        resp = requests.post(webhook, json={
            "msgtype": "text", "text": {"content": text}
        }, timeout=10)
        if resp.status_code != 200:
            raise Exception(f"HTTP {resp.status_code}")
        return True
    ok = _retry(_send)
    if ok:
        logger.info("企业微信推送成功")
    else:
        logger.error("企业微信推送失败（已重试）")
    return bool(ok)


# ========== Telegram Bot ==========

def send_telegram(text: str) -> bool:
    cfg = load_push_config()
    token = cfg["tg_bot_token"]
    chat_id = cfg["tg_chat_id"]
    if not (token and chat_id):
        return False
    def _send():
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        resp = requests.post(url, json={
            "chat_id": chat_id, "text": text, "parse_mode": "HTML",
        }, timeout=10)
        if resp.status_code != 200:
            raise Exception(f"HTTP {resp.status_code}")
        return True
    ok = _retry(_send)
    if ok:
        logger.info("Telegram 推送成功")
    else:
        logger.error("Telegram 推送失败（已重试）")
    return bool(ok)


# ========== 通用自定义 Webhook ==========

def send_webhook(event_type: str, payload: dict) -> bool:
    cfg = load_push_config()
    urls_raw = cfg["custom_webhook_urls"]
    if not urls_raw:
        return False
    allowed_events = [e.strip() for e in cfg["custom_webhook_events"].split(",")]
    if event_type not in allowed_events:
        return False

    from datetime import datetime
    envelope = {
        "source": "dayshub",
        "event_type": event_type,
        "timestamp": datetime.now().isoformat(),
        "data": payload,
    }
    headers = {"Content-Type": "application/json"}
    headers_raw = cfg["custom_webhook_headers"]
    if headers_raw:
        try:
            headers.update(json.loads(headers_raw))
        except Exception:
            pass

    urls = [u.strip() for u in urls_raw.split(",") if u.strip()]
    success = True
    for url in urls:
        def _send(u=url):
            resp = requests.post(u, json=envelope, headers=headers, timeout=15)
            if resp.status_code >= 400:
                raise Exception(f"HTTP {resp.status_code}")
            return True
        ok = _retry(_send)
        if ok:
            logger.info(f"Webhook 推送成功: {event_type} -> {url[:60]}...")
        else:
            logger.error(f"Webhook 推送失败（已重试）: {event_type} -> {url[:60]}...")
            success = False
    return success


# ========== 推送测试 ==========

def test_push() -> dict:
    """测试推送各通道是否可用，返回各通道结果 (True/False/None)"""
    results: dict[str, bool | None] = {"企业微信": None, "邮件": None, "Telegram": None, "Webhook": None}
    cfg = load_push_config()

    # 企业微信
    if cfg["wecom_webhook"]:
        try:
            resp = requests.post(cfg["wecom_webhook"], json={
                "msgtype": "text", "text": {"content": "📅 DaysHub 推送测试 — 通道配置正常！"}
            }, timeout=10)
            results["企业微信"] = (resp.status_code == 200)
        except Exception as e:
            logger.warning(f"企业微信测试失败: {e}")
            results["企业微信"] = False

    # 邮件
    if cfg["smtp_host"] and cfg["smtp_user"] and cfg["smtp_pass"] and cfg["smtp_to"]:
        try:
            html = """
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 500px; margin: 0 auto; padding: 20px; border: 1px solid #e8e8e8; border-radius: 12px;">
                <h2 style="color: #667eea; margin-top: 0;">📅 DaysHub 推送测试</h2>
                <p style="color: #333; font-size: 15px;">如果您收到此邮件，说明 DaysHub 邮件 SMTP 通道配置完全正常！</p>
                <div style="font-size: 12px; color: #888; border-top: 1px solid #eee; padding-top: 10px; margin-top: 20px;">DaysHub 时光看板</div>
            </div>
            """
            results["邮件"] = send_email("📅 DaysHub 推送测试", html, "DaysHub 推送测试 — 邮件通道配置正常！")
        except Exception as e:
            logger.warning(f"邮件测试失败: {e}")
            results["邮件"] = False

    # Telegram
    if cfg["tg_bot_token"] and cfg["tg_chat_id"]:
        try:
            results["Telegram"] = send_telegram("📅 <b>DaysHub 推送测试</b> — Telegram 通道配置正常！")
        except Exception as e:
            logger.warning(f"Telegram 测试失败: {e}")
            results["Telegram"] = False

    # Webhook
    if cfg["custom_webhook_urls"]:
        try:
            results["Webhook"] = send_webhook("test", {"msg": "DaysHub 推送测试"})
        except Exception as e:
            logger.warning(f"Webhook 测试失败: {e}")
            results["Webhook"] = False

    return results


# ========== 提醒消息排版与推送 ==========

def build_reminder_text(to_notify: list, today: date) -> str:
    """构建提醒消息文本（美化版）"""
    lines = [f"🔔 DaysHub 纪念日提醒\n{'─' * 26}"]
    for ev, adv in to_notify:
        icon = ev.get("icon") or "📌"
        if ev.get("event_type") == "accumulate":
            lines.append(f"\n🏆「{ev['title']}」已达成 {adv} 天里程碑！")
            lines.append(f"   {icon} 起始日期：{ev.get('date')}")
        elif adv == 0:
            lines.append(f"\n🎉 今天就是「{ev['title']}」！")
        else:
            lines.append(f"\n⏳ 还有 {adv} 天就是「{ev['title']}」")

        if ev.get("event_type") != "accumulate":
            if ev.get("lunar_str"):
                lines.append(f"   {icon} 农历：{ev['lunar_str']}（公历 {ev.get('next_date', '?')}）")
            elif ev.get("next_date"):
                lines.append(f"   {icon} 公历：{ev['next_date']}")
            else:
                lines.append(f"   {icon} 日期：{ev['date']}")

        if ev.get("note"):
            lines.append(f"   📝 备注：{ev['note']}")
    lines.append(f"\n{'─' * 26}")
    lines.append(f"📅 日期：{today.isoformat()} · DaysHub")
    return "\n".join(lines)


def build_reminder_html(to_notify: list, today: date) -> str:
    """构建提醒邮件 HTML 模板"""
    items_html = ""
    for ev, adv in to_notify:
        color = ev.get("color") or "#667eea"
        icon = ev.get("icon") or "📌"
        if ev.get("event_type") == "accumulate":
            badge = f"🏆 {adv} 天里程碑！"
            sub = f"起始日期：{ev.get('date')}"
        elif adv == 0:
            badge = "🎉 今天！"
            sub = f"农历：{ev['lunar_str']} (公历 {ev.get('next_date','?')})" if ev.get("lunar_str") else f"公历：{ev.get('next_date') or ev['date']}"
        else:
            badge = f"还有 {adv} 天"
            sub = f"农历：{ev['lunar_str']} (公历 {ev.get('next_date','?')})" if ev.get("lunar_str") else f"公历：{ev.get('next_date') or ev['date']}"

        note_div = f"<div style='font-size:13px;color:#666;margin-top:4px;'>📝 {ev['note']}</div>" if ev.get("note") else ""
        items_html += f"""
        <div style="background:#f9fafb; border-left: 4px solid {color}; border-radius: 8px; padding: 12px 16px; margin-bottom: 12px;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="font-size:16px; font-weight:600; color:#1a1a2e;">{icon} {ev['title']}</span>
                <span style="background:{color}; color:#fff; font-size:12px; font-weight:bold; padding:2px 8px; border-radius:10px;">{badge}</span>
            </div>
            <div style="font-size:13px; color:#555; margin-top:4px;">📅 {sub}</div>
            {note_div}
        </div>
        """
    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 520px; margin: 0 auto; padding: 20px; background: #ffffff; border: 1px solid #e8e8e8; border-radius: 12px;">
        <h2 style="color: #667eea; margin-top: 0; font-size: 20px;">🔔 DaysHub 纪念日提醒</h2>
        <p style="font-size: 13px; color: #888; margin-bottom: 16px;">日期：{today.isoformat()}</p>
        {items_html}
        <div style="text-align: center; font-size: 12px; color: #aaa; margin-top: 20px; border-top: 1px solid #eee; padding-top: 12px;">
            DaysHub 时光看板
        </div>
    </div>
    """


def check_and_notify():
    """检查需要提醒的事件并发送通知（支持倒数/循环事件提前提醒及累计事件里程碑提醒）"""
    from models import list_events, compute_event, get_db
    today = date.today()
    events = list_events()
    to_notify = []
    ACCUMULATE_MILESTONES = {100, 200, 300, 500, 1000, 1500, 2000, 3000, 5000, 10000}

    for ev in events:
        ev = compute_event(ev, today)

        # 1. 倒数日 / 循环日
        if ev["event_type"] in ("countdown", "recurring"):
            dr = ev.get("days_remaining")
            ev_advance = ev.get("advance_days")
            if ev_advance is None:
                ev_advance = 3
            advance_list = [0] + ([ev_advance] if ev_advance > 0 else [])
            if dr is not None and dr in advance_list:
                conn = get_db()
                already = conn.execute(
                    "SELECT 1 FROM notification_log WHERE event_id=? AND notify_date=? AND advance_days=?",
                    (ev["id"], today.isoformat(), dr)
                ).fetchone()
                conn.close()
                if not already:
                    to_notify.append((ev, dr))

        # 2. 累计日里程碑提醒 (100/200/500/1000天等)
        elif ev["event_type"] == "accumulate":
            dp = ev.get("days_passed")
            if dp is not None and dp in ACCUMULATE_MILESTONES:
                conn = get_db()
                already = conn.execute(
                    "SELECT 1 FROM notification_log WHERE event_id=? AND notify_date=? AND advance_days=?",
                    (ev["id"], today.isoformat(), dp)
                ).fetchone()
                conn.close()
                if not already:
                    to_notify.append((ev, dp))

    if not to_notify:
        logger.debug("今日无需提醒")
        return

    text = build_reminder_text(to_notify, today)
    html = build_reminder_html(to_notify, today)
    logger.info(f"需提醒 {len(to_notify)} 个事件")

    # 4 通道推送
    send_wecom(text)
    send_telegram(text)
    send_email(f"🔔 DaysHub 纪念日提醒 ({today.isoformat()})", html, text)
    send_webhook("reminder", {
        "date": today.isoformat(),
        "events": [
            {"title": ev["title"], "advance_days": adv, "is_today": adv == 0,
             "event_type": ev["event_type"],
             "next_date": ev.get("next_date"), "lunar_str": ev.get("lunar_str"), "note": ev.get("note", "")}
            for ev, adv in to_notify
        ],
    })

    conn = get_db()
    for ev, adv in to_notify:
        conn.execute(
            "INSERT INTO notification_log (event_id, notify_date, advance_days, channel, status) VALUES (?,?,?,?,?)",
            (ev["id"], today.isoformat(), adv, "all", "sent")
        )
    conn.commit()
    conn.close()