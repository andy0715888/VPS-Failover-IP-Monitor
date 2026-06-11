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

def delete_old_records(config, ip_address, domain=None):
    """如果 domain 为 None，则删除所有配置的域名中的记录"""
    cf = config['cloudflare']
    api_token = cf.get('api_token')
    zone_id = cf.get('zone_id')
    domains = cf.get('domains', [])
    if domain:
        domains = [domain]

    for d in domains:
        # 每个域名单独处理
        zid = zone_id if zone_id else get_zone_id(api_token, d)
        if not zid:
            print(f"无法获取域名 {d} 的 Zone ID")
            continue
        headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
        url = f"https://api.cloudflare.com/client/v4/zones/{zid}/dns_records?type=A&name={d}"
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            print(f"获取域名 {d} DNS 记录失败")
            continue
        records = resp.json().get('result', [])
        for record in records:
            if record['content'] == ip_address:
                del_url = f"https://api.cloudflare.com/client/v4/zones/{zid}/dns_records/{record['id']}"
                del_resp = requests.delete(del_url, headers=headers)
                if del_resp.status_code != 200:
                    print(f"删除记录 {record['id']} 失败")

def add_new_record(config, new_ip, domain=None):
    cf = config['cloudflare']
    api_token = cf.get('api_token')
    zone_id = cf.get('zone_id')
    domains = cf.get('domains', [])
    ttl = cf.get('record_ttl', 120)

    if domain:
        domains = [domain]

    for d in domains:
        zid = zone_id if zone_id else get_zone_id(api_token, d)
        if not zid:
            print(f"无法获取域名 {d} 的 Zone ID，跳过")
            continue
        headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
        # 检查是否已存在相同IP的记录
        url = f"https://api.cloudflare.com/client/v4/zones/{zid}/dns_records?type=A&name={d}"
        resp = requests.get(url, headers=headers)
        exists = False
        if resp.status_code == 200:
            records = resp.json().get('result', [])
            for record in records:
                if record['content'] == new_ip:
                    exists = True
                    print(f"记录 {d} -> {new_ip} 已存在，跳过添加")
                    break
        if not exists:
            data = {
                "type": "A",
                "name": d,
                "content": new_ip,
                "ttl": ttl,
                "proxied": False
            }
            url = f"https://api.cloudflare.com/client/v4/zones/{zid}/dns_records"
            resp = requests.post(url, headers=headers, json=data)
            if resp.status_code != 200:
                print(f"添加 DNS 记录失败 for {d}: {resp.text}")
