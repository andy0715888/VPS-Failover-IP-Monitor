import json
import os
import threading

_config_lock = threading.Lock()
_status = {
    'fail_count': 0,
    'last_switch': None,
    'is_running': True,
    'last_success_time': None
}

def load_config(config_file):
    with _config_lock:
        with open(config_file, 'r') as f:
            return json.load(f)

def save_config(config_file, config):
    with _config_lock:
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=4)

def update_status(**kwargs):
    global _status
    with _config_lock:
        _status.update(kwargs)

def get_current_status():
    with _config_lock:
        return _status.copy()
