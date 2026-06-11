import requests

def get_zone_id(api_token, domain):
    url = f"https://api.cloudflare.com/client/v4/zones?name={domain}"
    headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        if data['result']:
            return data['result'][0]['id']
    return None

def delete_old_records(config, ip_address):
    cf = config['cloudflare']
    api_token = cf.get('api_token')
    domains = cf.get('domains', [])
    zone_ids = cf.get('zone_ids', {})
    
    headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
    
    for domain in domains:
        zone_id = zone_ids.get(domain)
        if not zone_id:
            zone_id = get_zone_id(api_token, domain)
            if not zone_id:
                raise Exception(f"无法获取域名 {domain} 的 Zone ID")
            # 缓存 zone_id 到配置（可选）
            zone_ids[domain] = zone_id
        
        url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records?type=A&name={domain}"
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            raise Exception(f"获取域名 {domain} 的 DNS 记录失败")
        
        records = resp.json().get('result', [])
        for record in records:
            if record['content'] == ip_address:
                del_url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{record['id']}"
                del_resp = requests.delete(del_url, headers=headers)
                if del_resp.status_code != 200:
                    raise Exception(f"删除域名 {domain} 的记录 {record['id']} 失败")
    # 保存更新后的 zone_ids 到配置文件
    config['cloudflare']['zone_ids'] = zone_ids
    from modules.config import save_config
    save_config('/opt/ip_failover/config.json', config)

def add_new_record(config, new_ip):
    cf = config['cloudflare']
    api_token = cf.get('api_token')
    domains = cf.get('domains', [])
    zone_ids = cf.get('zone_ids', {})
    ttl = cf.get('record_ttl', 120)
    proxied = False
    
    headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
    
    for domain in domains:
        zone_id = zone_ids.get(domain)
        if not zone_id:
            zone_id = get_zone_id(api_token, domain)
            if not zone_id:
                raise Exception(f"无法获取域名 {domain} 的 Zone ID")
            zone_ids[domain] = zone_id
        
        # 检查是否已存在相同 IP 的记录
        url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records?type=A&name={domain}"
        resp = requests.get(url, headers=headers)
        exists = False
        if resp.status_code == 200:
            records = resp.json().get('result', [])
            for record in records:
                if record['content'] == new_ip:
                    exists = True
                    break
        if exists:
            print(f"域名 {domain} 的记录 {new_ip} 已存在，跳过添加")
            continue
        
        data = {
            "type": "A",
            "name": domain,
            "content": new_ip,
            "ttl": ttl,
            "proxied": proxied
        }
        url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
        resp = requests.post(url, headers=headers, json=data)
        if resp.status_code != 200:
            raise Exception(f"添加域名 {domain} 的 DNS 记录失败: {resp.text}")
    # 保存 zone_ids
    config['cloudflare']['zone_ids'] = zone_ids
    from modules.config import save_config
    save_config('/opt/ip_failover/config.json', config)
