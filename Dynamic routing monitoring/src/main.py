#!/usr/bin/env python3
import time
import logging
import logging.handlers
import sys
import os
import signal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import load_config
from db import Database
from pinger import ping
from tracer import traceroute
from speedtest import test_download_speed
from baseline import compute_baseline, check_anomaly, check_path_change, check_speed_anomaly
from alerter import send_alert, build_alert_message, build_daily_report
from tg_bot import TelegramBot
from geoip import get_path_countries

running = True
tg_bot = None

def signal_handler(sig, frame):
    global running
    running = False

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

def setup_logging(config):
    log_cfg = config.get("log", {})
    level = getattr(logging, log_cfg.get("level", "INFO"))
    log_file = log_cfg.get("file", "monitor.log")
    max_bytes = log_cfg.get("max_size_mb", 50) * 1024 * 1024
    backup_count = log_cfg.get("backup_count", 5)
    fmt = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(console)
    root.addHandler(file_handler)

def should_alert():
    global tg_bot
    if tg_bot and tg_bot.is_muted():
        return False
    return True

def do_ping_cycle(db, config):
    logger = logging.getLogger("ping")
    targets = config["ping_targets"]
    count = config["monitoring"]["ping_count"]
    consecutive = {}
    results = []
    for target in targets:
        host = target["host"]
        name = target["name"]
        result = ping(host, count=count)
        if result["success"]:
            latency = result["latency_ms"]
            loss = result["packet_loss_pct"]
            std = result.get("std_ms", 0)
            min_ms = result.get("min_ms", latency)
            max_ms = result.get("max_ms", latency)
            is_anomaly, reason, severity = check_anomaly(db, config, host, latency, loss, std)
            db.save_ping(host, name, latency, min_ms, max_ms, std, loss, is_anomaly)
            status = "ANOMALY" if is_anomaly else "OK"
            logger.info(f"[{status}] {name}({host}): {latency:.1f}ms (min:{min_ms:.1f} max:{max_ms:.1f} std:{std:.1f}) loss:{loss:.1f}%")
            results.append({"host": host, "name": name, "latency": latency, "loss": loss, "anomaly": is_anomaly})
            if is_anomaly:
                consecutive[host] = consecutive.get(host, 0) + 1
                threshold = config["alert"]["consecutive_failures"]
                if consecutive[host] >= threshold:
                    cooldown = config["alert"]["cooldown_sec"]
                    last = db.get_last_alert_time("ping_anomaly", host)
                    if time.time() - last > cooldown and should_alert():
                        msg = build_alert_message("延迟/丢包异常", severity, config["server_name"], {
                            "目标": f"{name} ({host})",
                            "延迟": f"{latency:.1f}ms (基线: {db.get_baseline(host)[0]:.1f}ms)" if db.get_baseline(host) else f"{latency:.1f}ms",
                            "抖动": f"{std:.1f}ms",
                            "丢包": f"{loss:.1f}%",
                            "原因": reason,
                            "连续异常": f"{consecutive[host]}次"
                        })
                        send_alert(config, msg)
                        db.save_alert("ping_anomaly", severity, f"{host} {reason}")
                        logger.warning(f"ALERT SENT [{severity}]: {name} {reason}")
            else:
                if consecutive.get(host, 0) >= config["alert"]["consecutive_failures"]:
                    if config["alert"].get("recovery_notify") and should_alert():
                        msg = build_alert_message("延迟恢复", "recovery", config["server_name"], {
                            "目标": f"{name} ({host})",
                            "当前延迟": f"{latency:.1f}ms",
                            "丢包": f"{loss:.1f}%"
                        })
                        send_alert(config, msg)
                        db.save_alert("ping_recovery", "recovery", f"{host} recovered")
                consecutive[host] = 0
        else:
            db.save_ping(host, name, None, None, None, None, 100.0, True)
            logger.warning(f"[FAIL] {name}({host}): ping failed")
            consecutive[host] = consecutive.get(host, 0) + 1
    return results

def do_traceroute_cycle(db, config):
    logger = logging.getLogger("traceroute")
    targets = config["traceroute_targets"]
    for target in targets:
        host = target["host"]
        name = target["name"]
        result = traceroute(host)
        if result["success"]:
            hop_count = result["hop_count"]
            baseline = db.get_baseline(host)
            baseline_hops = baseline[5] if baseline else None
            # 首次运行或基线为空时不报路径变化
            if baseline_hops and baseline_hops != "[]" and baseline_hops != "null":
                changed, detail = check_path_change(result["hops"], baseline_hops)
            else:
                changed, detail = False, "first run, setting baseline"
            db.save_traceroute(host, name, result["hops"], hop_count, changed, detail)
            if changed:
                cooldown = config["alert"]["cooldown_sec"]
                last = db.get_last_alert_time("path_change", host)
                if time.time() - last > cooldown and should_alert():
                    path_str = " -> ".join(h["ip"] for h in result["hops"][:8])
                    countries = get_path_countries(result["hops"])
                    geo_str = " → ".join(countries) if countries else "未知"
                    msg = build_alert_message("路径变化", "warning", config["server_name"], {
                        "目标": f"{name} ({host})",
                        "跳数": str(hop_count),
                        "变化": detail,
                        "当前路径": path_str,
                        "经过地区": geo_str
                    })
                    send_alert(config, msg)
                    db.save_alert("path_change", "warning", f"{host} {detail}")
                    logger.warning(f"PATH CHANGED: {name} {detail}")
            hops_str = " -> ".join(h["ip"] for h in result["hops"][:5])
            logger.info(f"[{'CHANGED' if changed else 'OK'}] {name}: {hop_count} hops | {hops_str}")
        else:
            logger.warning(f"[FAIL] {name}({host}): traceroute failed")

def do_speedtest_cycle(db, config):
    logger = logging.getLogger("speedtest")
    st_cfg = config.get("speedtest", {})
    if not st_cfg.get("enabled"):
        return
    url = st_cfg.get("target_url")
    if not url:
        return
    result = test_download_speed(url)
    if result["success"]:
        speed = result["speed_mbps"]
        is_anomaly, reason = check_speed_anomaly(db, config, speed)
        db.save_speed(url, speed, result["downloaded_bytes"], result["elapsed_sec"], is_anomaly)
        status = "ANOMALY" if is_anomaly else "OK"
        logger.info(f"[{status}] Speed: {speed:.1f}Mbps ({result['downloaded_bytes']/1024/1024:.1f}MB in {result['elapsed_sec']:.1f}s)")
        if is_anomaly:
            cooldown = config["alert"]["cooldown_sec"]
            last = db.get_last_alert_time("speed_anomaly")
            if time.time() - last > cooldown and should_alert():
                msg = build_alert_message("带宽下降", "warning", config["server_name"], {
                    "当前速度": f"{speed:.1f}Mbps",
                    "原因": reason
                })
                send_alert(config, msg)
                db.save_alert("speed_anomaly", "warning", reason)
                logger.warning(f"SPEED ALERT: {reason}")
    else:
        logger.warning("Speedtest failed")

def update_baselines(db, config):
    logger = logging.getLogger("baseline")
    for t in config["ping_targets"]:
        host = t["host"]
        bl = compute_baseline(db, host)
        if bl:
            old = db.get_baseline(host)
            old_avg = old[0] if old else None
            old_hops = old[5] if old else "[]"
            hop_count = old[4] if old else 0
            db.save_baseline(host, bl["avg_ms"], bl["std_ms"], bl["min_ms"], bl["max_ms"], hop_count, old_hops)
            if old_avg and abs(bl["avg_ms"] - old_avg) > old_avg * 0.3:
                logger.warning(f"Baseline shifted for {host}: {old_avg:.1f}ms -> {bl['avg_ms']:.1f}ms")
            else:
                logger.info(f"Baseline: {t['name']}({host}) avg={bl['avg_ms']:.1f}ms std={bl['std_ms']:.1f}ms")

def do_cleanup(db, config):
    days = config.get("database", {}).get("cleanup_days", 30)
    db.cleanup_old_data(days)

def main():
    global running, tg_bot
    config = load_config()
    setup_logging(config)
    logger = logging.getLogger("main")
    db = Database(config["database"]["path"])
    server_name = config["server_name"]

    tg_cfg = config.get("telegram", {})
    if tg_cfg.get("enabled") and tg_cfg.get("bot_token"):
        tg_bot = TelegramBot(tg_cfg["bot_token"], tg_cfg["chat_id"], db, config)
        tg_bot.start_polling()
        logger.info("Telegram bot started")

    logger.info(f"{'='*50}")
    logger.info(f"AWS Route Monitor - {server_name}")
    logger.info(f"Mode: {config.get('mode', 'full')}")
    logger.info(f"Ping targets: {[t['name'] for t in config['ping_targets']]}")
    logger.info(f"Traceroute targets: {[t['name'] for t in config['traceroute_targets']]}")
    logger.info(f"Speedtest: {'enabled' if config.get('speedtest', {}).get('enabled') else 'disabled'}")
    logger.info(f"{'='*50}")

    ping_interval = config["monitoring"]["ping_interval_sec"]
    tr_interval = config["monitoring"]["traceroute_interval_sec"]
    st_interval = config.get("speedtest", {}).get("interval_sec", 1800)
    bl_interval = 600
    report_interval = 86400
    cleanup_interval = 86400
    sample_count = config["monitoring"]["baseline_sample_count"]

    last_tr = 0
    last_bl = 0
    last_st = 0
    last_report = 0
    last_cleanup = 0
    cycle = 0

    logger.info(f"Warming up: collecting {sample_count} samples for baseline...")

    while running:
        try:
            now = time.time()
            do_ping_cycle(db, config)
            cycle += 1
            if now - last_tr >= tr_interval:
                do_traceroute_cycle(db, config)
                last_tr = now
            if now - last_st >= st_interval:
                do_speedtest_cycle(db, config)
                last_st = now
            if now - last_bl >= bl_interval:
                update_baselines(db, config)
                last_bl = now
            if cycle == sample_count:
                logger.info("Warmup complete, computing initial baselines...")
                update_baselines(db, config)
                last_bl = now
                if should_alert():
                    stats = db.get_stats_summary(hours=1)
                    if stats:
                        from alerter import build_daily_report
                        report = "✅ 路由监测已启动\n\n" + build_daily_report(config, stats)
                        send_alert(config, report)
                        logger.info("Startup report sent")
            if now - last_report >= report_interval:
                stats = db.get_stats_summary(hours=24)
                if stats:
                    report = build_daily_report(config, stats)
                    send_alert(config, report)
                    logger.info("Daily report sent")
                last_report = now
            if now - last_cleanup >= cleanup_interval:
                do_cleanup(db, config)
                last_cleanup = now
            time.sleep(ping_interval)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)
            time.sleep(5)

    if tg_bot:
        tg_bot.stop()
    logger.info("Monitor stopped.")

if __name__ == "__main__":
    main()
