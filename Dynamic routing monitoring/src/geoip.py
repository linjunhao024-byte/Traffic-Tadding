import os
import logging

logger = logging.getLogger("geoip")

_cache = {}
_reader_city = None
_reader_asn = None

_PRIVATE_PREFIXES = (
    "10.", "127.", "192.168.",
    "172.16.", "172.17.", "172.18.", "172.19.",
    "172.20.", "172.21.", "172.22.", "172.23.",
    "172.24.", "172.25.", "172.26.", "172.27.",
    "172.28.", "172.29.", "172.30.", "172.31.",
)

def _get_readers():
    global _reader_city, _reader_asn
    if _reader_city is None:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        city_path = os.path.join(base, "GeoLite2-City.mmdb")
        asn_path = os.path.join(base, "GeoLite2-ASN.mmdb")
        try:
            import geoip2.database
            if os.path.exists(city_path):
                _reader_city = geoip2.database.Reader(city_path)
            if os.path.exists(asn_path):
                _reader_asn = geoip2.database.Reader(asn_path)
        except Exception as e:
            logger.error(f"Failed to load GeoLite2 databases: {e}")
    return _reader_city, _reader_asn

def lookup(ip):
    if ip in _cache:
        return _cache[ip]

    if ip.startswith(_PRIVATE_PREFIXES):
        result = {"ip": ip, "country": "私有", "city": "本地", "org": "内网"}
        _cache[ip] = result
        return result

    result = {"ip": ip, "country": "未知", "city": "", "org": "", "asn": ""}

    reader_city, reader_asn = _get_readers()

    if reader_city:
        try:
            resp = reader_city.city(ip)
            result["country"] = resp.country.name or "未知"
            if resp.city and resp.city.name:
                result["city"] = resp.city.name
        except Exception:
            pass

    if reader_asn:
        try:
            resp = reader_asn.asn(ip)
            result["org"] = resp.autonomous_system_organization or ""
            result["asn"] = f"AS{resp.autonomous_system_number}"
        except Exception:
            pass

    _cache[ip] = result
    return result

def format_hop(index, hop):
    ip = hop.get("ip", "*")
    rtt = hop.get("rtt_ms")
    geo = lookup(ip)
    location = f"{geo['country']}"
    if geo.get("city"):
        location += f" {geo['city']}"
    org = geo.get("org", "")
    asn = geo.get("asn", "")
    rtt_str = f"{rtt:.1f}ms" if rtt else "*"
    line = f"  {index+1:>2}. {ip:<16} {rtt_str:<10} {location}"
    if org:
        line += f" ({org})"
    elif asn:
        line += f" ({asn})"
    return line

def format_traceroute_result(target_name, hops):
    lines = [f"路由追踪: {target_name}", ""]
    lines.append("跳 IP               延迟       位置")
    lines.append("-" * 60)
    for i, hop in enumerate(hops[:15]):
        lines.append(format_hop(i, hop))
    return "\n".join(lines)

def get_path_countries(hops):
    countries = []
    for hop in hops:
        geo = lookup(hop.get("ip", "*"))
        country = geo.get("country", "")
        if country and country not in ("未知", "查询失败", "私有", "本地") and country not in countries:
            countries.append(country)
    return countries
