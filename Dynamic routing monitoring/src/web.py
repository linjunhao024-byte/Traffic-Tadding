#!/usr/bin/env python3
"""
Dynamic Routing Monitor - Web Dashboard
轻量级 Web 界面，使用 Python 内置 http.server，零依赖
"""

import json
import time
import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger("web")

# 全局引用（由 main.py 注入）
_db = None
_config = None

# HTML 页面（内嵌）
HTML_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Route Monitor - Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, monospace;
            background: #0f0f0f;
            color: #e0e0e0;
            min-height: 100vh;
        }
        .header {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            padding: 20px 30px;
            border-bottom: 2px solid #0ff;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 {
            font-size: 24px;
            color: #0ff;
            font-weight: 600;
        }
        .header .info {
            display: flex;
            gap: 20px;
            font-size: 14px;
        }
        .header .info span { color: #888; }
        .header .info .value { color: #0ff; font-weight: 600; }
        .status-dot {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 6px;
        }
        .status-dot.running { background: #0f0; box-shadow: 0 0 8px #0f0; }
        .status-dot.stopped { background: #f00; box-shadow: 0 0 8px #f00; }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }

        .card {
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 20px;
            transition: border-color 0.3s;
        }
        .card:hover { border-color: #0ff; }
        .card h3 {
            color: #0ff;
            font-size: 16px;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid #333;
        }

        .chart-container {
            position: relative;
            height: 250px;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }
        th {
            background: #222;
            color: #0ff;
            padding: 10px 12px;
            text-align: left;
            font-weight: 600;
            border-bottom: 2px solid #0ff;
        }
        td {
            padding: 8px 12px;
            border-bottom: 1px solid #333;
        }
        tr:hover td { background: #222; }

        .badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
        }
        .badge.ok { background: #0a3; color: #fff; }
        .badge.warning { background: #a50; color: #fff; }
        .badge.critical { background: #a00; color: #fff; }
        .badge.recovery { background: #08a; color: #fff; }

        .stat-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
        }
        .stat-item {
            background: #222;
            padding: 12px;
            border-radius: 6px;
            text-align: center;
        }
        .stat-item .label {
            font-size: 11px;
            color: #888;
            margin-bottom: 4px;
        }
        .stat-item .value {
            font-size: 20px;
            font-weight: 700;
            color: #0ff;
        }

        .actions {
            display: flex;
            gap: 10px;
            margin-top: 15px;
        }
        .btn {
            padding: 8px 16px;
            border: 1px solid #0ff;
            background: transparent;
            color: #0ff;
            border-radius: 4px;
            cursor: pointer;
            font-size: 13px;
            transition: all 0.2s;
        }
        .btn:hover {
            background: #0ff;
            color: #000;
        }
        .btn.danger {
            border-color: #f44;
            color: #f44;
        }
        .btn.danger:hover {
            background: #f44;
            color: #fff;
        }

        .toast {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #0ff;
            color: #000;
            padding: 12px 20px;
            border-radius: 6px;
            font-weight: 600;
            transform: translateY(100px);
            opacity: 0;
            transition: all 0.3s;
        }
        .toast.show {
            transform: translateY(0);
            opacity: 1;
        }

        .loading {
            text-align: center;
            padding: 40px;
            color: #888;
        }

        @media (max-width: 768px) {
            .header { flex-direction: column; gap: 10px; }
            .grid { grid-template-columns: 1fr; }
            .stat-grid { grid-template-columns: 1fr 1fr; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🚦 Dynamic Routing Monitor</h1>
        <div class="info">
            <span>服务器: <span class="value" id="server-name">-</span></span>
            <span>状态: <span id="status-indicator"><span class="status-dot stopped"></span><span class="value">加载中...</span></span></span>
            <span>运行时间: <span class="value" id="uptime">-</span></span>
        </div>
    </div>

    <div class="container">
        <!-- 统计卡片 -->
        <div class="grid">
            <div class="card">
                <h3>📊 延迟趋势</h3>
                <div class="chart-container">
                    <canvas id="latencyChart"></canvas>
                </div>
                <div class="actions">
                    <button class="btn" onclick="loadChart('1h')">1小时</button>
                    <button class="btn" onclick="loadChart('6h')">6小时</button>
                    <button class="btn" onclick="loadChart('24h')">24小时</button>
                </div>
            </div>

            <div class="card">
                <h3>📉 丢包趋势</h3>
                <div class="chart-container">
                    <canvas id="lossChart"></canvas>
                </div>
            </div>

            <div class="card">
                <h3>🚀 带宽趋势</h3>
                <div class="chart-container">
                    <canvas id="speedChart"></canvas>
                </div>
                <div class="actions">
                    <button class="btn" onclick="runSpeedtest()">立即测速</button>
                </div>
            </div>

            <div class="card">
                <h3>📈 基线数据</h3>
                <table>
                    <thead>
                        <tr>
                            <th>目标</th>
                            <th>平均延迟</th>
                            <th>抖动</th>
                            <th>范围</th>
                        </tr>
                    </thead>
                    <tbody id="baseline-table">
                        <tr><td colspan="4" class="loading">加载中...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- 当前状态 -->
        <div class="card" style="margin-bottom: 20px;">
            <h3>📋 当前状态（过去1小时）</h3>
            <table>
                <thead>
                    <tr>
                        <th>目标</th>
                        <th>平均延迟</th>
                        <th>最低</th>
                        <th>最高</th>
                        <th>丢包</th>
                        <th>样本数</th>
                    </tr>
                </thead>
                <tbody id="status-table">
                    <tr><td colspan="6" class="loading">加载中...</td></tr>
                </tbody>
            </table>
        </div>

        <!-- 告警历史 -->
        <div class="card">
            <h3>🔔 告警历史</h3>
            <table>
                <thead>
                    <tr>
                        <th>时间</th>
                        <th>类型</th>
                        <th>级别</th>
                        <th>消息</th>
                    </tr>
                </thead>
                <tbody id="alert-table">
                    <tr><td colspan="4" class="loading">加载中...</td></tr>
                </tbody>
            </table>
            <div class="actions">
                <button class="btn" onclick="testAlert()">测试告警</button>
            </div>
        </div>
    </div>

    <div class="toast" id="toast"></div>

    <script>
        // 全局变量
        let latencyChart, lossChart, speedChart;
        let currentTarget = null;
        let refreshTimer = null;

        // API 请求
        async function api(endpoint, method = 'GET', body = null) {
            try {
                const opts = { method };
                if (body) {
                    opts.headers = { 'Content-Type': 'application/json' };
                    opts.body = JSON.stringify(body);
                }
                const resp = await fetch('/api' + endpoint, opts);
                return await resp.json();
            } catch (e) {
                console.error('API Error:', e);
                return null;
            }
        }

        // 显示提示
        function showToast(msg, duration = 3000) {
            const toast = document.getElementById('toast');
            toast.textContent = msg;
            toast.classList.add('show');
            setTimeout(() => toast.classList.remove('show'), duration);
        }

        // 初始化图表
        function initCharts() {
            const chartOpts = {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                },
                scales: {
                    x: {
                        grid: { color: '#333' },
                        ticks: { color: '#888', maxTicksLimit: 8 }
                    },
                    y: {
                        grid: { color: '#333' },
                        ticks: { color: '#888' }
                    }
                },
                elements: {
                    point: { radius: 0 },
                    line: { borderWidth: 2 }
                }
            };

            latencyChart = new Chart(document.getElementById('latencyChart'), {
                type: 'line',
                data: { labels: [], datasets: [] },
                options: { ...chartOpts, scales: { ...chartOpts.scales, y: { ...chartOpts.scales.y, title: { display: true, text: 'ms', color: '#888' } } } }
            });

            lossChart = new Chart(document.getElementById('lossChart'), {
                type: 'line',
                data: { labels: [], datasets: [] },
                options: { ...chartOpts, scales: { ...chartOpts.scales, y: { ...chartOpts.scales.y, title: { display: true, text: '%', color: '#888' } } } }
            });

            speedChart = new Chart(document.getElementById('speedChart'), {
                type: 'line',
                data: { labels: [], datasets: [] },
                options: { ...chartOpts, scales: { ...chartOpts.scales, y: { ...chartOpts.scales.y, title: { display: true, text: 'Mbps', color: '#888' } } } }
            });
        }

        // 格式化时间戳
        function formatTime(ts) {
            const d = new Date(ts * 1000);
            return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
        }

        // 加载服务器信息
        async function loadServerInfo() {
            const data = await api('/server');
            if (data) {
                document.getElementById('server-name').textContent = data.name;
                const indicator = document.getElementById('status-indicator');
                if (data.running) {
                    indicator.innerHTML = '<span class="status-dot running"></span><span class="value">运行中</span>';
                } else {
                    indicator.innerHTML = '<span class="status-dot stopped"></span><span class="value">已停止</span>';
                }
                document.getElementById('uptime').textContent = data.uptime || '-';
            }
        }

        // 加载当前状态
        async function loadStatus() {
            const data = await api('/status');
            if (!data || !data.length) {
                document.getElementById('status-table').innerHTML = '<tr><td colspan="6" style="color:#888">暂无数据</td></tr>';
                return;
            }

            const tbody = document.getElementById('status-table');
            tbody.innerHTML = data.map(row => `
                <tr>
                    <td>${row.name}</td>
                    <td>${row.avg?.toFixed(1) || '-'}ms</td>
                    <td>${row.min?.toFixed(1) || '-'}ms</td>
                    <td>${row.max?.toFixed(1) || '-'}ms</td>
                    <td>${row.loss?.toFixed(1) || '-'}%</td>
                    <td>${row.count || 0}</td>
                </tr>
            `).join('');

            // 设置第一个目标为默认图表目标
            if (!currentTarget && data.length > 0) {
                currentTarget = data[0].host;
                loadChart('1h');
            }
        }

        // 加载基线数据
        async function loadBaselines() {
            const data = await api('/baselines');
            if (!data || !data.length) {
                document.getElementById('baseline-table').innerHTML = '<tr><td colspan="4" style="color:#888">暂无基线数据</td></tr>';
                return;
            }

            document.getElementById('baseline-table').innerHTML = data.map(b => `
                <tr>
                    <td>${b.name}</td>
                    <td>${b.avg?.toFixed(1) || '-'}ms</td>
                    <td>${b.std?.toFixed(1) || '-'}ms</td>
                    <td>${b.min?.toFixed(1) || '-'} ~ ${b.max?.toFixed(1)}ms</td>
                </tr>
            `).join('');
        }

        // 加载图表数据
        async function loadChart(period) {
            if (!currentTarget) return;

            const hours = period === '1h' ? 1 : period === '6h' ? 6 : 24;

            // 延迟图表
            const latencyData = await api(`/chart/latency/${currentTarget}?hours=${hours}`);
            if (latencyData && latencyData.timestamps) {
                latencyChart.data = {
                    labels: latencyData.timestamps.map(formatTime),
                    datasets: [{
                        label: '延迟',
                        data: latencyData.values,
                        borderColor: '#0ff',
                        backgroundColor: 'rgba(0,255,255,0.1)',
                        fill: true
                    }]
                };
                latencyChart.update();
            }

            // 丢包图表
            const lossData = await api(`/chart/loss/${currentTarget}?hours=${hours}`);
            if (lossData && lossData.timestamps) {
                lossChart.data = {
                    labels: lossData.timestamps.map(formatTime),
                    datasets: [{
                        label: '丢包',
                        data: lossData.values,
                        borderColor: '#f44',
                        backgroundColor: 'rgba(255,68,68,0.1)',
                        fill: true
                    }]
                };
                lossChart.update();
            }

            // 带宽图表
            const speedData = await api(`/chart/speed?hours=${hours}`);
            if (speedData && speedData.timestamps) {
                speedChart.data = {
                    labels: speedData.timestamps.map(formatTime),
                    datasets: [{
                        label: '带宽',
                        data: speedData.values,
                        borderColor: '#0f0',
                        backgroundColor: 'rgba(0,255,0,0.1)',
                        fill: true
                    }]
                };
                speedChart.update();
            }
        }

        // 加载告警历史
        async function loadAlerts() {
            const data = await api('/alerts?limit=20');
            if (!data || !data.length) {
                document.getElementById('alert-table').innerHTML = '<tr><td colspan="4" style="color:#888">暂无告警</td></tr>';
                return;
            }

            document.getElementById('alert-table').innerHTML = data.map(a => {
                const badgeClass = a.severity === 'critical' ? 'critical' : a.severity === 'warning' ? 'warning' : a.severity === 'recovery' ? 'recovery' : 'ok';
                return `
                    <tr>
                        <td>${formatTime(a.timestamp)}</td>
                        <td>${a.alert_type}</td>
                        <td><span class="badge ${badgeClass}">${a.severity}</span></td>
                        <td>${a.message}</td>
                    </tr>
                `;
            }).join('');
        }

        // 触发测速
        async function runSpeedtest() {
            showToast('正在测速...');
            const result = await api('/speed/run', 'POST');
            if (result && result.success) {
                showToast(`测速完成: ${result.speed_mbps} Mbps`);
                loadChart('24h');
            } else {
                showToast('测速失败');
            }
        }

        // 测试告警
        async function testAlert() {
            const result = await api('/alert/test', 'POST');
            if (result && result.ok) {
                showToast('测试告警已发送');
            } else {
                showToast('发送失败');
            }
        }

        // 刷新所有数据
        async function refreshAll() {
            await Promise.all([
                loadServerInfo(),
                loadStatus(),
                loadBaselines(),
                loadAlerts()
            ]);
        }

        // 初始化
        document.addEventListener('DOMContentLoaded', () => {
            initCharts();
            refreshAll();

            // 每 30 秒刷新一次
            refreshTimer = setInterval(refreshAll, 30000);
        });
    </script>
</body>
</html>"""


class RequestHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器"""

    def log_message(self, format, *args):
        """重写日志，使用 logging 模块"""
        logger.debug(f"{self.client_address[0]} - {format % args}")

    def _send_json(self, data, status=200):
        """发送 JSON 响应"""
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html, status=200):
        """发送 HTML 响应"""
        body = html.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def _parse_path(self):
        """解析请求路径"""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')
        query = parse_qs(parsed.query)
        return path, query

    def do_GET(self):
        """处理 GET 请求"""
        path, query = self._parse_path()

        # 主页面
        if path == '' or path == '/':
            self._send_html(HTML_PAGE)
            return

        # API 端点
        if path == '/api/server':
            self._handle_server_info()
        elif path == '/api/status':
            self._handle_status(query)
        elif path == '/api/config':
            self._handle_config()
        elif path == '/api/baselines':
            self._handle_baselines()
        elif path == '/api/alerts':
            self._handle_alerts(query)
        elif path.startswith('/api/chart/latency/'):
            self._handle_chart_latency(path, query)
        elif path.startswith('/api/chart/loss/'):
            self._handle_chart_loss(path, query)
        elif path == '/api/chart/speed':
            self._handle_chart_speed(query)
        else:
            self._send_json({'error': 'Not Found'}, 404)

    def do_POST(self):
        """处理 POST 请求"""
        path, _ = self._parse_path()

        if path == '/api/speed/run':
            self._handle_speed_run()
        elif path == '/api/alert/test':
            self._handle_alert_test()
        else:
            self._send_json({'error': 'Not Found'}, 404)

    def _handle_server_info(self):
        """服务器信息"""
        import subprocess
        running = False
        uptime = None
        try:
            result = subprocess.run(['systemctl', 'is-active', 'route-monitor'],
                                  capture_output=True, text=True, timeout=5)
            running = result.stdout.strip() == 'active'
            if running:
                result = subprocess.run(['systemctl', 'show', 'route-monitor',
                                       '--property=ActiveEnterTimestamp', '--value'],
                                      capture_output=True, text=True, timeout=5)
                start_str = result.stdout.strip()
                if start_str:
                    from datetime import datetime
                    start_ts = datetime.strptime(start_str, '%a %Y-%m-%d %H:%M:%S %Z').timestamp()
                    diff = int(time.time() - start_ts)
                    if diff < 3600:
                        uptime = f"{diff // 60}分钟"
                    elif diff < 86400:
                        uptime = f"{diff // 3600}小时{(diff % 3600) // 60}分钟"
                    else:
                        uptime = f"{diff // 86400}天{(diff % 86400) // 3600}小时"
        except Exception:
            pass

        self._send_json({
            'name': _config.get('server_name', 'Unknown'),
            'region': _config.get('region', ''),
            'running': running,
            'uptime': uptime
        })

    def _handle_status(self, query):
        """当前状态"""
        hours = int(query.get('hours', [1])[0])
        rows = _db.get_stats_summary(hours=hours)
        result = []
        for row in rows:
            host, name, avg, mn, mx, loss, cnt = row
            result.append({
                'host': host,
                'name': name,
                'avg': round(avg, 1) if avg else None,
                'min': round(mn, 1) if mn else None,
                'max': round(mx, 1) if mx else None,
                'loss': round(loss, 1) if loss else None,
                'count': cnt
            })
        self._send_json(result)

    def _handle_config(self):
        """配置信息（去除敏感字段）"""
        safe_config = {k: v for k, v in _config.items() if k not in ('telegram', 'dingtalk')}
        safe_config['telegram'] = {'enabled': _config.get('telegram', {}).get('enabled', False)}
        safe_config['dingtalk'] = {'enabled': _config.get('dingtalk', {}).get('enabled', False)}
        self._send_json(safe_config)

    def _handle_baselines(self):
        """基线数据"""
        targets = _config.get('ping_targets', [])
        result = []
        for t in targets:
            bl = _db.get_baseline(t['host'])
            if bl:
                result.append({
                    'host': t['host'],
                    'name': t['name'],
                    'avg': round(bl[0], 1) if bl[0] else None,
                    'std': round(bl[1], 1) if bl[1] else None,
                    'min': round(bl[2], 1) if bl[2] else None,
                    'max': round(bl[3], 1) if bl[3] else None
                })
        self._send_json(result)

    def _handle_alerts(self, query):
        """告警历史"""
        limit = int(query.get('limit', [20])[0])
        rows = _db.query(
            "SELECT timestamp, alert_type, severity, message FROM alerts ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        result = []
        for row in rows:
            result.append({
                'timestamp': row[0],
                'alert_type': row[1],
                'severity': row[2],
                'message': row[3]
            })
        self._send_json(result)

    def _handle_chart_latency(self, path, query):
        """延迟图表数据"""
        host = path.split('/')[-1]
        hours = int(query.get('hours', [1])[0])
        cutoff = time.time() - hours * 3600

        rows = _db.query(
            "SELECT timestamp, latency_ms FROM ping_results WHERE target_host=? AND timestamp>? AND latency_ms IS NOT NULL ORDER BY timestamp",
            (host, cutoff)
        )

        # 聚合数据（避免数据量过大）
        if len(rows) > 500:
            bucket_size = len(rows) // 500
            aggregated = []
            for i in range(0, len(rows), bucket_size):
                chunk = rows[i:i + bucket_size]
                avg_ts = sum(r[0] for r in chunk) / len(chunk)
                avg_val = sum(r[1] for r in chunk) / len(chunk)
                aggregated.append((avg_ts, avg_val))
            rows = aggregated

        self._send_json({
            'timestamps': [r[0] for r in rows],
            'values': [round(r[1], 1) for r in rows]
        })

    def _handle_chart_loss(self, path, query):
        """丢包图表数据"""
        host = path.split('/')[-1]
        hours = int(query.get('hours', [1])[0])
        cutoff = time.time() - hours * 3600

        rows = _db.query(
            "SELECT timestamp, packet_loss_pct FROM ping_results WHERE target_host=? AND timestamp>? ORDER BY timestamp",
            (host, cutoff)
        )

        if len(rows) > 500:
            bucket_size = len(rows) // 500
            aggregated = []
            for i in range(0, len(rows), bucket_size):
                chunk = rows[i:i + bucket_size]
                avg_ts = sum(r[0] for r in chunk) / len(chunk)
                avg_val = sum(r[1] for r in chunk) / len(chunk)
                aggregated.append((avg_ts, avg_val))
            rows = aggregated

        self._send_json({
            'timestamps': [r[0] for r in rows],
            'values': [round(r[1], 1) for r in rows]
        })

    def _handle_chart_speed(self, query):
        """带宽图表数据"""
        hours = int(query.get('hours', [1])[0])
        cutoff = time.time() - hours * 3600

        rows = _db.query(
            "SELECT timestamp, speed_mbps FROM speed_results WHERE timestamp>? AND speed_mbps IS NOT NULL ORDER BY timestamp",
            (cutoff,)
        )

        self._send_json({
            'timestamps': [r[0] for r in rows],
            'values': [round(r[1], 1) for r in rows]
        })

    def _handle_speed_run(self):
        """触发测速"""
        try:
            from speedtest import test_download_speed
            url = _config.get('speedtest', {}).get('target_url')
            if not url:
                self._send_json({'success': False, 'error': '未配置测速目标'})
                return

            result = test_download_speed(url)
            if result['success']:
                _db.save_speed(url, result['speed_mbps'], result['downloaded_bytes'],
                             result['elapsed_sec'], False)
            self._send_json({
                'success': result['success'],
                'speed_mbps': round(result.get('speed_mbps', 0), 1),
                'downloaded_mb': round(result.get('downloaded_bytes', 0) / 1024 / 1024, 1),
                'elapsed_sec': round(result.get('elapsed_sec', 0), 1)
            })
        except Exception as e:
            logger.error(f"Speedtest error: {e}")
            self._send_json({'success': False, 'error': str(e)})

    def _handle_alert_test(self):
        """测试告警"""
        try:
            from alerter import send_alert
            msg = f"🔔 Web 测试告警\n\n服务器: {_config.get('server_name')}\n时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n如果你看到这条消息，说明告警通道正常！"
            ok = send_alert(_config, msg)
            self._send_json({'ok': ok})
        except Exception as e:
            logger.error(f"Alert test error: {e}")
            self._send_json({'ok': False, 'error': str(e)})


def start_web_server(db, config):
    """启动 Web 服务器（非阻塞）"""
    global _db, _config
    _db = db
    _config = config

    web_cfg = config.get('web', {})
    if not web_cfg.get('enabled', True):
        logger.info("Web server disabled")
        return None

    host = web_cfg.get('host', '0.0.0.0')
    port = web_cfg.get('port', 8080)

    def run():
        try:
            server = HTTPServer((host, port), RequestHandler)
            logger.info(f"Web server started at http://{host}:{port}")
            server.serve_forever()
        except Exception as e:
            logger.error(f"Web server error: {e}")

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread
