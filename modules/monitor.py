    def run(self):
        self.log("监控线程启动")
        while self.running:
            config = load_config(self.config_file)
            # 检查全局开关
            if not config.get('enabled', True):
                time.sleep(5)
                continue
            
            monitor_cfg = config['monitor']
            targets = monitor_cfg['targets']
            count = monitor_cfg['ping_count']
            timeout = monitor_cfg['timeout_sec']
            threshold = monitor_cfg['failure_threshold']
            
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

            time.sleep(monitor_cfg['interval_sec'])
