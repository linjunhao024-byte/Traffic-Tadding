import subprocess
import re
import platform

def traceroute(host, max_hops=20):
    result = {
        "host": host,
        "hops": [],
        "hop_count": 0,
        "success": False,
        "raw": ""
    }

    system = platform.system().lower()
    if system == "windows":
        cmd = ["tracert", "-d", "-h", str(max_hops), "-w", "3000", host]
    else:
        cmd = ["traceroute", "-n", "-m", str(max_hops), "-w", "3", host]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        output = proc.stdout + proc.stderr
        result["raw"] = output

        ip_pattern = r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
        lines = output.strip().split("\n")

        for line in lines:
            # 跳过第一行（包含目标IP的头部）
            if "traceroute to" in line or "tracert" in line.lower():
                continue
            # 跳过包含 "*" 的行（超时跳）
            if "*" in line and not re.search(ip_pattern, line):
                continue

            ips = re.findall(ip_pattern, line)
            if ips:
                hop_ip = ips[0]
                # 跳过保留 IP 段
                if hop_ip.startswith(("240.", "241.", "242.", "243.", "244.", "245.", "246.", "247.", "0.")):
                    continue
                times = re.findall(r"(\d+(?:\.\d+)?)\s*ms", line)
                avg_time = sum(float(t) for t in times) / len(times) if times else None
                result["hops"].append({"ip": hop_ip, "rtt_ms": avg_time})

        result["hop_count"] = len(result["hops"])
        result["success"] = result["hop_count"] > 0

    except subprocess.TimeoutExpired:
        result["raw"] = "timeout"
    except Exception as e:
        result["raw"] = str(e)

    return result
