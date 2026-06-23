import time
import urllib.request
import logging

logger = logging.getLogger("speedtest")

def test_download_speed(url, timeout=30):
    result = {
        "url": url,
        "speed_mbps": None,
        "downloaded_bytes": 0,
        "elapsed_sec": 0,
        "success": False
    }

    try:
        start = time.time()
        req = urllib.request.Request(url, headers={"User-Agent": "RouteMonitor/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            elapsed = time.time() - start
            result["downloaded_bytes"] = len(data)
            result["elapsed_sec"] = round(elapsed, 2)
            if elapsed > 0:
                result["speed_mbps"] = round((len(data) * 8) / (elapsed * 1_000_000), 2)
            result["success"] = True
    except Exception as e:
        logger.error(f"Speedtest failed: {e}")

    return result
