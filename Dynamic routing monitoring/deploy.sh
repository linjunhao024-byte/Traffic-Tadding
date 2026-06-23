#!/bin/bash
set -e

INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_FILE="$INSTALL_DIR/config.local.json"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

show_logo() {
    echo -e "${CYAN}"
    echo "    ____  _   _ ___________  ____  _   _ ______ _____   ____ ___  ____  _____"
    echo "   |  _ \| | | |_   _| ___ \/ ___|| | | |  ____|  _  \ / ___/ _ \|  _ \| ____|"
    echo "   | |_) | | | | | | | |_/ / |  _ | |_| | |__  | |_) | |  | | | | |_) |  _|"
    echo "   |  _ <| | | | | | |    /| |_| ||  _  |  __| |  _ <| |__| |_| |  _ <| |___"
    echo "   | |_) | |_| | | | | |\ \|  _| || | | | |    | |_) |\____\___/| |_\ \_____|"
    echo "   |____/ \___/  |_| |_| \_\_|   |_| |_|_|    |____/      \___/ \____/      "
    echo -e "${NC}"
    echo -e "${BOLD}                        Dynamic Routing Monitoring${NC}"
    echo -e "${BOLD}                            动态路由监测工具${NC}"
    echo ""
}

# ============================================================================
# 环境检查
# ============================================================================

check_environment() {
    echo -e "${CYAN}+===========================================================================+${NC}"
    printf "${CYAN}|${NC}  ${BOLD}%-69s${NC}${CYAN}|${NC}\n" "环境检查"
    echo -e "${CYAN}+---------------------------------------------------------------------------+${NC}"

    local ok=true

    # 检查 Python
    if command -v python3 &> /dev/null; then
        local py_ver=$(python3 --version 2>&1 | awk '{print $2}')
        printf "${CYAN}|${NC}  ${GREEN}[✓]${NC} Python %-59s${CYAN}|${NC}\n" "$py_ver"
    else
        printf "${CYAN}|${NC}  ${RED}[✗]${NC} Python 未安装                                            ${CYAN}|${NC}\n"
        ok=false
    fi

    # 检查 pip
    if command -v pip3 &> /dev/null || command -v pip &> /dev/null; then
        printf "${CYAN}|${NC}  ${GREEN}[✓]${NC} pip                                                   ${CYAN}|${NC}\n"
    else
        printf "${CYAN}|${NC}  ${RED}[✗]${NC} pip 未安装                                              ${CYAN}|${NC}\n"
        ok=false
    fi

    # 检查 traceroute
    if command -v traceroute &> /dev/null; then
        printf "${CYAN}|${NC}  ${GREEN}[✓]${NC} traceroute                                            ${CYAN}|${NC}\n"
    else
        printf "${CYAN}|${NC}  ${YELLOW}[!]${NC} traceroute 未安装（将自动安装）                        ${CYAN}|${NC}\n"
    fi

    # 检查 systemctl
    if command -v systemctl &> /dev/null; then
        printf "${CYAN}|${NC}  ${GREEN}[✓]${NC} systemd                                               ${CYAN}|${NC}\n"
    else
        printf "${CYAN}|${NC}  ${RED}[✗]${NC} systemd 不可用                                          ${CYAN}|${NC}\n"
        ok=false
    fi

    echo -e "${CYAN}+===========================================================================+${NC}"

    if ! $ok; then
        echo ""
        echo -e "  ${RED}环境检查失败，请先安装缺失的依赖${NC}"
        exit 1
    fi
}

# ============================================================================
# 安装步骤
# ============================================================================

install_dependencies() {
    echo ""
    echo -e "${CYAN}+===========================================================================+${NC}"
    printf "${CYAN}|${NC}  ${BOLD}%-69s${NC}${CYAN}|${NC}\n" "[1/5] 安装系统依赖"
    echo -e "${CYAN}+---------------------------------------------------------------------------+${NC}"

    if command -v apt-get &> /dev/null; then
        printf "${CYAN}|${NC}  %-69s${CYAN}|${NC}\n" "检测到 apt 包管理器"
        apt-get update -qq > /dev/null 2>&1
        apt-get install -y -qq python3 python3-pip python3-venv traceroute unzip curl > /dev/null 2>&1
    elif command -v yum &> /dev/null; then
        printf "${CYAN}|${NC}  %-69s${CYAN}|${NC}\n" "检测到 yum 包管理器"
        yum install -y python3 python3-pip traceroute unzip curl > /dev/null 2>&1
    elif command -v dnf &> /dev/null; then
        printf "${CYAN}|${NC}  %-69s${CYAN}|${NC}\n" "检测到 dnf 包管理器"
        dnf install -y python3 python3-pip traceroute unzip curl > /dev/null 2>&1
    fi

    printf "${CYAN}|${NC}  ${GREEN}[✓]${NC} 系统依赖安装完成                                           ${CYAN}|${NC}\n"
    echo -e "${CYAN}+===========================================================================+${NC}"
}

setup_python_env() {
    echo ""
    echo -e "${CYAN}+===========================================================================+${NC}"
    printf "${CYAN}|${NC}  ${BOLD}%-69s${NC}${CYAN}|${NC}\n" "[2/5] 创建 Python 虚拟环境"
    echo -e "${CYAN}+---------------------------------------------------------------------------+${NC}"

    if [ ! -d "$INSTALL_DIR/venv" ]; then
        printf "${CYAN}|${NC}  %-69s${CYAN}|${NC}\n" "正在创建虚拟环境..."
        python3 -m venv "$INSTALL_DIR/venv"
    else
        printf "${CYAN}|${NC}  %-69s${CYAN}|${NC}\n" "虚拟环境已存在，跳过创建"
    fi

    printf "${CYAN}|${NC}  %-69s${CYAN}|${NC}\n" "正在安装 Python 依赖..."
    source "$INSTALL_DIR/venv/bin/activate"
    pip install -r "$INSTALL_DIR/requirements.txt" --quiet 2>/dev/null
    deactivate

    printf "${CYAN}|${NC}  ${GREEN}[✓]${NC} Python 环境配置完成                                         ${CYAN}|${NC}\n"
    echo -e "${CYAN}+===========================================================================+${NC}"
}

configure_params() {
    echo ""
    echo -e "${CYAN}+===========================================================================+${NC}"
    printf "${CYAN}|${NC}  ${BOLD}%-69s${NC}${CYAN}|${NC}\n" "[3/5] 配置参数"
    echo -e "${CYAN}+---------------------------------------------------------------------------+${NC}"
    echo -e "${CYAN}|${NC}                                                              ${CYAN}|${NC}"

    # 如果已有配置，询问是否保留
    if [ -f "$CONFIG_FILE" ]; then
        printf "${CYAN}|${NC}  ${YELLOW}[!]${NC} 检测到已有配置文件                                        ${CYAN}|${NC}\n"
        echo -e "${CYAN}|${NC}                                                              ${CYAN}|${NC}"
        echo -ne "${CYAN}|${NC}  是否重新配置？(y/N) [默认: N]: "
        read reconfig
        if [ "$reconfig" != "y" ] && [ "$reconfig" != "Y" ]; then
            printf "${CYAN}|${NC}  ${GREEN}[✓]${NC} 使用已有配置                                            ${CYAN}|${NC}\n"
            echo -e "${CYAN}|${NC}                                                              ${CYAN}|${NC}"
            echo -e "${CYAN}+===========================================================================+${NC}"
            return
        fi
        rm -f "$CONFIG_FILE"
    fi

    # 服务器名称
    echo -ne "${CYAN}|${NC}  服务器名称 [默认: $(hostname)]: "
    read server_name
    if [ -z "$server_name" ]; then
        server_name="server-$(hostname | tail -c 8)"
    fi
    echo -e "${CYAN}|${NC}                                                              ${CYAN}|${NC}"

    # Telegram 配置
    printf "${CYAN}|${NC}  ${BOLD}%-69s${NC}${CYAN}|${NC}\n" "Telegram 告警配置"
    echo -ne "${CYAN}|${NC}  启用 Telegram？(y/N) [默认: N]: "
    read enable_tg
    tg_enabled="false"
    tg_token=""
    tg_chatid=""
    if [ "$enable_tg" = "y" ] || [ "$enable_tg" = "Y" ]; then
        tg_enabled="true"
        echo -ne "${CYAN}|${NC}  Bot Token: "
        read tg_token
        echo -ne "${CYAN}|${NC}  Chat ID: "
        read tg_chatid
    fi
    echo -e "${CYAN}|${NC}                                                              ${CYAN}|${NC}"

    # 钉钉配置
    printf "${CYAN}|${NC}  ${BOLD}%-69s${NC}${CYAN}|${NC}\n" "钉钉告警配置"
    echo -ne "${CYAN}|${NC}  启用钉钉？(y/N) [默认: N]: "
    read enable_dt
    dt_enabled="false"
    dt_webhook=""
    dt_secret=""
    if [ "$enable_dt" = "y" ] || [ "$enable_dt" = "Y" ]; then
        dt_enabled="true"
        echo -ne "${CYAN}|${NC}  Webhook URL: "
        read dt_webhook
        echo -ne "${CYAN}|${NC}  加签密钥 (可留空): "
        read dt_secret
    fi
    echo -e "${CYAN}|${NC}                                                              ${CYAN}|${NC}"

    # 自定义快捷命令
    echo -ne "${CYAN}|${NC}  管理命令名称 [默认: monitor]: "
    read cmd_name
    CMD_NAME="${cmd_name:-monitor}"
    CMD_NAME="${CMD_NAME:0:7}"
    echo -e "${CYAN}|${NC}                                                              ${CYAN}|${NC}"

    # 生成配置文件
    cat > "$CONFIG_FILE" <<JSONEOF
{
  "server_name": "$server_name",
  "region": "tokyo",
  "mode": "full",
  "ping_targets": [
    {"host": "8.8.8.8", "name": "Google DNS"},
    {"host": "8.8.4.4", "name": "Google DNS-2"},
    {"host": "1.1.1.1", "name": "Cloudflare"},
    {"host": "1.0.0.1", "name": "Cloudflare-2"},
    {"host": "208.67.222.222", "name": "OpenDNS"},
    {"host": "168.63.129.16", "name": "Azure"},
    {"host": "13.107.42.14", "name": "Microsoft"},
    {"host": "99.86.1.150", "name": "Amazon CloudFront"}
  ],
  "traceroute_targets": [
    {"host": "8.8.8.8", "name": "Google"},
    {"host": "1.1.1.1", "name": "Cloudflare"},
    {"host": "13.107.42.14", "name": "Microsoft"}
  ],
  "speedtest": {
    "enabled": true,
    "interval_sec": 1800,
    "target_url": "http://speedtest.tele2.net/10MB.zip"
  },
  "monitoring": {
    "ping_interval_sec": 5,
    "ping_count": 10,
    "traceroute_interval_sec": 180,
    "baseline_sample_count": 100
  },
  "alert": {
    "latency_multiplier": 1.8,
    "latency_abs_threshold_ms": 80,
    "packet_loss_threshold_pct": 3.0,
    "speed_drop_threshold_pct": 50,
    "consecutive_failures": 3,
    "cooldown_sec": 300,
    "recovery_notify": true
  },
  "telegram": {
    "enabled": $tg_enabled,
    "bot_token": "$tg_token",
    "chat_id": "$tg_chatid"
  },
  "dingtalk": {
    "enabled": $dt_enabled,
    "webhook_url": "$dt_webhook",
    "secret": "$dt_secret"
  },
  "database": {
    "path": "monitor.db",
    "cleanup_days": 30
  },
  "log": {
    "level": "INFO",
    "file": "monitor.log",
    "max_size_mb": 50,
    "backup_count": 5
  }
}
JSONEOF

    printf "${CYAN}|${NC}  ${GREEN}[✓]${NC} 配置已保存                                                ${CYAN}|${NC}\n"

    # 显示配置摘要
    echo -e "${CYAN}|${NC}                                                              ${CYAN}|${NC}"
    echo -e "${CYAN}+---------------------------------------------------------------------------+${NC}"
    printf "${CYAN}|${NC}  ${BOLD}%-69s${NC}${CYAN}|${NC}\n" "配置摘要"
    echo -e "${CYAN}+---------------------------------------------------------------------------+${NC}"
    printf "${CYAN}|${NC}    服务器名称  ${GREEN}%-53s${NC}${CYAN}|${NC}\n" "$server_name"
    printf "${CYAN}|${NC}    Telegram    ${GREEN}%-53s${NC}${CYAN}|${NC}\n" "$tg_enabled"
    printf "${CYAN}|${NC}    钉钉        ${GREEN}%-53s${NC}${CYAN}|${NC}\n" "$dt_enabled"
    printf "${CYAN}|${NC}    管理命令    ${GREEN}%-53s${NC}${CYAN}|${NC}\n" "$CMD_NAME"
    echo -e "${CYAN}|${NC}                                                              ${CYAN}|${NC}"
    echo -e "${CYAN}+===========================================================================+${NC}"
}

setup_systemd() {
    echo ""
    echo -e "${CYAN}+===========================================================================+${NC}"
    printf "${CYAN}|${NC}  ${BOLD}%-69s${NC}${CYAN}|${NC}\n" "[4/5] 配置系统服务"
    echo -e "${CYAN}+---------------------------------------------------------------------------+${NC}"

    PYTHON_PATH="$INSTALL_DIR/venv/bin/python3"

    cat > /tmp/route-monitor.service <<SVCEOF
[Unit]
Description=Dynamic Routing Monitor
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$INSTALL_DIR
ExecStart=$PYTHON_PATH $INSTALL_DIR/src/main.py
Restart=always
RestartSec=10
Nice=19
MemoryMax=100M

[Install]
WantedBy=multi-user.target
SVCEOF

    mv /tmp/route-monitor.service /etc/systemd/system/route-monitor.service
    systemctl daemon-reload
    systemctl enable route-monitor > /dev/null 2>&1

    printf "${CYAN}|${NC}  ${GREEN}[✓]${NC} 系统服务配置完成                                            ${CYAN}|${NC}\n"
    echo -e "${CYAN}+===========================================================================+${NC}"
}

install_command() {
    echo ""
    echo -e "${CYAN}+===========================================================================+${NC}"
    printf "${CYAN}|${NC}  ${BOLD}%-69s${NC}${CYAN}|${NC}\n" "[5/5] 安装管理命令"
    echo -e "${CYAN}+---------------------------------------------------------------------------+${NC}"

    if [ -f "$INSTALL_DIR/monitor.sh" ]; then
        chmod +x "$INSTALL_DIR/monitor.sh"
        ln -sf "$INSTALL_DIR/monitor.sh" "/usr/local/bin/${CMD_NAME}"
        printf "${CYAN}|${NC}  ${GREEN}[✓]${NC} 管理命令: ${CMD_NAME}                                             ${CYAN}|${NC}\n"
    fi

    echo -e "${CYAN}+===========================================================================+${NC}"
}

start_service() {
    echo ""
    echo -e "${CYAN}+===========================================================================+${NC}"
    printf "${CYAN}|${NC}  ${BOLD}%-69s${NC}${CYAN}|${NC}\n" "启动服务"
    echo -e "${CYAN}+---------------------------------------------------------------------------+${NC}"

    systemctl restart route-monitor
    sleep 2

    if systemctl is-active --quiet route-monitor; then
        printf "${CYAN}|${NC}  ${GREEN}[✓]${NC} 服务启动成功                                              ${CYAN}|${NC}\n"
    else
        printf "${CYAN}|${NC}  ${RED}[✗]${NC} 服务启动失败                                              ${CYAN}|${NC}\n"
        printf "${CYAN}|${NC}  查看日志: journalctl -u route-monitor -n 20                   ${CYAN}|${NC}\n"
    fi

    echo -e "${CYAN}+===========================================================================+${NC}"
}

test_alert() {
    echo ""
    echo -e "${CYAN}+===========================================================================+${NC}"
    printf "${CYAN}|${NC}  ${BOLD}%-69s${NC}${CYAN}|${NC}\n" "发送测试消息"
    echo -e "${CYAN}+---------------------------------------------------------------------------+${NC}"

    PYTHON="$INSTALL_DIR/venv/bin/python3"
    result=$($PYTHON -c "
import sys, os
sys.path.insert(0, '$INSTALL_DIR/src')
os.chdir('$INSTALL_DIR')
from config import load_config
from alerter import send_alert
config = load_config()
msg = '🔔 路由监测测试消息\n\n服务器: ' + config['server_name'] + '\n状态: 告警通道配置正常\n\n如果你看到这条消息，说明部署成功！'
ok = send_alert(config, msg)
print('ok' if ok else 'fail')
" 2>/dev/null)

    if [ "$result" = "ok" ]; then
        printf "${CYAN}|${NC}  ${GREEN}[✓]${NC} 测试消息发送成功                                          ${CYAN}|${NC}\n"
    else
        printf "${CYAN}|${NC}  ${RED}[✗]${NC} 测试消息发送失败，请检查配置                              ${CYAN}|${NC}\n"
    fi

    echo -e "${CYAN}+===========================================================================+${NC}"
}

show_success() {
    echo ""
    echo -e "${GREEN}+===========================================================================+${NC}"
    echo -e "${GREEN}|${NC}                                                                          ${GREEN}|${NC}"
    echo -e "${GREEN}|${NC}                    🎉  ${BOLD}部署成功！${NC}  🎉                                 ${GREEN}|${NC}"
    echo -e "${GREEN}|${NC}                                                                          ${GREEN}|${NC}"
    echo -e "${GREEN}+===========================================================================+${NC}"
    echo -e "${GREEN}|${NC}                                                                          ${GREEN}|${NC}"
    echo -e "${GREEN}|${NC}  ${BOLD}管理命令:${NC}                                                               ${GREEN}|${NC}"
    printf "${GREEN}|${NC}    ${CYAN}%-12s${NC}  呼出管理菜单                                           ${GREEN}|${NC}\n" "${CMD_NAME}"
    echo -e "${GREEN}|${NC}                                                                          ${GREEN}|${NC}"
    echo -e "${GREEN}|${NC}  ${BOLD}常用命令:${NC}                                                               ${GREEN}|${NC}"
    printf "${GREEN}|${NC}    ${CYAN}%-44s${NC} 查看状态   ${GREEN}|${NC}\n" "systemctl status route-monitor"
    printf "${GREEN}|${NC}    ${CYAN}%-44s${NC} 查看日志   ${GREEN}|${NC}\n" "journalctl -u route-monitor -f"
    printf "${GREEN}|${NC}    ${CYAN}%-44s${NC} 重启服务   ${GREEN}|${NC}\n" "systemctl restart route-monitor"
    echo -e "${GREEN}|${NC}                                                                          ${GREEN}|${NC}"
    echo -e "${GREEN}+===========================================================================+${NC}"
    echo ""
}

# ============================================================================
# 主流程
# ============================================================================

main() {
    show_logo
    check_environment
    install_dependencies
    setup_python_env
    configure_params
    setup_systemd
    install_command
    start_service
    test_alert
    show_success
}

main "$@"
