#!/bin/bash
# VPS Failover IP Monitor - 一键安装脚本
# 适用于 Ubuntu/Debian

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  VPS Failover IP Monitor 安装脚本${NC}"
echo -e "${GREEN}========================================${NC}"

# 检查是否以 root 运行
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}请使用 root 用户运行此脚本 (sudo bash install.sh)${NC}"
    exit 1
fi

# 安装依赖
echo -e "${YELLOW}[1/6] 安装系统依赖...${NC}"
apt update
apt install -y python3 python3-pip git curl iputils-ping net-tools

# 创建安装目录
INSTALL_DIR="/opt/ip_failover"
echo -e "${YELLOW}[2/6] 创建目录 $INSTALL_DIR ...${NC}"
mkdir -p $INSTALL_DIR
mkdir -p $INSTALL_DIR/logs
mkdir -p $INSTALL_DIR/static
mkdir -p $INSTALL_DIR/templates
mkdir -p $INSTALL_DIR/modules

# 复制本脚本所在目录的所有文件到安装目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo -e "${YELLOW}[3/6] 复制项目文件...${NC}"
cp -r $SCRIPT_DIR/* $INSTALL_DIR/ 2>/dev/null || true

# 安装 Python 依赖
echo -e "${YELLOW}[4/6] 安装 Python 依赖...${NC}"
pip3 install flask requests ping3 netifaces --break-system-packages

# 检测网络配置
echo -e "${YELLOW}[5/6] 自动检测网络配置...${NC}"
DEFAULT_IFACE=$(ip route show default | awk '{print $5}' | head -n1)
DEFAULT_GATEWAY=$(ip route show default | awk '{print $3}')
CURRENT_IP=$(ip -4 addr show $DEFAULT_IFACE | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -n1)
# 获取所有辅助 IP（secondary）
AVAILABLE_IPS=$(ip -4 addr show $DEFAULT_IFACE | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | tr '\n' ' ')

# 生成默认配置文件
cat > $INSTALL_DIR/config.json <<EOF
{
    "monitor": {
        "targets": ["1.1.1.1", "8.8.8.8", "baidu.com"],
        "interval_sec": 10,
        "ping_count": 3,
        "timeout_sec": 2,
        "failure_threshold": 5
    },
    "network": {
        "interface": "$DEFAULT_IFACE",
        "gateway": "$DEFAULT_GATEWAY",
        "current_src_ip": "$CURRENT_IP",
        "available_ips": [$(echo $AVAILABLE_IPS | sed 's/ /, /g' | sed 's/,$//' | sed 's/^/"/;s/ /","/g;s/$/"/')]
    },
    "cloudflare": {
        "api_token": "",
        "zone_id": "",
        "domain": "example.com",
        "delete_old_records": true,
        "add_new_record": true,
        "record_ttl": 120
    },
    "web": {
        "port": 5000,
        "username": "admin",
        "password_hash": ""
    }
}
EOF

# 创建 systemd 服务
echo -e "${YELLOW}[6/6] 创建 systemd 服务...${NC}"
cat > /etc/systemd/system/ip_failover.service <<EOF
[Unit]
Description=VPS Failover IP Monitor
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/python3 $INSTALL_DIR/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ip_failover
systemctl start ip_failover

# 开放防火墙端口（如果 ufw 存在）
if command -v ufw &> /dev/null; then
    PORT=$(grep -oP '"port":\s*\K\d+' $INSTALL_DIR/config.json | head -n1)
    ufw allow $PORT/tcp
    echo -e "${GREEN}已开放端口 $PORT${NC}"
fi

# 获取本机公网 IP
PUBLIC_IP=$(curl -s ifconfig.me)

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}安装完成！${NC}"
echo -e "${GREEN}Web 面板地址: http://$PUBLIC_IP:5000${NC}"
echo -e "${YELLOW}首次访问请设置管理员密码${NC}"
echo -e "${GREEN}服务状态: systemctl status ip_failover${NC}"
echo -e "${GREEN}日志目录: $INSTALL_DIR/logs/${NC}"
echo -e "${GREEN}========================================${NC}"
