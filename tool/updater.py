import sys
import os
import requests
import zipfile
import io
import time
import subprocess

def download_and_replace(url):
    try:
        print("[Updater] Tải file zip mới...")
        r = requests.get(url, timeout=15)
        z = zipfile.ZipFile(io.BytesIO(r.content))

        print("[Updater] Giải nén và ghi đè...")
        z.extractall(path=os.getcwd())  # Ghi đè file cũ
        z.close()

        print("[Updater] Cập nhật xong. Khởi động lại app...")
        run_app()
    except Exception as e:
        print("[Updater] Lỗi:", e)

def run_app():
    # ⚠️ Thay 'VoiceToolPro.exe' bằng file chạy chính của bạn
    app_path = os.path.join(os.getcwd(), "VoiceToolPro.exe")
    if os.path.exists(app_path):
        subprocess.Popen([app_path])
    else:
        print(f"❌ Không tìm thấy file: {app_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❌ Thiếu URL")
        sys.exit()

    time.sleep(2)  # Chờ app chính thoát
    url = sys.argv[1]
    download_and_replace(url)
