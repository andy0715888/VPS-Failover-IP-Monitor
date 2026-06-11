#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import json
import threading
import time
import hashlib
from flask import Flask, render_template, request, jsonify, session, redirect, url_for

app = Flask(__name__)
app.secret_key = os.urandom(24)

CONFIG_FILE = '/opt/ip_failover/config.json'
LOG_DIR = '/opt/ip_failover/logs'

# 导入模块
from modules.config import load_config, save_config, get_current_status
from modules.monitor import MonitorThread
from modules.switch_ip import switch_outgoing_ip
from modules.cloudflare_dns import delete_old_records, add_new_record

# 全局监控线程对象
monitor_thread = None

def require_auth(func):
    """登录验证装饰器"""
    def wrapper(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        config = load_config(CONFIG_FILE)
        expected_hash = config.get('web', {}).get('password_hash', '')
        if expected_hash and hashlib.sha256(password.encode()).hexdigest() == expected_hash and username == config['web'].get('username', 'admin'):
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            if not expected_hash:
                config['web']['password_hash'] = hashlib.sha256(password.encode()).hexdigest()
                config['web']['username'] = username
                save_config(CONFIG_FILE, config)
                session['logged_in'] = True
                return redirect(url_for('index'))
            return render_template('login.html', error='用户名或密码错误')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/')
@require_auth
def index():
    config = load_config(CONFIG_FILE)
    status = get_current_status()
    return render_template('index.html', config=config, status=status)

@app.route('/settings', methods=['GET', 'POST'])
@require_auth
def settings():
    if request.method == 'POST':
        new_config = {
            "monitor": {
                "targets": request.form.get('targets').splitlines(),
                "interval_sec": int(request.form.get('interval_sec')),
                "ping_count": int(request.form.get('ping_count')),
                "timeout_sec": int(request.form.get('timeout_sec')),
                "failure_threshold": int(request.form.get('failure_threshold'))
            },
            "network": {
                "interface": request.form.get('interface'),
                "gateway": request.form.get('gateway'),
                "current_src_ip": request.form.get('current_src_ip'),
                "available_ips": request.form.get('available_ips').splitlines()
            },
            "cloudflare": {
                "api_token": request.form.get('api_token'),
                "zone_id": request.form.get('zone_id'),
                "domain": request.form.get('domain'),
                "delete_old_records": request.form.get('delete_old_records') == 'on',
                "add_new_record": request.form.get('add_new_record') == 'on',
                "record_ttl": int(request.form.get('record_ttl'))
            },
            "web": {
                "port": int(request.form.get('web_port')),
                "username": request.form.get('web_username'),
                "password_hash": load_config(CONFIG_FILE)['web'].get('password_hash', '')
            }
        }
        save_config(CONFIG_FILE, new_config)
        restart_monitor()
        return jsonify({"status": "success", "message": "配置已保存，监控已重启"})
    config = load_config(CONFIG_FILE)
    return render_template('settings.html', config=config)

@app.route('/logs')
@require_auth
def logs():
    log_file = os.path.join(LOG_DIR, 'failover.log')
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            content = f.read().splitlines()[-200:]
    else:
        content = []
    return render_template('logs.html', logs=content)

@app.route('/api/switch_now', methods=['POST'])
@require_auth
def api_switch_now():
    config = load_config(CONFIG_FILE)
    try:
        new_ip = switch_outgoing_ip(config)
        if new_ip and config['cloudflare'].get('api_token'):
            old_ip = config['network']['current_src_ip']
            if config['cloudflare'].get('delete_old_records'):
                delete_old_records(config, old_ip)
            if config['cloudflare'].get('add_new_record'):
                add_new_record(config, new_ip)
        return jsonify({"status": "success", "new_ip": new_ip})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

def restart_monitor():
    global monitor_thread
    if monitor_thread and monitor_thread.is_alive():
        monitor_thread.stop()
        monitor_thread.join(timeout=2)
    monitor_thread = MonitorThread(CONFIG_FILE, LOG_DIR)
    monitor_thread.start()
@app.route('/api/toggle', methods=['POST'])
@require_auth
def api_toggle():
    config = load_config(CONFIG_FILE)
    new_state = not config.get('enabled', True)
    config['enabled'] = new_state
    save_config(CONFIG_FILE, config)
    # 重启监控线程以立即生效
    restart_monitor()
    return jsonify({"status": "success", "enabled": new_state})
if __name__ == '__main__':
    config = load_config(CONFIG_FILE)
    port = config.get('web', {}).get('port', 5000)
    restart_monitor()
    app.run(host='0.0.0.0', port=port, debug=False)
