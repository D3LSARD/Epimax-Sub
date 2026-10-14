import asyncio
import aiohttp
from aiohttp_socks import ProxyConnector
import base64
import urllib.parse
import sys
import time
import os
import json
import subprocess
import random
import re
import html as html_lib

# Local v2rayN / PattN port used in Stage 1
LOCAL_V2RAY_PORT = 10808

# Automatically push updated sub.txt to GitHub if git is initialized
AUTO_GIT_PUSH = True

SUBSCRIPTION_URLS = [
    "https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/main/subscriptions/v2ray/all_sub.txt",
    "https://raw.githubusercontent.com/Epodonios/v2ray-configs/raw/main/All_Configs_Sub.txt",
    "https://raw.githubusercontent.com/itsyebekhe/PSG/main/subscriptions/xray/base64/reality",
    "https://raw.githubusercontent.com/itsyebekhe/PSG/main/subscriptions/xray/base64/xhttp",
    "https://raw.githubusercontent.com/barry-far/V2ray-config/main/All_Configs_Sub.txt",
    "https://raw.githubusercontent.com/youfoundamin/V2rayCollector/main/mixed_iran.txt",
    "https://raw.githubusercontent.com/mahsanet/MahsaFreeConfig/refs/heads/main/mci/sub_2.txt"
]

TELEGRAM_CHANNELS = [
    "v2rayngvpn", "ConfigsCity", "PrivateVPNs", "v2ray_configs_pool",
    "V2rayng_Fast", "FreakConfig", "IRN_VPN", "V2ray_Alpha"
]

FOFA_EMAIL = "mostafa.asadi1377@gmail.com"
FOFA_API_KEY = "c579849e3580e751b13a29400ae14878"

CUSTOM_BRAND = "Mostafa Asadi | @EpimaxVPN"
TARGET_LIVE_CONFIGS = 25
HISTORY_FILE = "alive_history.json"

CLEAN_IPS = [
    "104.18.2.161",
    "172.67.73.163",
    "104.16.132.229",
    "104.17.147.22",
    "162.159.135.42"
]

CF_HTTPS_PORTS = {443, 2053, 2083, 2087, 2096, 8443}

BLOCKED_PREFIXES = (
    "169.40.", "169.38.", "169.45.", "169.46.", "169.47.", "169.48.",
    "169.50.", "169.51.", "169.53.", "169.55.", "169.60.", "169.61.",
    "169.62.", "169.63.", "158.175.", "158.176.", "158.177."
)

def find_xray_binary():
    local_paths = [
        "xray_core/xray.exe",
        "xray.exe",
        "./xray_core/xray",
        r"C:\Users\Mostafa\Desktop\PattN-windows-64\bin\xray\xray.exe"
    ]
    for p in local_paths:
        if os.path.exists(p):
            return os.path.abspath(p)

    search_roots = [os.path.expanduser("~\\Desktop"), "C:\\", "D:\\"]
    for root_dir in search_roots:
        if not os.path.exists(root_dir):
            continue
        for root, dirs, files in os.walk(root_dir):
            if "xray.exe" in [f.lower() for f in files]:
                return os.path.join(root, "xray.exe")
            if root.count(os.sep) - root_dir.count(os.sep) > 3:
                del dirs[:]
    return None

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_history(history_dict):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history_dict, f, indent=2)
    except Exception:
        pass

def decode_base64(data):
    try:
        missing_padding = len(data) % 4
        if missing_padding:
            data += '=' * (4 - missing_padding)
        return base64.b64decode(data).decode('utf-8', errors='ignore')
    except Exception:
        return ""

def is_valid_candidate(line):
    line = line.strip()
    if not line.startswith('vless://'):
        return False
    lower = line.lower()
    if 'security=reality' in lower or 'pbk=' in lower:
        return True
    if 'security=tls' in lower and any(t in lower for t in ['type=ws', 'type=xhttp', 'type=grpc']):
        return True
    return False

async def check_local_proxy():
    proxy_url = f"socks5://127.0.0.1:{LOCAL_V2RAY_PORT}"
    try:
        connector = ProxyConnector.from_url(proxy_url)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get("http://cp.cloudflare.com/generate_204", timeout=3.0) as resp:
                if resp.status in (200, 204):
                    return proxy_url
    except Exception:
        pass
    return None

async def fetch_url_text(url, proxy_url, headers=None, timeout=18):
    if proxy_url:
        try:
            connector = ProxyConnector.from_url(proxy_url)
            async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
                async with session.get(url, timeout=timeout) as response:
                    if response.status == 200:
                        return await response.text()
        except Exception:
            pass
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=timeout) as response:
                if response.status == 200:
                    return await response.text()
    except Exception:
        pass
    return None

async def fetch_fofa(proxy_url):
    if not FOFA_EMAIL or not FOFA_API_KEY:
        return []
    query = 'body="vless://" && country!="IR" && country!="CN"'
    qbase64 = base64.b64encode(query.encode('utf-8')).decode('utf-8')
    url = f"https://fofa.info/api/v1/search/all?email={FOFA_EMAIL}&key={FOFA_API_KEY}&qbase64={qbase64}&size=100&fields=body"
    extracted = []
    text = await fetch_url_text(url, proxy_url, timeout=20)
    if text:
        try:
            data = json.loads(text)
            for item in data.get("results", []):
                links = re.findall(r'vless://[a-zA-Z0-9@:%._\-\+~#?&//=]+', item[0])
                extracted.extend([l for l in links if is_valid_candidate(l)])
        except Exception:
            pass
    return extracted

async def fetch_github(url, proxy_url):
    text = await fetch_url_text(url, proxy_url, timeout=20)
    if text:
        decoded = decode_base64(text.strip())
        target = decoded if ('://' in decoded) else text
        return [l.strip() for l in target.splitlines() if is_valid_candidate(l)]
    return []

async def fetch_telegram(channel, proxy_url):
    url = f"https://t.me/s/{channel}"
    text = await fetch_url_text(url, proxy_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    if text:
        html_content = html_lib.unescape(text)
        links = re.findall(r'vless://[a-zA-Z0-9@:%._\-\+~#?&//=]+', html_content)
        return [l for l in links if is_valid_candidate(l)]
    return []

def get_subnet_key(address):
    parts = address.split('.')
    if len(parts) == 4 and all(p.isdigit() for p in parts):
        return f"{parts[0]}.{parts[1]}.{parts[2]}"
    return address.lower()

def optimize_and_deduplicate(raw_configs):
    unique = []
    seen_endpoints = set()
    seen_subnets = {}
    seen_hosts = set()

    for config in raw_configs:
        try:
            base, remark = config.split('#', 1) if '#' in config else (config, "")
            parsed = urllib.parse.urlparse(base)
            address, port = parsed.hostname, int(parsed.port)
            if not address or not port:
                continue
            if address.startswith(BLOCKED_PREFIXES):
                continue

            params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
            network = params.get("type", ["tcp"])[0].lower()
            security = params.get("security", ["none"])[0].lower()

            if security == "tls" and network in ("ws", "xhttp", "grpc") and port in CF_HTTPS_PORTS:
                original_host = params.get("host", params.get("sni", [address]))[0].strip()
                if original_host and not all(p.isdigit() for p in original_host.split('.')):
                    if original_host in seen_hosts:
                        continue
                    seen_hosts.add(original_host)
                    clean_ip = random.choice(CLEAN_IPS)
                    params["host"] = [original_host]
                    params["sni"] = [original_host]
                    new_query = urllib.parse.urlencode(params, doseq=True)
                    new_base = f"{parsed.scheme}://{parsed.username}@{clean_ip}:{port}?{new_query}"
                    unique.append(f"{new_base}#{remark}" if remark else new_base)
                    continue

            endpoint = f"{address}:{port}"
            if endpoint in seen_endpoints:
                continue

            subnet = get_subnet_key(address)
            if seen_subnets.get(subnet, 0) >= 2:
                continue

            seen_endpoints.add(endpoint)
            seen_subnets[subnet] = seen_subnets.get(subnet, 0) + 1
            unique.append(config)
        except Exception:
            continue
    return unique

async def tcp_ping(config, sem):
    try:
        parsed = urllib.parse.urlparse(config.split('#')[0])
        host, port = parsed.hostname, int(parsed.port)
        async with sem:
            start_time = time.time()
            reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=1.2)
            latency = (time.time() - start_time) * 1000
            writer.close()
            await writer.wait_closed()
            return (config, host, port, latency)
    except Exception:
        return None

def build_xray_json(config_url, local_port):
    try:
        parsed = urllib.parse.urlparse(config_url.split('#')[0])
        uuid_val, address, port = parsed.username, parsed.hostname, int(parsed.port)
        if not uuid_val or not address or not port:
            return None

        params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        def get_p(k, default=""):
            val = params.get(k, [""])[0].strip()
            return val if val else default

        network = get_p("type", "tcp").lower()
        if network in ("raw", "http"):
            network = "tcp"
        security = get_p("security", "none").lower()
        flow = get_p("flow", "")

        user_dict = {"id": uuid_val, "encryption": "none"}
        if flow and network == "tcp":
            user_dict["flow"] = flow

        outbound = {
            "protocol": "vless",
            "settings": {"vnext": [{"address": address, "port": port, "users": [user_dict]}]},
            "streamSettings": {"network": network, "security": security}
        }

        host_val = get_p("host", get_p("sni", address))
        path_val = urllib.parse.unquote(get_p("path", "/"))

        if network == "ws":
            outbound["streamSettings"]["wsSettings"] = {"path": path_val, "headers": {"Host": host_val}}
        elif network == "xhttp":
            outbound["streamSettings"]["xhttpSettings"] = {"path": path_val, "host": host_val}
        elif network == "grpc":
            outbound["streamSettings"]["grpcSettings"] = {"serviceName": get_p("serviceName", "")}

        if security == "tls":
            outbound["streamSettings"]["tlsSettings"] = {
                "serverName": get_p("sni", host_val),
                "allowInsecure": False,
                "fingerprint": get_p("fp", "chrome")
            }
        elif security == "reality":
            pbk = get_p("pbk", "")
            if not pbk:
                return None
            outbound["streamSettings"]["realitySettings"] = {
                "show": False,
                "serverName": get_p("sni", address),
                "fingerprint": get_p("fp", "chrome"),
                "publicKey": pbk,
                "shortId": get_p("sid", ""),
                "spiderX": urllib.parse.unquote(get_p("spx", "/"))
            }

        return {
            "log": {"loglevel": "none"},
            "inbounds": [{"port": local_port, "listen": "127.0.0.1", "protocol": "socks", "settings": {"auth": "noauth", "udp": True}}],
            "outbounds": [outbound]
        }
    except Exception:
        return None

async def wait_for_port(port, timeout=1.5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            reader, writer = await asyncio.wait_for(asyncio.open_connection('127.0.0.1', port), timeout=0.15)
            writer.close()
            await writer.wait_closed()
            return True
        except Exception:
            await asyncio.sleep(0.08)
    return False

def save_and_export(valid_real, quiet=False):
    if not valid_real:
        if not quiet:
            print("\n[Warning] No working configs were found.")
        return

    # Sort by: 1) Stability score descending, 2) Real latency ascending
    sorted_list = sorted(valid_real, key=lambda x: (-x[4], x[3]))
    final_configs = []
    for idx, (config, host, port, latency, score) in enumerate(sorted_list, start=1):
        badge = "STAR-VIP" if score > 1 else "VIP"
        new_name = urllib.parse.quote(f"{CUSTOM_BRAND} | {badge} #{idx} ({int(latency)}ms)")
        final_configs.append(f"{config.split('#')[0]}#{new_name}")

    raw_text = "\n".join(final_configs)
    with open("vip_links.txt", "w", encoding="utf-8") as f:
        f.write(raw_text)

    header = [
        "# profile-title: EpimaxVPN - VIP Auto",
        "# profile-update-interval: 2",
        "# subscription-userinfo: upload=0; download=0; total=107374182400; expire=1893456000",
        ""
    ]
    encoded = base64.b64encode("\n".join(header + final_configs).encode('utf-8')).decode('utf-8')
    with open("sub.txt", "w", encoding="utf-8") as f:
        f.write(encoded)

    if sys.platform == 'win32':
        subprocess.run(['clip'], input=raw_text.encode('utf-8'), check=False)
        if not quiet:
            print(f"\n[SUCCESS] Saved and copied {len(final_configs)} verified working configs to clipboard!")
            print("[ACTION] Open v2rayN / PattN now and press Ctrl + V to import them!")

def push_to_github(proxy_url=None):
    if not AUTO_GIT_PUSH or not os.path.exists(".git"):
        return
    print("\n[Stage 5] Auto-publishing sub.txt to GitHub for your users...")
    try:
        env = os.environ.copy()
        if proxy_url:
            env["HTTP_PROXY"] = proxy_url
            env["HTTPS_PROXY"] = proxy_url
        subprocess.run(["git", "add", "sub.txt"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "commit", "-m", "Auto-update verified Iranian ISP configs"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        res = subprocess.run(["git", "push"], env=env, capture_output=True, text=True, timeout=25)
        if res.returncode == 0:
            print("[SUCCESS] GitHub subscription (sub.txt) updated automatically!")
        else:
            print(f"[Info] Git push skipped: {res.stderr.strip()[:120]}")
    except Exception as e:
        print(f"[Info] Auto Git push skipped: {e}")

async def probe_once(local_port, url, timeout=3.0):
    """Create a fresh ProxyConnector per request to avoid aiohttp_socks socket reuse bug."""
    connector = ProxyConnector.from_url(f'socks5://127.0.0.1:{local_port}')
    start_t = time.time()
    async with aiohttp.ClientSession(connector=connector) as session:
        async with session.get(url, timeout=timeout) as resp:
            if resp.status in (200, 204):
                return (time.time() - start_t) * 1000
    return None

async def real_xray_test(item, index, total, sem, xray_exe, temp_dir, valid_real, stop_event, counter, history_dict):
    if stop_event.is_set():
        return

    config, host, port, tcp_latency = item

    async with sem:
        if stop_event.is_set():
            return

        local_port = 30000 + index
        conf_path = os.path.join(temp_dir, f"config_{local_port}.json")
        xray_json = build_xray_json(config, local_port)
        if not xray_json:
            counter[0] += 1
            return

        with open(conf_path, 'w', encoding='utf-8') as f:
            json.dump(xray_json, f)

        proc = None
        latency = None
        try:
            proc = await asyncio.create_subprocess_exec(
                xray_exe, 'run', '-c', conf_path,
                cwd=os.path.dirname(xray_exe),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )

            if await wait_for_port(local_port, timeout=1.5):
                # Request 1: Initial handshake verification
                lat1 = await probe_once(local_port, 'http://cp.cloudflare.com/generate_204', timeout=3.0)
                if lat1 is not None:
                    # Request 2: Separate fresh SOCKS5 connection to confirm server stability & non-DPI freeze
                    lat2 = await probe_once(local_port, 'http://www.gstatic.com/generate_204', timeout=2.5)
                    if lat2 is not None:
                        latency = min(lat1, lat2)
        except Exception:
            pass
        finally:
            if proc:
                try:
                    if proc.returncode is None:
                        proc.kill()
                        await asyncio.wait_for(proc.wait(), timeout=0.8)
                except Exception:
                    pass
            if os.path.exists(conf_path):
                try:
                    os.remove(conf_path)
                except Exception:
                    pass

        counter[0] += 1
        base_key = config.split('#')[0]
        if latency and not stop_event.is_set():
            prev_score = history_dict.get(base_key, {}).get("score", 0)
            new_score = prev_score + 1
            history_dict[base_key] = {"config": config, "score": new_score, "last_seen": int(time.time())}

            valid_real.append((config, host, port, latency, new_score))
            save_and_export(valid_real, quiet=True)
            tag = f"STAR(x{new_score})" if new_score > 1 else "VIP"
            print(f"  [+] LIVE #{len(valid_real)}/{TARGET_LIVE_CONFIGS} [{tag}] | {host}:{port} -> {int(latency)}ms  [Auto-Saved]")
            if len(valid_real) >= TARGET_LIVE_CONFIGS:
                stop_event.set()
        elif counter[0] % 20 == 0 and not stop_event.is_set():
            print(f"  [...] Progress: {counter[0]}/{total} checked | Verified Live: {len(valid_real)}")

async def main():
    print("=== Epimax V2Ray Enterprise Scanner v3.2 (Balanced Quota & Dual-Probe) ===")
    xray_exe = find_xray_binary()
    if not xray_exe:
        print("[ERROR] xray.exe not found! Please place xray.exe inside the xray_core folder.")
        return
    print(f"[Info] Using Xray Core at: {xray_exe}")

    history_dict = load_history()
    historical_configs = [v["config"] for v in history_dict.values() if "config" in v]
    if historical_configs:
        print(f"[Info] Loaded {len(historical_configs)} previously working configs from history.")

    proxy_url = await check_local_proxy()
    if proxy_url:
        print(f"[Stage 1] Local proxy ({proxy_url}) is ACTIVE! Fetching all sources...")
    else:
        print("[Stage 1] Local proxy not active. Fetching sources via direct fallback...")

    tasks = (
        [fetch_fofa(proxy_url)] +
        [fetch_github(u, proxy_url) for u in SUBSCRIPTION_URLS] +
        [fetch_telegram(c, proxy_url) for c in TELEGRAM_CHANNELS]
    )
    results = await asyncio.gather(*tasks)
    raw_configs = list(set(historical_configs + [cfg for res in results if res for cfg in res]))
    print(f"[Info] Downloaded {len(raw_configs)} total configs.")

    print("[Stage 2] Injecting Clean IPs & deduplicating subnets...")
    candidates = optimize_and_deduplicate(raw_configs)
    print(f"[Info] {len(candidates)} unique configs ready for direct ISP test.")

    print("[Stage 3] Direct TCP Ping on your ISP (No Proxy)...")
    tcp_sem = asyncio.Semaphore(250)
    valid_tcp = [r for r in await asyncio.gather(*[tcp_ping(c, tcp_sem) for c in candidates]) if r is not None]

    # Separate History, Reality, and CDN pools so Cloudflare IPs don't crowd out Reality servers
    hist_pool, reality_pool, cdn_pool = [], [], []
    for item in valid_tcp:
        cfg = item[0]
        if cfg.split('#')[0] in history_dict:
            hist_pool.append(item)
        elif 'security=reality' in cfg.lower() or 'pbk=' in cfg.lower():
            reality_pool.append(item)
        else:
            cdn_pool.append(item)

    reality_pool.sort(key=lambda x: x[3])
    cdn_pool.sort(key=lambda x: x[3])

    top_candidates = hist_pool + reality_pool[:160] + cdn_pool[:100]
    print(f"[Info] {len(valid_tcp)} open ports! Balanced queue: {len(hist_pool)} History + {len(reality_pool[:160])} Reality + {len(cdn_pool[:100])} CDN.")

    print(f"[Stage 4] Testing {len(top_candidates)} configs via Dual-Probe Xray Test...")
    temp_dir = os.path.abspath("temp_configs")
    os.makedirs(temp_dir, exist_ok=True)

    real_sem = asyncio.Semaphore(20)
    valid_real = []
    stop_event = asyncio.Event()
    counter = [0]

    test_tasks = [
        asyncio.create_task(
            real_xray_test(item, idx, len(top_candidates), real_sem, xray_exe, temp_dir, valid_real, stop_event, counter, history_dict)
        )
        for idx, item in enumerate(top_candidates)
    ]

    try:
        await asyncio.gather(*test_tasks)
    except (KeyboardInterrupt, asyncio.CancelledError):
        stop_event.set()
        for t in test_tasks:
            t.cancel()
    finally:
        save_history(history_dict)
        save_and_export(valid_real, quiet=False)
        push_to_github(proxy_url)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Info] Stopped by user. Verified configs are saved and copied to clipboard!")