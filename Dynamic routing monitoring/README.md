# AWS 动态路由监测工具

监测 AWS 东京服务器的网络路由变化，检测绕路和网络质量下降，通过 Telegram/钉钉实时告警。

## 功能

- **延迟监测**: 周期性 ping 多个目标，检测延迟异常和抖动
- **丢包监测**: 检测丢包率突增
- **路径追踪**: traceroute 检测路由路径变化（绕路）
- **带宽监测**: 定期测速，检测带宽下降
- **GeoIP 路由地图**: 显示路由经过的国家/地区
- **历史趋势图**: 延迟/丢包/带宽趋势可视化
- **基线对比**: 自动学习正常状态，偏离时告警
- **恢复通知**: 网络恢复正常时也会通知
- **每日报告**: 每天自动发送一份统计报告
- **TG 控制面板**: 在 Telegram 里直接操作，不用登录服务器

## 一键部署

SSH 登录服务器后，直接执行：

```bash
apt install -y unzip && \
wget https://github.com/linjunhao024-byte/Dynamic-routing-monitoring/archive/refs/heads/main.zip && \
unzip main.zip && \
mv Dynamic-routing-monitoring-main route-monitor && \
rm main.zip && \
cd route-monitor && \
bash deploy.sh
```

脚本会自动：
1. 安装系统依赖
2. 创建 Python 虚拟环境
3. 交互式询问配置（服务器名称、TG/钉钉信息）
4. 配置系统服务
5. 启动服务

## 重新配置

```bash
cd ~/route-monitor && bash deploy.sh
```

已有的配置会提示是否重新配置。

## Telegram 控制面板

给 bot 发 `/start` 弹出控制面板：

| 按钮 | 功能 |
|------|------|
| 📊 当前状态 | 查看过去1小时延迟/丢包 |
| 🚀 立即测速 | 执行带宽测速 |
| 📈 基线数据 | 查看各目标延迟基线 |
| 📋 历史记录 | 过去24小时统计 |
| 📉 趋势图 | 延迟/丢包/带宽趋势图 |
| 🗺 路由地图 | traceroute + GeoIP 地理位置 |
| 📝 每日报告 | 手动生成每日报告 |
| 🔇 静音 | 暂停告警推送 |

## 常用命令

```bash
# 查看状态
systemctl status route-monitor

# 查看实时日志
journalctl -u route-monitor -f

# 重启
systemctl restart route-monitor

# 停止
systemctl stop route-monitor

# 重新配置
bash ~/route-monitor/deploy.sh
```

## 更新

```bash
cd ~ && \
rm -rf route-monitor && \
wget https://github.com/linjunhao024-byte/Dynamic-routing-monitoring/archive/refs/heads/main.zip && \
unzip main.zip && \
mv Dynamic-routing-monitoring-main route-monitor && \
rm main.zip && \
cd route-monitor && \
bash deploy.sh
```

选择不重新配置即可保留原有设置。

## 卸载

```bash
systemctl stop route-monitor
systemctl disable route-monitor
rm /etc/systemd/system/route-monitor.service
systemctl daemon-reload
rm -rf ~/route-monitor
```
