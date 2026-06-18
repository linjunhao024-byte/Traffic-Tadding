<p align="center">
  <h1 align="center">🛡️ Traffic Padding Micro-Service</h1>
  <p align="center">流量伪装微服务 — 使云服务器上下行流量比例自然化</p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.6+-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/Platform-Linux-lightgrey?logo=linux" alt="Linux">
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/Dependencies-Zero-brightgreen" alt="Zero Deps">
</p>

---

## 🎯 解决的问题

国内云服务器（代理/中转机）的上下行流量比例过于对等（1:1），容易被防火墙识别。

**解决方案**：全天候随机微量碎片填充（Micro-padding），主动发起微量下载，人为制造自然的下行流量特征。

---

## ⚡ 一键安装

```bash
cd /tmp && wget -q https://raw.githubusercontent.com/linjunhao024-byte/traffic-padding/main/install.sh -O install.sh && wget -q https://raw.githubusercontent.com/linjunhao024-byte/traffic-padding/main/main.py -O main.py && sudo bash install.sh
```

或者分步执行：

```bash
# 下载安装脚本和主程序
wget https://raw.githubusercontent.com/linjunhao024-byte/traffic-padding/main/install.sh
wget https://raw.githubusercontent.com/linjunhao024-byte/traffic-padding/main/main.py

# 执行安装
sudo bash install.sh
```

---

## 📋 安装过程

安装脚本会引导你完成 3 项配置：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| 网卡 | 自动检测，回车确认 | eth0 |
| 流量比例 | 下行:上行 | 1:3 |
| 每日配额 | 最大额外下载量 | 10 GB |

---

## 🎮 管理

安装后输入 `tpm` 呼出交互式管理菜单：

```
╔══════════════════════════════════════════════════════════════╗
║          Traffic Padding Manager (tpm)                      ║
╚══════════════════════════════════════════════════════════════╝

状态: 运行中  自启: 已启用
网卡:eth0 比例:1:3 配额:10GB
今日: 0.123GB

服务控制     日志         配置         其他
  [1] 状态      [5] 实时日志  [7] 查看配置  [11] 自启开
  [2] 启动      [6] 最近日志  [8] 编辑配置  [12] 自启关
  [3] 停止                    [9] 查看配额  [13] 网卡测试
  [4] 重启                   [10] 重置配额  [0] 退出
```

---

## 📁 文件结构

```
GitHub 仓库                        服务器安装后
traffic-padding/                   /opt/traffic-padding/
├── install.sh  ──────────────────►├── main.py
├── main.py                        └── tpm.sh (自动生成)
└── README.md                           │
                                   /usr/local/bin/tpm (快捷命令)
                                        │
                                   /etc/traffic-padding/
                                   ├── config.json
                                   ├── usage.json
                                   └── url_health.json
```

---

## ⚙️ 配置说明

`/etc/traffic-padding/config.json` — **修改后 5 分钟自动生效，无需重启**

```json
{
    "interface": "eth0",              // 监控网卡
    "target_ratio": 3.0,              // 下行:上行比例
    "max_daily_extra_gb": 10.0,       // 每日配额 (GB)
    "min_task_bytes": 2097152,         // 最小任务 (2MB)
    "max_task_bytes": 15728640,        // 最大任务 (15MB)
    "jitter_base": 5,                 // 基础休眠 (秒)
    "jitter_range": 25,               // 随机抖动范围
    "enable_night_mode": true,        // 凌晨 2-5 点降频
    "night_multiplier": 5.0,          // 降频倍数
    "peak_hours": [19, 20, 21, 22],   // 晚高峰时段
    "peak_multiplier": 0.6            // 高峰加速倍数
}
```

---

## 🔧 技术特性

| 特性 | 说明 |
|------|------|
| 零依赖 | 仅使用 Python 标准库 |
| 极低资源 | CPU 最低优先级，内存上限 50MB |
| 国内优先 | 优先使用腾讯/阿里/华为 CDN |
| 健康检查 | URL 成功率追踪，自动降权失败源 |
| 配置热重载 | 修改配置 5 分钟内自动生效 |
| 滑动窗口 | 流量统计平滑，减少误判 |
| 溢出检测 | 兼容 32 位系统计数器溢出 |
| 优雅退出 | 支持 SIGTERM 信号处理 |

---

## 🗑️ 卸载

```bash
sudo bash install.sh uninstall
```

---

## 📄 License

MIT
