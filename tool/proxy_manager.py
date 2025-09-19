import os
import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

def parse_proxy_line(line: str, proxy_type="http"):
    line = line.strip()
    if not line:
        return None

    if re.match(r"^(socks5|socks4|http|https)://", line):
        return line

    parts = line.split(":")
    if len(parts) == 4:
        ip, port, user, pwd = parts
        return f"{proxy_type}://{user}:{pwd}@{ip}:{port}"
    elif len(parts) == 2:
        ip, port = parts
        return f"{proxy_type}://{ip}:{port}"
    else:
        return None

def load_proxies(file_path="proxies.txt", proxy_type="http"):
    if not os.path.exists(file_path):
        return []

    proxies = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            parsed = parse_proxy_line(line, proxy_type)
            if parsed:
                proxies.append((parsed, line.strip()))  # (parsed_url, raw_line)
    return proxies

def is_proxy_live(proxy_url: str, timeout=5):
    try:
        proxies = {
            "http": proxy_url,
            "https": proxy_url
        }
        r = requests.get("https://ipinfo.io/ip", proxies=proxies, timeout=timeout)
        return r.status_code == 200
    except:
        return False

def check_and_filter_proxies(input_file="proxies.txt", proxy_type="http", max_workers=5, output_to_file=True):
    proxies = load_proxies(input_file, proxy_type)
    if not proxies:
        print("⚠️ Không tìm thấy proxy hợp lệ trong file.")
        return [], []

    live_proxies = []
    dead_proxies = []
    lock = Lock()  # Dùng lock để đảm bảo an toàn khi nhiều thread ghi vào danh sách

    def check_single(proxy_url, raw_line):
        result = is_proxy_live(proxy_url)
        with lock:
            if result:
                live_proxies.append(raw_line)
            else:
                dead_proxies.append(raw_line)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for proxy_url, raw_line in proxies:
            futures.append(executor.submit(check_single, proxy_url, raw_line))

        for _ in as_completed(futures):
            pass  # không cần xử lý thêm, đã được xử lý trong check_single()

    if output_to_file:
        with open("proxies_live.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(live_proxies))
        with open("proxies_dead.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(dead_proxies))

    print(f"✅ Đã kiểm tra xong. Live: {len(live_proxies)} | Dead: {len(dead_proxies)}")
    return live_proxies, dead_proxies

