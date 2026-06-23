import requests
import time
import logging
import threading

logger = logging.getLogger("tg_bot")

class TelegramBot:
    def __init__(self, token, chat_id, db, config):
        self.token = token
        self.chat_id = str(chat_id)
        self.db = db
        self.config = config
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.last_update_id = 0
        self.muted = False
        self.mute_until = 0
        self._running = False
        self._thread = None

    def start_polling(self):
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info("Telegram bot polling started")

    def stop(self):
        self._running = False

    def _poll_loop(self):
        while self._running:
            try:
                self._poll_once()
            except Exception as e:
                logger.error(f"Poll error: {e}")
            time.sleep(2)

    def _poll_once(self):
        url = f"{self.base_url}/getUpdates"
        params = {"offset": self.last_update_id + 1, "timeout": 1}
        try:
            r = requests.get(url, params=params, timeout=5)
            data = r.json()
            if not data.get("ok"):
                return
            for update in data.get("result", []):
                self.last_update_id = update["update_id"]
                if "callback_query" in update:
                    self._handle_callback(update["callback_query"])
                elif "message" in update:
                    self._handle_message(update["message"])
        except Exception as e:
            logger.error(f"Poll request error: {e}")

    def _handle_message(self, message):
        chat_id = str(message.get("chat", {}).get("id", ""))
        if chat_id != self.chat_id:
            return
        text = message.get("text", "").strip()
        if text in ("/start", "/menu"):
            self._send_menu()
        elif text == "/status":
            self._action_status()
        elif text == "/speed":
            threading.Thread(target=self._action_speed, daemon=True).start()
        elif text == "/baseline":
            self._action_baseline()
        elif text == "/chart":
            self._action_chart()
        elif text == "/geoip":
            threading.Thread(target=self._action_geoip, daemon=True).start()

    def _handle_callback(self, callback_query):
        chat_id = str(callback_query.get("message", {}).get("chat", {}).get("id", ""))
        if chat_id != self.chat_id:
            return
        data = callback_query.get("data", "")
        self._answer_callback(callback_query["id"])
        actions = {
            "status": self._action_status,
            "speed": lambda: threading.Thread(target=self._action_speed, daemon=True).start(),
            "baseline": self._action_baseline,
            "history": self._action_history,
            "mute_1h": lambda: self._action_mute(3600),
            "mute_4h": lambda: self._action_mute(14400),
            "unmute": self._action_unmute,
            "report": self._action_report,
            "menu": self._send_menu,
            "chart": self._action_chart,
            "geoip": lambda: threading.Thread(target=self._action_geoip, daemon=True).start(),
            "chart_1h": lambda: threading.Thread(target=self._action_chart_hours, args=(1,), daemon=True).start(),
            "chart_6h": lambda: threading.Thread(target=self._action_chart_hours, args=(6,), daemon=True).start(),
            "chart_24h": lambda: threading.Thread(target=self._action_chart_hours, args=(24,), daemon=True).start(),
            "test_alert": self._action_test_alert,
        }
        action = actions.get(data)
        if action:
            action()
        else:
            self._send_text(f"未知操作: {data}")

    def _answer_callback(self, callback_id):
        url = f"{self.base_url}/answerCallbackQuery"
        try:
            requests.post(url, json={"callback_query_id": callback_id}, timeout=5)
        except Exception:
            pass

    def send_keyboard(self, text, buttons=None):
        if buttons is None:
            buttons = self._default_buttons()
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "reply_markup": {"inline_keyboard": buttons}
        }
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            logger.error(f"Send keyboard failed: {e}")

    def _send_text(self, text):
        url = f"{self.base_url}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": text}
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            logger.error(f"Send text failed: {e}")

    def _default_buttons(self):
        mute_btn = [{"text": "🔇 静音1小时", "callback_data": "mute_1h"},
                     {"text": "🔇 静音4小时", "callback_data": "mute_4h"}]
        if self.muted and time.time() < self.mute_until:
            remaining = int((self.mute_until - time.time()) / 60)
            mute_btn = [{"text": f"🔕 静音中({remaining}分钟)", "callback_data": "unmute"},
                        {"text": "🔔 取消静音", "callback_data": "unmute"}]
        return [
            [{"text": "📊 当前状态", "callback_data": "status"},
             {"text": "🚀 立即测速", "callback_data": "speed"}],
            [{"text": "📈 基线数据", "callback_data": "baseline"},
             {"text": "📋 历史记录", "callback_data": "history"}],
            [{"text": "📉 趋势图", "callback_data": "chart"},
             {"text": "🗺 路由地图", "callback_data": "geoip"}],
            [{"text": "📝 每日报告", "callback_data": "report"},
             {"text": "🔔 测试告警", "callback_data": "test_alert"}],
            mute_btn,
        ]

    def _send_menu(self):
        self.send_keyboard(
            f"🖥 路由监测控制面板\n\n服务器: {self.config['server_name']}\n\n"
            f"/start - 控制面板\n/status - 当前状态\n/speed - 立即测速\n"
            f"/baseline - 基线数据\n/chart - 趋势图\n/geoip - 路由地图",
            self._default_buttons()
        )

    def _action_status(self):
        summary = self.db.get_stats_summary(hours=1)
        lines = [f"📊 过去1小时状态", f"服务器: {self.config['server_name']}", ""]
        if not summary:
            lines.append("暂无数据")
        else:
            lines.append("目标 | 平均延迟 | 最低 | 最高 | 丢包")
            lines.append("---|---|---|---|---")
            for row in summary:
                host, name, avg, mn, mx, loss, cnt = row
                lines.append(f"{name} | {avg:.1f}ms | {mn:.1f}ms | {mx:.1f}ms | {loss:.1f}%")
        buttons = [[{"text": "◀️ 返回", "callback_data": "menu"}]]
        self.send_keyboard("\n".join(lines), buttons)

    def _action_speed(self):
        self._send_text("🚀 正在测速，请稍候...")
        from speedtest import test_download_speed
        url = self.config.get("speedtest", {}).get("target_url")
        if not url:
            self._send_text("未配置测速目标")
            return
        result = test_download_speed(url)
        if result["success"]:
            self._send_text(
                f"🚀 测速结果\n\n"
                f"速度: {result['speed_mbps']:.1f} Mbps\n"
                f"下载: {result['downloaded_bytes']/1024/1024:.1f} MB\n"
                f"耗时: {result['elapsed_sec']:.1f}s"
            )
        else:
            self._send_text("❌ 测速失败")

    def _action_baseline(self):
        lines = [f"📈 基线数据", f"服务器: {self.config['server_name']}", ""]
        for t in self.config["ping_targets"]:
            host = t["host"]
            name = t["name"]
            bl = self.db.get_baseline(host)
            if bl:
                avg, std, mn, mx = bl[0], bl[1], bl[2], bl[3]
                lines.append(f"{name} ({host})")
                lines.append(f"  平均: {avg:.1f}ms | 抖动: {std:.1f}ms")
                lines.append(f"  范围: {mn:.1f}ms ~ {mx:.1f}ms")
                lines.append("")
            else:
                lines.append(f"{name}: 暂无基线")
        buttons = [[{"text": "◀️ 返回", "callback_data": "menu"}]]
        self.send_keyboard("\n".join(lines), buttons)

    def _action_history(self):
        summary = self.db.get_stats_summary(hours=24)
        lines = [f"📋 过去24小时统计", f"服务器: {self.config['server_name']}", ""]
        if not summary:
            lines.append("暂无数据")
        else:
            lines.append("目标 | 平均延迟 | 最低 | 最高 | 丢包 | 样本数")
            lines.append("---|---|---|---|---|---")
            for row in summary:
                host, name, avg, mn, mx, loss, cnt = row
                lines.append(f"{name} | {avg:.1f}ms | {mn:.1f}ms | {mx:.1f}ms | {loss:.1f}% | {cnt}")
        buttons = [[{"text": "◀️ 返回", "callback_data": "menu"}]]
        self.send_keyboard("\n".join(lines), buttons)

    def _action_report(self):
        summary = self.db.get_stats_summary(hours=24)
        if not summary:
            self._send_text("暂无数据，无法生成报告")
            return
        from alerter import build_daily_report
        report = build_daily_report(self.config, summary)
        self._send_text(report)

    def _action_chart(self):
        buttons = [
            [{"text": "1小时", "callback_data": "chart_1h"},
             {"text": "6小时", "callback_data": "chart_6h"},
             {"text": "24小时", "callback_data": "chart_24h"}],
            [{"text": "◀️ 返回", "callback_data": "menu"}]
        ]
        self.send_keyboard("📉 选择时间范围:", buttons)

    def _action_chart_hours(self, hours):
        from chart import generate_latency_chart, generate_loss_chart, generate_speed_chart
        self._send_text(f"📉 正在生成 {hours} 小时趋势图...")
        for t in self.config["ping_targets"][:4]:
            chart_text, _ = generate_latency_chart(self.db, t["host"], t["name"], hours=hours)
            if chart_text:
                self._send_text(chart_text)
            loss_chart = generate_loss_chart(self.db, t["host"], t["name"], hours=hours)
            if loss_chart:
                self._send_text(loss_chart)
            time.sleep(0.1)
        speed_chart = generate_speed_chart(self.db, hours=hours)
        if speed_chart:
            self._send_text(speed_chart)
        buttons = [[{"text": "◀️ 返回", "callback_data": "menu"}]]
        self.send_keyboard("✅ 趋势图生成完毕", buttons)

    def _action_geoip(self):
        from geoip import format_traceroute_result, get_path_countries
        from tracer import traceroute
        self._send_text("🗺 正在执行路由追踪，请稍候...")
        for t in self.config.get("traceroute_targets", [])[:2]:
            result = traceroute(t["host"])
            if result["success"] and result["hops"]:
                geo_text = format_traceroute_result(t["name"], result["hops"])
                countries = get_path_countries(result["hops"])
                if countries:
                    geo_text += f"\n\n🌍 经过: {' → '.join(countries)}"
                self._send_text(geo_text)
            else:
                self._send_text(f"❌ {t['name']} 追踪失败")
            time.sleep(0.1)
        buttons = [[{"text": "◀️ 返回", "callback_data": "menu"}]]
        self.send_keyboard("✅ 路由地图生成完毕", buttons)

    def _action_mute(self, seconds):
        self.muted = True
        self.mute_until = time.time() + seconds
        hours = seconds // 3600
        self._send_text(f"🔇 告警已静音 {hours} 小时")
        logger.info(f"Alerts muted for {hours} hours")

    def _action_unmute(self):
        self.muted = False
        self.mute_until = 0
        self._send_text("🔔 告警已恢复")
        logger.info("Alerts unmuted")

    def is_muted(self):
        if not self.muted:
            return False
        if time.time() >= self.mute_until:
            self.muted = False
            return False
        return True

    def _action_test_alert(self):
        from alerter import send_alert
        msg = f"🔔 路由监测测试消息\n\n服务器: {self.config['server_name']}\n状态: 告警通道正常\n\n如果你看到这条消息，说明一切正常！"
        if send_alert(self.config, msg):
            self._send_text("✅ 测试消息已发送，请检查 TG 和钉钉是否收到")
        else:
            self._send_text("❌ 发送失败，请检查配置")
