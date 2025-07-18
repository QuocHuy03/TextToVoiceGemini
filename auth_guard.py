import uuid
import hashlib
import platform
import subprocess
import requests
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QHBoxLayout, QSpacerItem, QSizePolicy
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from requests.exceptions import RequestException, ConnectionError, Timeout

SECRET_SALT = "huydev"


def get_device_id():
    mac = str(uuid.getnode())
    serial = "unknown"

    if platform.system() == "Windows":
        try:
            result = subprocess.check_output("wmic diskdrive get SerialNumber", shell=True)
            lines = result.decode().strip().split("\n")
            if len(lines) > 1:
                serial = lines[1].strip()
        except:
            pass

    raw = f"{mac}-{serial}-{SECRET_SALT}"
    device_id_hash = hashlib.sha256(raw.encode()).hexdigest()
    return device_id_hash, mac, serial


def check_key_online(key: str, api_url: str):
    device_id_hash, mac, serial = get_device_id()

    try:
        response = requests.post(api_url, data={
            "key": key,
            "device_id": device_id_hash
        }, timeout=10)

        # Nếu lỗi status HTTP (500, 404,...)
        try:
            res = response.json()
            message = res.get("message", f"❌ HTTP {response.status_code}")
        except Exception:
            message = f"❌ HTTP {response.status_code} (no JSON)"
            res = {}

        if response.status_code != 200:
            return False, message, {}
        
        
        res = response.json()

        if res.get("success"):
            info = {
                "key": key,
                "device_id": f"{mac} | {serial}",
                "expires": res.get("expires", ""),
                "remaining": res.get("remaining", "")
            }
            return True, res.get("message", "✅ Thành công"), info
        else:
            return False, res.get("message", "❌ KEY không hợp lệ"), {}

    except ConnectionError:
        return False, "📡 Không thể kết nối tới máy chủ. Kiểm tra kết nối mạng.", {}

    except Timeout:
        return False, "⏳ Máy chủ không phản hồi. Vui lòng thử lại sau.", {}

    except RequestException as e:
        return False, f"❌ Lỗi mạng: {str(e)}", {}

    except Exception as e:
        return False, f"⚠️ Lỗi không xác định: {str(e)}", {}


class KeyCheckThread(QThread):
    result_ready = pyqtSignal(bool, str, dict)

    def __init__(self, key, api_url):
        super().__init__()
        self.key = key
        self.api_url = api_url

    def run(self):
        success, message, info = check_key_online(self.key, self.api_url)
        self.result_ready.emit(success, message, info)


class KeyLoginDialog(QDialog):
    def __init__(self, api_url):
        super().__init__()
        self.setWindowTitle("🔐 Đăng nhập bằng KEY")
        self.api_url = api_url
        self.validated = False
        self.key_info = {}

        self.setFixedWidth(420)
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self.build_ui()

    def build_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("Vui lòng nhập KEY để sử dụng công cụ")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("Nhập KEY của bạn...")
        self.key_input.setMinimumHeight(32)
        self.key_input.setStyleSheet("font-size: 13px;")
        self.key_input.returnPressed.connect(self.validate_key)
        layout.addWidget(self.key_input)

        # Nút xác nhận
        btn_layout = QHBoxLayout()
        btn_layout.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self.submit_btn = QPushButton("🔑 Xác nhận")
        self.submit_btn.setMinimumHeight(30)
        self.submit_btn.clicked.connect(self.validate_key)
        btn_layout.addWidget(self.submit_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

        self.key_input.setFocus()

    def validate_key(self):
        key = self.key_input.text().strip()
        if not key:
            QMessageBox.warning(self, "Thiếu KEY", "Vui lòng nhập KEY để tiếp tục.")
            return

        self.submit_btn.setEnabled(False)
        self.submit_btn.setText("⏳ Đang kiểm tra...")

        self.thread = KeyCheckThread(key, self.api_url)
        self.thread.result_ready.connect(self.handle_result)
        self.thread.start()

    def handle_result(self, success, message, info):
        self.submit_btn.setEnabled(True)
        self.submit_btn.setText("🔑 Xác nhận")

        if success:
            QMessageBox.information(self, "Thành công", message)
            self.validated = True
            self.key_info = info
            self.accept()
        else:
            QMessageBox.critical(self, "Thất bại", message)
            self.key_input.setFocus()
