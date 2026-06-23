import time
import logging

logger = logging.getLogger("chart")

def generate_latency_chart(db, target_host, target_name, hours=24, width=50):
    cutoff = time.time() - hours * 3600
    try:
        rows = db.query(
            "SELECT timestamp, latency_ms FROM ping_results WHERE target_host=? AND timestamp>? AND latency_ms IS NOT NULL ORDER BY timestamp",
            (target_host, cutoff)
        )
    except Exception as e:
        logger.error(f"Chart query failed: {e}")
        return None, None

    if len(rows) < 2:
        return None, None

    timestamps = [r[0] for r in rows]
    latencies = [r[1] for r in rows]

    min_lat = max(0, min(latencies) - 5)
    max_lat = max(latencies) + 5
    avg_lat = sum(latencies) / len(latencies)

    chart = []
    chart.append(f"📈 *延迟趋势: {target_name}* (过去{hours}小时)")
    chart.append(f"样本: {len(latencies)} | 平均: {avg_lat:.1f}ms | 范围: {min(latencies):.1f}~{max(latencies):.1f}ms")
    chart.append("")

    bucket_size = len(latencies) / width
    buckets = []
    for i in range(width):
        start_idx = int(i * bucket_size)
        end_idx = int((i + 1) * bucket_size)
        if start_idx < len(latencies):
            bucket_vals = latencies[start_idx:end_idx]
            buckets.append(sum(bucket_vals) / len(bucket_vals))

    if not buckets:
        return None, None

    chars = "▁▂▃▄▅▆▇█"
    chart_line = ""
    for val in buckets:
        if max_lat > min_lat:
            normalized = (val - min_lat) / (max_lat - min_lat)
        else:
            normalized = 0.5
        normalized = max(0, min(1, normalized))
        idx = int(normalized * (len(chars) - 1))
        chart_line += chars[idx]

    chart.append(f"`{chart_line}`")
    chart.append("")

    first_time = time.strftime("%m-%d %H:%M", time.localtime(timestamps[0]))
    last_time = time.strftime("%m-%d %H:%M", time.localtime(timestamps[-1]))
    chart.append(f"`{min_lat:.0f}ms{' ' * max(1, width - 10)}{max_lat:.0f}ms`")
    chart.append(f"`{first_time}{' ' * max(1, width - 16)}{last_time}`")

    return "\n".join(chart), None

def generate_loss_chart(db, target_host, target_name, hours=24, width=50):
    cutoff = time.time() - hours * 3600
    try:
        rows = db.query(
            "SELECT timestamp, packet_loss_pct FROM ping_results WHERE target_host=? AND timestamp>? ORDER BY timestamp",
            (target_host, cutoff)
        )
    except Exception as e:
        logger.error(f"Chart query failed: {e}")
        return None

    if len(rows) < 2:
        return None

    losses = [r[1] for r in rows]
    avg_loss = sum(losses) / len(losses)
    max_loss = max(losses)

    chars = "▁▂▃▄▅▆▇█"
    bucket_size = len(losses) / width
    chart_line = ""
    for i in range(width):
        start_idx = int(i * bucket_size)
        end_idx = int((i + 1) * bucket_size)
        if start_idx < len(losses):
            bucket_vals = losses[start_idx:end_idx]
            avg = sum(bucket_vals) / len(bucket_vals)
            normalized = avg / 100.0
            normalized = max(0, min(1, normalized))
            idx = int(normalized * (len(chars) - 1))
            chart_line += chars[idx]

    chart = []
    chart.append(f"📉 *丢包趋势: {target_name}* (过去{hours}小时)")
    chart.append(f"平均: {avg_loss:.1f}% | 最高: {max_loss:.1f}%")
    chart.append("")
    chart.append(f"`{chart_line}`")

    return "\n".join(chart)

def generate_speed_chart(db, hours=24, width=50):
    cutoff = time.time() - hours * 3600
    try:
        rows = db.query(
            "SELECT timestamp, speed_mbps FROM speed_results WHERE timestamp>? AND speed_mbps IS NOT NULL ORDER BY timestamp",
            (cutoff,)
        )
    except Exception as e:
        logger.error(f"Chart query failed: {e}")
        return None

    if len(rows) < 2:
        return None

    speeds = [r[1] for r in rows]
    avg_speed = sum(speeds) / len(speeds)
    min_speed = min(speeds)
    max_speed = max(speeds)

    chars = "▁▂▃▄▅▆▇█"
    bucket_size = len(speeds) / width
    chart_line = ""
    for i in range(width):
        start_idx = int(i * bucket_size)
        end_idx = int((i + 1) * bucket_size)
        if start_idx < len(speeds):
            bucket_vals = speeds[start_idx:end_idx]
            avg = sum(bucket_vals) / len(bucket_vals)
            if max_speed > min_speed:
                normalized = (avg - min_speed) / (max_speed - min_speed)
            else:
                normalized = 0.5
            normalized = max(0, min(1, normalized))
            idx = int(normalized * (len(chars) - 1))
            chart_line += chars[idx]

    chart = []
    chart.append(f"🚀 *带宽趋势* (过去{hours}小时)")
    chart.append(f"平均: {avg_speed:.1f}Mbps | 范围: {min_speed:.1f}~{max_speed:.1f}Mbps")
    chart.append("")
    chart.append(f"`{chart_line}`")

    return "\n".join(chart)
