import threading
import time
import subprocess
import os
from datetime import datetime
from modules.config import load_config, save_config, update_status
from modules.switch_ip import switch_outgoing_ip
from modules.cloudflare_dns import delete_old_records, add_new_record

class MonitorThread(threading.Thread):
    def __init__(self, config_file, log_dir):
        super().__init__()
        self.config_file = config_file
        self.log_dir = log_dir
        self.running = True
        self.fail_count = 0
        self.daemon = True

    def stop(self):
        self.running = False

    def log(self, message):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_line = f"[{timestamp}] {message}\n"
        log_file = os.path.join(self.log_dir, 'failover.log')
        with open(log_file, 'a') as f:
            f.write(log_line)
        print(log_line.strip())

    def ping_target(self, target, count, timeout):
        """返回是否成功（至少收到一个回应）"""
        try:
            cmd = ['ping', '-c', str(count), '-W', str(timeout), target]
            result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return result.returncode == 0
        except:
            return False

    def run(self):
        self.log("监控线程启动")
        while self.running:
            config = load_config(self.config_file)
            monitor_cfg = config['monitor']
            targets = monitor_cfg['targets']
            count = monitor_cfg['ping_count']
            timeout = monitor_cfg['timeout_sec']
            threshold = monitor_cfg['failure_threshold']

            # 对每个目标进行 ping，全部成功才算成功
            success = True
            for target in targets:
                if not self.ping_target(target.strip(), count, timeout):
                    success = False
                    self.log(f"Ping 失败: {target}")
                    break

            if not success:
                self.fail_count += 1
                update_status(fail_count=self.fail_count)
                self.log(f"连续失败次数: {self.fail_count}")
                if self.fail_count >= threshold:
                    self.log(f"达到阈值 {threshold}，执行故障转移")
                    self.do_failover(config)
                    self.fail_count = 0
                    update_status(fail_count=0)
            else:
                if self.fail_count > 0:
                    self.log("Ping 恢复，重置失败计数")
                self.fail_count = 0
                update_status(fail_count=0, last_success_time=datetime.now().isoformat())

            # 等待下一次检查
            time.sleep(monitor_cfg['interval_sec'])

    def do_failover(self, config):
        try:
            # 记录旧 IP
            old_ip = config['network']['current_src_ip']
            self.log(f"开始故障转移，旧 IP: {old_ip}")

            # 切换出口 IP
            new_ip = switch_outgoing_ip(config)
            if not new_ip:
                self.log("切换 IP 失败，无可用其他 IP")
                return

            self.log(f"出口 IP 已切换为: {new_ip}")

            # 更新 Cloudflare DNS
            cf_cfg = config['cloudflare']
            if cf_cfg.get('api_token'):
                if cf_cfg.get('delete_old_records'):
                    delete_old_records(config, old_ip)
                    self.log(f"已删除 Cloudflare 中 IP {old_ip} 的 DNS 记录")
                if cf_cfg.get('add_new_record'):
                    add_new_record(config, new_ip)
                    self.log(f"已添加新 IP {new_ip} 到 Cloudflare 域名 {cf_cfg['domain']}")
            else:
                self.log("未配置 Cloudflare API Token，跳过 DNS 更新")

            update_status(last_switch=datetime.now().isoformat())
            self.log("故障转移完成")
        except Exception as e:
            self.log(f"故障转移异常: {str(e)}")
