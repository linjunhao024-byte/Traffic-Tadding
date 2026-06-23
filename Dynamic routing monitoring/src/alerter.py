import requests
import time
import hmac
import hashlib
import base64
import urllib.parse
import logging

logger = logging.getLogger("alerter")

def _escape_md(text):
    text = str(text)
    for ch in ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']:
        text = text.replace(ch, f'\\{ch}')
    return text

def send_telegram(bot_token, chat_id, message):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "MarkdownV2"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code != 200:
            logger.warning(f"Telegram API returned {r.status_code}: {r.text[:200]}")
            payload["parse_mode"] = ""
            payload["text"] = message.replace("*", "").replace("`", "").replace("_", "")
            r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")
        return False

def send_dingtalk(webhook_url, secret, message):
    url = webhook_url
    if secret:
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{secret}"
        hmac_code = hmac.new(secret.encode(), string_to_sign.encode(), hashlib.sha256).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        url = f"{webhook_url}&timestamp={timestamp}&sign={sign}"
    payload = {"msgtype": "text", "text": {"content": "路由监测告警\n\n" + message}}
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        logger.error(f"DingTalk send failed: {e}")
        return False

def send_alert(config, message):
    ok = True
    tg = config.get("telegram", {})
    if tg.get("enabled"):
        if not send_telegram(tg["bot_token"], tg["chat_id"], message):
            ok = False
    dt = config.get("dingtalk", {})
    if dt.get("enabled"):
        if not send_dingtalk(dt["webhook_url"], dt.get("secret", ""), message):
            ok = False
    return ok

def build_alert_message(alert_type, severity, server_name, details):
    icon = {"critical": "🔴", "warning": "🟡", "info": "🟢", "recovery": "✅"}.get(severity, "⚪")
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    lines = []
    lines.append(f"{icon} 路由监测告警")
    lines.append("")
    lines.append(f"服务器: {server_name}")
    lines.append(f"时间: {timestamp}")
    lines.append(f"级别: {severity.upper()}")
    lines.append(f"类型: {alert_type}")
    lines.append("")
    for k, v in details.items():
        lines.append(f"{k}: {v}")
    lines.append("")
    lines.append("---")
    return "\n".join(lines)

def build_daily_report(config, stats):
    server_name = config["server_name"]
    timestamp = time.strftime("%Y-%m-%d %H:%M", time.localtime())
    lines = []
    lines.append(f"📊 每日路由报告")
    lines.append(f"服务器: {server_name}")
    lines.append(f"时间: {timestamp}")
    lines.append("")
    lines.append("目标 | 平均延迟 | 最低 | 最高 | 丢包")
    lines.append("---|---|---|---|---")
    for row in stats:
        host, name, avg, mn, mx, loss, cnt = row
        lines.append(f"{name} | {avg:.1f}ms | {mn:.1f}ms | {mx:.1f}ms | {loss:.1f}%")
    return "\n".join(lines)
