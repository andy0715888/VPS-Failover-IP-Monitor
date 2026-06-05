import subprocess
import netifaces as ni
from modules.config import load_config, save_config

def get_default_gateway(iface):
    """从路由表获取指定网卡的网关"""
    try:
        result = subprocess.run(['ip', 'route', 'show', 'default'], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if f'dev {iface}' in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == 'via' and i+1 < len(parts):
                        return parts[i+1]
    except:
        pass
    return None

def switch_outgoing_ip(config):
    """切换默认路由的源 IP，返回新 IP，失败返回 None"""
    iface = config['network']['interface']
    gateway = config['network']['gateway']
    current = config['network']['current_src_ip']
    available = config['network']['available_ips']

    if not available:
        return None

    # 选择下一个可用的 IP（轮换）
    try:
        idx = available.index(current)
        new_ip = available[(idx + 1) % len(available)]
    except ValueError:
        new_ip = available[0]

    if new_ip == current:
        # 没有其他 IP，无法切换
        return None

    # 执行路由替换
    cmd = f"ip route replace default via {gateway} dev {iface} src {new_ip} onlink"
    try:
        subprocess.run(cmd, shell=True, check=True, capture_output=True)
        # 更新配置文件
        config['network']['current_src_ip'] = new_ip
        save_config('/opt/ip_failover/config.json', config)
        return new_ip
    except subprocess.CalledProcessError as e:
        print(f"切换 IP 失败: {e}")
        return None
