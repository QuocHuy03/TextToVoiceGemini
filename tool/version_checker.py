import requests
import subprocess
import sys
import os
from PyQt5.QtWidgets import QMessageBox
from packaging import version

CURRENT_VERSION = "1.0.0"  # 👉 Cập nhật version tại đây

def check_for_update(version_url):
    try:
        res = requests.get(version_url, timeout=5)
        if res.status_code != 200:
            return False

        data = res.json()
        latest_version = data.get("version", "").strip()
        changelog = data.get("changelog", "Không có mô tả cập nhật.")
        download_url = data.get("download_url", "")

        if version.parse(latest_version) > version.parse(CURRENT_VERSION):
            return show_update_prompt(latest_version, changelog, download_url)

        return False
    except Exception as e:
        print("[Update] Lỗi khi kiểm tra version:", e)
        return False

def show_update_prompt(latest_version, changelog, download_url):
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Information)
    msg.setWindowTitle(f"🔔 Cập nhật mới ({latest_version})")
    msg.setText(f"<b>Voice Tool Pro</b> đã có bản mới <b>{latest_version}</b>!")
    msg.setInformativeText("Bạn có muốn tải bản mới không?")
    msg.setDetailedText(changelog)
    msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    msg.setDefaultButton(QMessageBox.Yes)

    if msg.exec_() == QMessageBox.Yes:
        if download_url:
            launch_updater(download_url)
        return True
    return False

def launch_updater(download_url):
    updater_path = os.path.join(os.getcwd(), "updater.py")
    subprocess.Popen([sys.executable, updater_path, download_url])
