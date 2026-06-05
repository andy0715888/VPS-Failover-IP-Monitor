cat > install.sh << 'EOF'
#!/bin/bash
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  VPS Failover IP Monitor 安装脚本${NC}"
echo -e "${GREEN}========================================${NC}"

if [ "$EUID" -ne 0 ]; then
    echo "请使用 root 用户运行此脚本"
    exit 1
fi

echo -e "${YELLOW}[1/5] 安装系统依赖...${NC}"
apt update
apt install -y python3 python3-pip git curl iputils-ping net-tools

echo -e "${YELLOW}[2/5] 克隆项目...${NC}"
rm -rf /opt/ip_failover
git clone https://github.com/andy0715888/VPS-Failover-IP-Monitor.git /opt/ip_failover

echo -e "${YELLOW}[3/5] 安装 Python 依赖...${NC}"
pip3 install flask requests --break-system-packages

echo -e "${YELLOW}[4/5] 创建配置文件...${NC}"
if [ ! -f /opt/ip_failover/config.json ]; then
    cat > /opt/ip_failover/config.json << 'CONFIGEOF'
{
    "monitor": {
        "targets": ["1.1.1.1", "8.8.8.8"],
        "interval_sec": 10,
        "ping_count": 3,
        "timeout_sec": 2,
        "failure_threshold": 5
    },
    "network": {
        "interface": "",
        "gateway": "",
        "current_src_ip": "",
        "available_ips": []
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
CONFIGEOF
fi

echo -e "${YELLOW}[5/5] 创建 systemd 服务...${NC}"
cat > /etc/systemd/system/ip_failover.service << EOF
[Unit]
Description=VPS Failover IP Monitor
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/ip_failover
ExecStart=/usr/bin/python3 /opt/ip_failover/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ip_failover
systemctl restart ip_failover

if command -v ufw &> /dev/null; then
    ufw allow 5000/tcp
fi

PUBLIC_IP=$(curl -s ifconfig.me)
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}安装完成！${NC}"
echo -e "${GREEN}Web 面板地址: http://$PUBLIC_IP:5000${NC}"
echo -e "${YELLOW}首次访问请设置管理员密码${NC}"
echo -e "${GREEN}========================================${NC}"
EOF
chmod +x install.sh
