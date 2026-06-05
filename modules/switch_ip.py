import subprocess
from modules.config import load_config, save_config

def switch_outgoing_ip(config):
    iface = config['network']['interface']
    gateway = config['network']['gateway']
    current = config['network']['current_src_ip']
    available = config['network']['available_ips']

    if not available:
        return None

    try:
        idx = available.index(current)
        new_ip = available[(idx + 1) % len(available)]
    except ValueError:
        new_ip = available[0]

    if new_ip == current:
        return None

    cmd = f"ip route replace default via {gateway} dev {iface} src {new_ip} onlink"
    try:
        subprocess.run(cmd, shell=True, check=True, capture_output=True)
        config['network']['current_src_ip'] = new_ip
        save_config('/opt/ip_failover/config.json', config)
        return new_ip
    except subprocess.CalledProcessError as e:
        print(f"切换 IP 失败: {e}")
        return None
