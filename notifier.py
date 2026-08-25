"""
DaysHub 通知推送模块 v1.1.0
- SMTP 邮件推送（HTML + 纯文本回退）
- 企业微信 Webhook
- Telegram Bot
- 通用自定义 Webhook
- 多级预警（提前 7/3/1/0 天）
- 推送失败重试 + 告警日志
- 每日一言
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
from models import get_dashboard_data, get_today_events, get_upcoming_events

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

# ========== 每日一言 ==========
DAILY_QUOTES = [
    "时间是最好的老师，可惜它杀死了所有的学生。",
    "不要为已消尽之年华叹息，必须正视匆匆溜走的时光。",
    "今天是余生中最年轻的一天。",
    "种一棵树最好的时间是十年前，其次是现在。",
    "你不必每天都很厉害，只要每天都没放弃。",
    "时光不语，静待花开。",
    "生活不是等待暴风雨过去，而是学会在雨中跳舞。",
    "所有的美好都在路上，不急不躁。",
    "愿你有前进一寸的勇气，亦有后退一尺的从容。",
    "把每一天当作生命的第一天，也当作最后一天。",
    "岁月不居，时节如流。",
    "星光不问赶路人，时光不负有心人。",
    "愿你历尽千帆，归来仍是少年。",
    "时间会给出所有答案，如果还没有，那就再等等。",
    "做时间的朋友，而不是做时间的奴隶。",
]

def get_daily_quote(d: date = None) -> str:
    if d is None:
        d = date.today()
    idx = (d.year * 366 + d.month * 31 + d.day) % len(DAILY_QUOTES)
    return DAILY_QUOTES[idx]


# ========== 纯文本摘要（邮件回退用） ==========

def build_text_report(dash: dict) -> str:
    """构建纯文本晨报摘要"""
    today_str = dash["date"]
    lunar_str = dash["lunar"]["chinese_str"]
    lines = [f"DaysHub 晨报 | {today_str} {lunar_str}"]
    lines.append(f"今年已过 {dash['year_progress']['percent']}% · 本月 {dash['month_progress']['percent']}%")
    if dash["solar_term"]:
        lines.append(f"今日节气：{dash['solar_term']}")

    if dash["today_events"]:
        lines.append("\n今日纪念：")
        for ev in dash["today_events"]:
            age = f"（第{ev['age']}年）" if ev.get("age") else ""
            lines.append(f"  {ev['title']}{age}")
            if ev["note"]:
                lines.append(f"    备注: {ev['note']}")
    else:
        lines.append("\n今天没有纪念日")

    upcoming = get_upcoming_events(7)
    if upcoming:
        lines.append("\n近7天倒数：")
        for ev in upcoming:
            days = ev.get("days_remaining", 0)
            badge = "今天" if days == 0 else f"还有{days}天"
            lines.append(f"  {ev['title']} — {badge}")

    if dash["accumulate"]:
        lines.append("\n时光累计：")
        for ev in dash["accumulate"][:3]:
            lines.append(f"  {ev['title']} — 已{ev.get('days_passed',0)}天")

    lines.append(f"\n{get_daily_quote()}")
    return "\n".join(lines)


# ========== HTML 邮件模板 ==========

def build_html_report(dash: dict) -> str:
    today = dash["date"]
    lunar = dash["lunar"]["chinese_str"]
    yp = dash["year_progress"]
    mp = dash["month_progress"]
    quote = get_daily_quote()

    today_html = ""
    if dash["today_events"]:
        for ev in dash["today_events"]:
            today_html += f'<div class="event-today" style="border-left:4px solid {ev["color"]};">'
            today_html += f'<span class="ev-icon">{ev["icon"]}</span>'
            today_html += f'<span class="ev-title">{ev["title"]}</span>'
            if ev.get("age"):
                today_html += f'<span class="ev-age">第{ev["age"]}年</span>'
            if ev["note"]:
                today_html += f'<div class="ev-note">📝 {ev["note"]}</div>'
            today_html += '</div>'
    else:
        today_html = '<div class="no-event">今天没有纪念日，安静而美好的一天 ☕️</div>'

    upcoming = get_upcoming_events(30)
    upcoming_html = ""
    for ev in upcoming[:10]:
        days = ev.get("days_remaining", 0)
        badge = "🎉 今天" if days == 0 else f"还有 {days} 天"
        upcoming_html += f'<div class="upcoming-item" style="border-left:3px solid {ev["color"]};">'
        upcoming_html += f'<span class="ev-icon">{ev["icon"]}</span>'
        upcoming_html += f'<span class="ev-title">{ev["title"]}</span>'
        upcoming_html += f'<span class="ev-badge">{badge}</span>'
        upcoming_html += '</div>'
    if not upcoming:
        upcoming_html = '<div class="no-event">未来30天暂无事件</div>'

    accum_html = ""
    for ev in dash["accumulate"][:5]:
        days = ev.get("days_passed", 0)
        accum_html += f'<div class="accum-item" style="border-left:3px solid {ev["color"]};">'
        accum_html += f'<span class="ev-icon">{ev["icon"]}</span>'
        accum_html += f'<span class="ev-title">{ev["title"]}</span>'
        accum_html += f'<span class="ev-badge">已经 {days} 天</span>'
        accum_html += '</div>'

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body {{ font-family: -apple-system, "PingFang SC", "Helvetica Neue", sans-serif; background:#f5f5f5; margin:0; padding:20px; color:#333; }}
.container {{ max-width:600px; margin:0 auto; background:#fff; border-radius:16px; overflow:hidden; box-shadow:0 2px 12px rgba(0,0,0,0.08); }}
.header {{ background:linear-gradient(135deg,#667eea,#764ba2); color:#fff; padding:30px; text-align:center; }}
.header h1 {{ margin:0; font-size:24px; }}
.header .lunar {{ margin-top:8px; font-size:14px; opacity:0.85; }}
.header .term {{ margin-top:4px; font-size:13px; opacity:0.7; }}
.progress-bar {{ background:rgba(255,255,255,0.2); height:6px; border-radius:3px; margin:12px 0; overflow:hidden; }}
.progress-fill {{ background:#fff; height:100%; border-radius:3px; }}
.progress-text {{ font-size:12px; opacity:0.8; }}
.section {{ padding:20px 24px; }}
.section h2 {{ font-size:16px; color:#667eea; border-bottom:2px solid #f0f0f0; padding-bottom:8px; }}
.event-today {{ background:#fff8f0; border-radius:8px; padding:12px 16px; margin:8px 0; display:flex; align-items:center; flex-wrap:wrap; gap:8px; }}
.event-today .ev-icon {{ font-size:24px; }}
.event-today .ev-title {{ font-size:16px; font-weight:600; }}
.event-today .ev-age {{ font-size:12px; color:#888; background:#eee; padding:2px 8px; border-radius:10px; }}
.event-today .ev-note {{ width:100%; font-size:13px; color:#666; margin-top:4px; }}
.no-event {{ text-align:center; color:#999; padding:20px; font-size:14px; }}
.upcoming-item, .accum-item {{ display:flex; align-items:center; gap:8px; padding:8px 12px; margin:6px 0; border-radius:6px; background:#fafafa; }}
.upcoming-item .ev-icon, .accum-item .ev-icon {{ font-size:18px; }}
.upcoming-item .ev-title, .accum-item .ev-title {{ flex:1; font-size:14px; }}
.ev-badge {{ font-size:13px; color:#667eea; font-weight:600; }}
.quote {{ text-align:center; padding:24px; font-style:italic; color:#888; font-size:14px; border-top:1px solid #f0f0f0; }}
.footer {{ text-align:center; padding:16px; font-size:11px; color:#ccc; }}
</style></head><body>
<div class="container">
  <div class="header">
    <h1>📅 DaysHub 时光看板</h1>
    <div class="lunar">{today} · {lunar} · {dash["shengxiao"]}年{dash["ganzhi"]}</div>
    {f'<div class="term">🌿 今日节气：{dash["solar_term"]}</div>' if dash["solar_term"] else ''}
    <div class="progress-bar"><div class="progress-fill" style="width:{yp["percent"]}%"></div></div>
    <div class="progress-text">📊 今年已过 {yp["passed"]}/{yp["total"]} 天（{yp["percent"]}%） · 本月 {mp["percent"]}%</div>
  </div>
  <div class="section"><h2>🎯 今日纪念</h2>{today_html}</div>
  <div class="section"><h2>⏳ 近期倒数（30天内）</h2>{upcoming_html}</div>
  <div class="section"><h2>📈 时光累计</h2>{accum_html}</div>
  <div class="quote">「 {quote} 」</div>
  <div class="footer">DaysHub v1.1.0 · 时光看板 · {Config.BASE_URL}</div>
</div>
</body></html>"""


# ========== 邮件发送（HTML + 纯文本回退） ==========

def send_email(subject: str, html_body: str, text_body: str = None, to_addrs: list = None) -> bool:
    """发送邮件（HTML + 纯文本回退）"""
    cfg = load_push_config()
    if not (cfg["smtp_host"] and cfg["smtp_user"] and cfg["smtp_pass"] and cfg["smtp_to"]):
        logger.debug("邮件未配置，跳过")
        return False
    if to_addrs is None:
        to_addrs = [t.strip() for t in cfg["smtp_to"].split(",") if t.strip()]

    # 纯文本回退
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

    ok = _retry(_send)
    if ok:
        logger.info(f"邮件发送成功 -> {to_addrs}")
    else:
        logger.error(f"邮件发送失败（已重试）-> {to_addrs}")
    return ok


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
    return ok


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
    return ok


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


# ========== 综合晨报 ==========

def test_push():
    """测试推送各通道是否可用，返回各通道结果"""
    results = {"企业微信": None, "邮件": None, "Telegram": None, "Webhook": None}
    cfg = load_push_config()

    # 企业微信
    if cfg["wecom_webhook"]:
        try:
            resp = requests.post(cfg["wecom_webhook"], json={
                "msgtype": "text", "text": {"content": "📅 DaysHub 推送测试 — 通道正常"}
            }, timeout=10)
            results["企业微信"] = resp.status_code == 200
        except Exception as e:
            results["企业微信"] = False

    # 邮件
    if cfg["smtp_host"] and cfg["smtp_user"] and cfg["smtp_pass"] and cfg["smtp_to"]:
        results["邮件"] = send_email(
            "📅 DaysHub 推送测试",
            "<h2>DaysHub 推送测试</h2><p>如果您收到此邮件，说明邮件通道配置正常。</p>",
            "DaysHub 推送测试 — 邮件通道配置正常"
        )

    # Telegram
    if cfg["tg_bot_token"] and cfg["tg_chat_id"]:
        results["Telegram"] = send_telegram("📅 DaysHub 推送测试 — 通道正常")

    # Webhook
    if cfg["custom_webhook_urls"]:
        results["Webhook"] = send_webhook("test", {"msg": "DaysHub 推送测试"})

    return results


def build_reminder_text(to_notify, today):
    """构建提醒消息文本（美化版）"""
    lines = [f"📅 DaysHub 事件提醒\n{'─' * 22}"]
    for ev, adv in to_notify:
        if adv == 0:
            lines.append(f"\n🎉 今天就是「{ev['title']}」！")
        else:
            lines.append(f"\n⏳ 还有 {adv} 天就是「{ev['title']}」")
        if ev.get("lunar_str"):
            lines.append(f"   📅 {ev['lunar_str']}（公历 {ev.get('next_date', '?')}）")
        elif ev.get("next_date"):
            lines.append(f"   📅 公历 {ev['next_date']}")
        else:
            lines.append(f"   📅 {ev['date']}")
        if ev["note"]:
            lines.append(f"   📝 {ev['note']}")
    lines.append(f"\n{'─' * 22}")
    lines.append("DaysHub 时光看板")
    return "\n".join(lines)


def check_and_notify():
    """检查需要提醒的事件并发送通知（按每个事件单独的 advance_days）"""
    from models import list_events, compute_event, get_db
    today = date.today()
    events = list_events()
    to_notify = []

    for ev in events:
        ev = compute_event(ev, today)
        dr = ev.get("days_remaining")
        # 每个事件有自己的 advance_days，默认3天
        ev_advance = ev.get("advance_days", 3)
        if ev_advance is None:
            ev_advance = 3
        advance_list = [0] + ([ev_advance] if ev_advance > 0 else [])
        if dr is not None and dr in advance_list and ev["event_type"] in ("countdown", "recurring"):
            conn = get_db()
            already = conn.execute(
                "SELECT 1 FROM notification_log WHERE event_id=? AND notify_date=? AND advance_days=?",
                (ev["id"], today.isoformat(), dr)
            ).fetchone()
            conn.close()
            if not already:
                to_notify.append((ev, dr))

    if not to_notify:
        logger.debug("今日无需提醒")
        return

    text = build_reminder_text(to_notify, today)
    logger.info(f"需提醒 {len(to_notify)} 个事件")

    send_wecom(text)
    send_telegram(text)
    send_webhook("reminder", {
        "date": today.isoformat(),
        "events": [
            {"title": ev["title"], "advance_days": adv, "is_today": adv == 0,
             "next_date": ev.get("next_date"), "lunar_str": ev.get("lunar_str"), "note": ev["note"]}
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