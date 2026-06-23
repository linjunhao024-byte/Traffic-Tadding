import sqlite3
import time
import json
import threading

class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()

    def _get_conn(self):
        conn = getattr(self._local, 'conn', None)
        if conn is None:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn = conn
        return conn

    def _init_db(self):
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS ping_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                target_host TEXT,
                target_name TEXT,
                latency_ms REAL,
                min_ms REAL,
                max_ms REAL,
                std_ms REAL,
                packet_loss_pct REAL,
                is_anomaly INTEGER DEFAULT 0
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS traceroute_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                target_host TEXT,
                target_name TEXT,
                hops_json TEXT,
                hop_count INTEGER,
                changed INTEGER DEFAULT 0,
                change_detail TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS speed_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                url TEXT,
                speed_mbps REAL,
                downloaded_bytes INTEGER,
                elapsed_sec REAL,
                is_anomaly INTEGER DEFAULT 0
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS baselines (
                target_host TEXT PRIMARY KEY,
                avg_latency_ms REAL,
                std_latency_ms REAL,
                min_latency_ms REAL,
                max_latency_ms REAL,
                hop_count INTEGER,
                hops_json TEXT,
                avg_speed_mbps REAL,
                updated_at REAL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                alert_type TEXT,
                severity TEXT,
                message TEXT,
                resolved INTEGER DEFAULT 0
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_ping_ts ON ping_results(timestamp)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_ping_host ON ping_results(target_host, timestamp)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_alert_type ON alerts(alert_type, timestamp)")
        conn.commit()

    def save_ping(self, target_host, target_name, latency_ms, min_ms, max_ms, std_ms, packet_loss_pct, is_anomaly=False):
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO ping_results (timestamp, target_host, target_name, latency_ms, min_ms, max_ms, std_ms, packet_loss_pct, is_anomaly) VALUES (?,?,?,?,?,?,?,?,?)",
            (time.time(), target_host, target_name, latency_ms, min_ms, max_ms, std_ms, packet_loss_pct, int(is_anomaly))
        )
        conn.commit()

    def save_traceroute(self, target_host, target_name, hops, hop_count, changed=False, change_detail=""):
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO traceroute_results (timestamp, target_host, target_name, hops_json, hop_count, changed, change_detail) VALUES (?,?,?,?,?,?,?)",
            (time.time(), target_host, target_name, json.dumps(hops), hop_count, int(changed), change_detail)
        )
        conn.commit()

    def save_speed(self, url, speed_mbps, downloaded_bytes, elapsed_sec, is_anomaly=False):
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO speed_results (timestamp, url, speed_mbps, downloaded_bytes, elapsed_sec, is_anomaly) VALUES (?,?,?,?,?,?)",
            (time.time(), url, speed_mbps, downloaded_bytes, elapsed_sec, int(is_anomaly))
        )
        conn.commit()

    def get_recent_pings(self, target_host, count=100):
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT latency_ms, min_ms, max_ms, std_ms, packet_loss_pct FROM ping_results WHERE target_host=? ORDER BY id DESC LIMIT ?",
            (target_host, count)
        ).fetchall()
        return rows

    def get_recent_speeds(self, count=20):
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT speed_mbps FROM speed_results ORDER BY id DESC LIMIT ?", (count,)
        ).fetchall()
        return rows

    def get_baseline(self, target_host):
        conn = self._get_conn()
        row = conn.execute(
            "SELECT avg_latency_ms, std_latency_ms, min_latency_ms, max_latency_ms, hop_count, hops_json, avg_speed_mbps FROM baselines WHERE target_host=?",
            (target_host,)
        ).fetchone()
        return row

    def save_baseline(self, target_host, avg_latency, std_latency, min_latency, max_latency, hop_count, hops_json, avg_speed=None):
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO baselines (target_host, avg_latency_ms, std_latency_ms, min_latency_ms, max_latency_ms, hop_count, hops_json, avg_speed_mbps, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (target_host, avg_latency, std_latency, min_latency, max_latency, hop_count, hops_json, avg_speed, time.time())
        )
        conn.commit()

    def save_alert(self, alert_type, severity, message):
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO alerts (timestamp, alert_type, severity, message) VALUES (?,?,?,?)",
            (time.time(), alert_type, severity, message)
        )
        conn.commit()

    def get_last_alert_time(self, alert_type, target_host=None):
        conn = self._get_conn()
        if target_host:
            row = conn.execute(
                "SELECT timestamp FROM alerts WHERE alert_type=? AND message LIKE ? ORDER BY id DESC LIMIT 1",
                (alert_type, f"%{target_host}%")
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT timestamp FROM alerts WHERE alert_type=? ORDER BY id DESC LIMIT 1",
                (alert_type,)
            ).fetchone()
        return row[0] if row else 0

    def cleanup_old_data(self, days=30):
        cutoff = time.time() - days * 86400
        conn = self._get_conn()
        conn.execute("DELETE FROM ping_results WHERE timestamp < ?", (cutoff,))
        conn.execute("DELETE FROM traceroute_results WHERE timestamp < ?", (cutoff,))
        conn.execute("DELETE FROM speed_results WHERE timestamp < ?", (cutoff,))
        conn.execute("DELETE FROM alerts WHERE timestamp < ?", (cutoff,))
        conn.commit()

    def get_stats_summary(self, hours=24):
        cutoff = time.time() - hours * 3600
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT target_host, target_name, AVG(latency_ms), MIN(latency_ms), MAX(latency_ms), AVG(packet_loss_pct), COUNT(*) FROM ping_results WHERE timestamp > ? AND latency_ms IS NOT NULL GROUP BY target_host",
            (cutoff,)
        ).fetchall()
        return rows

    def query(self, sql, params=()):
        conn = self._get_conn()
        return conn.execute(sql, params).fetchall()
