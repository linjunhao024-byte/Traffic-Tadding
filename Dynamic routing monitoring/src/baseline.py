import json
import logging

logger = logging.getLogger("baseline")

def compute_baseline(db, target_host):
    rows = db.get_recent_pings(target_host, count=100)
    if len(rows) < 20:
        logger.info(f"Not enough data for baseline on {target_host} ({len(rows)} samples)")
        return None
    latencies = [r[0] for r in rows if r[0] is not None]
    if len(latencies) < 20:
        return None
    avg = sum(latencies) / len(latencies)
    variance = sum((x - avg) ** 2 for x in latencies) / len(latencies)
    std = variance ** 0.5
    return {
        "avg_ms": round(avg, 2),
        "std_ms": round(std, 2),
        "min_ms": round(min(latencies), 2),
        "max_ms": round(max(latencies), 2)
    }

def check_anomaly(db, config, target_host, current_latency, current_loss, current_std=None):
    alert_cfg = config["alert"]
    baseline = db.get_baseline(target_host)
    if baseline is None:
        return False, "no baseline", "info"
    avg_ms = baseline[0]
    std_ms = baseline[1]
    reasons = []
    severity = "info"
    if current_latency is not None and avg_ms > 0:
        if current_latency > avg_ms * alert_cfg["latency_multiplier"]:
            reasons.append(f"延迟 {current_latency:.1f}ms > 基线 {avg_ms:.1f}ms x{alert_cfg['latency_multiplier']}")
            severity = "warning"
        if current_latency > alert_cfg["latency_abs_threshold_ms"]:
            reasons.append(f"延迟 {current_latency:.1f}ms > 绝对阈值 {alert_cfg['latency_abs_threshold_ms']}ms")
            severity = "critical"
        if current_std is not None and current_std > std_ms * 3:
            reasons.append(f"抖动 {current_std:.1f}ms > 基线 {std_ms:.1f}ms x3")
            if severity == "info":
                severity = "warning"
    if current_loss > alert_cfg["packet_loss_threshold_pct"]:
        reasons.append(f"丢包 {current_loss:.1f}% > 阈值 {alert_cfg['packet_loss_threshold_pct']}%")
        severity = "critical"
    return len(reasons) > 0, "; ".join(reasons), severity

def check_path_change(current_hops, baseline_hops_json):
    if not baseline_hops_json:
        return False, "no baseline"
    baseline_hops = json.loads(baseline_hops_json)
    if len(current_hops) != len(baseline_hops):
        return True, f"跳数变化 {len(baseline_hops)} -> {len(current_hops)}"
    changes = []
    for i, (cur, base) in enumerate(zip(current_hops, baseline_hops)):
        if cur["ip"] != base["ip"]:
            changes.append(f"第{i+1}跳: {base['ip']} -> {cur['ip']}")
    if changes:
        return True, "; ".join(changes[:5])
    return False, "no change"

def check_speed_anomaly(db, config, current_speed):
    rows = db.get_recent_speeds(count=10)
    if len(rows) < 3:
        return False, "no baseline"
    speeds = [r[0] for r in rows if r[0] is not None]
    if not speeds:
        return False, "no data"
    avg_speed = sum(speeds) / len(speeds)
    threshold = config["alert"]["speed_drop_threshold_pct"]
    if avg_speed > 0 and current_speed < avg_speed * (1 - threshold / 100):
        return True, f"速度 {current_speed:.1f}Mbps < 基线 {avg_speed:.1f}Mbps (下降{threshold}%+)"
    return False, "ok"
