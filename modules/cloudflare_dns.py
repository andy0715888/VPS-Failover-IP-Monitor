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
    zone_id = cf.get('zone_id')
    domain = cf.get('domain')

    if not zone_id:
        zone_id = get_zone_id(api_token, domain)
        if not zone_id:
            raise Exception(f"无法获取域名 {domain} 的 Zone ID")

    headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records?type=A&name={domain}"
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        raise Exception("获取 DNS 记录失败")

    records = resp.json().get('result', [])
    for record in records:
        if record['content'] == ip_address:
            del_url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{record['id']}"
            del_resp = requests.delete(del_url, headers=headers)
            if del_resp.status_code != 200:
                raise Exception(f"删除记录 {record['id']} 失败")

def add_new_record(config, new_ip):
    cf = config['cloudflare']
    api_token = cf.get('api_token')
    zone_id = cf.get('zone_id')
    domain = cf.get('domain')
    ttl = cf.get('record_ttl', 120)

    if not zone_id:
        zone_id = get_zone_id(api_token, domain)
        if not zone_id:
            raise Exception(f"无法获取域名 {domain} 的 Zone ID")

    headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
    data = {
        "type": "A",
        "name": domain,
        "content": new_ip,
        "ttl": ttl,
        "proxied": False
    }
    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
    resp = requests.post(url, headers=headers, json=data)
    if resp.status_code != 200:
        raise Exception(f"添加 DNS 记录失败: {resp.text}")
