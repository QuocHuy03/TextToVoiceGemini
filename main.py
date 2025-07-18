import sys
import os
import requests
import pandas as pd
import json
from PyQt5.QtGui import QColor, QBrush
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox,
    QFileDialog, QTableWidget, QHeaderView, QTableWidgetItem, QGroupBox, QMessageBox, QDialog
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QUrl
from PyQt5.QtGui import QDesktopServices 
from auth_guard import KeyLoginDialog, get_device_id
from version_checker import check_for_update, CURRENT_VERSION


API_URL = "http://192.168.0.193:5000"

def centered_item(text):
    item = QTableWidgetItem(text)
    item.setTextAlignment(Qt.AlignCenter)
    return item

class ImageGenerateThread(QThread):
    result_ready = pyqtSignal(int, bool, str, str)

    def __init__(self, row, prompt, save_folder, file_name, user_key,
                 ratio, style, theme, mood, lighting, detail_level):
        super().__init__()
        self.row = row
        self.prompt = prompt
        self.save_folder = save_folder
        self.file_name = file_name
        self.user_key = user_key
        self.ratio = ratio
        self.style = style
        self.theme = theme
        self.mood = mood
        self.lighting = lighting
        self.detail_level = detail_level

    def run(self):
        try:
            device_id, _, _ = get_device_id()
            payload = {
                "key": self.user_key,
                "text": self.prompt,
                "ratio": self.ratio,
                "style": self.style,
                "theme": self.theme,
                "mood": self.mood,
                "lighting": self.lighting,
                "detail_level": self.detail_level,
                "device_id": device_id
            }
            resp = requests.post(f"{API_URL}/api/image/create", data=payload, timeout=60)
            res = resp.json()
            if not resp.ok or not res.get("success"):
                msg = res.get("message", f"HTTP {resp.status_code}")
                self.result_ready.emit(self.row, False, "", msg)
                return

            file_url = res.get("file_url", "")
            if not file_url.endswith((".png", ".jpg", ".jpeg")):
                self.result_ready.emit(self.row, False, "", "Invalid file_url")
                return

            r = requests.get(file_url, timeout=30)
            if r.status_code != 200:
                self.result_ready.emit(self.row, False, "", f"Download failed: {r.status_code}")
                return

            os.makedirs(self.save_folder, exist_ok=True)
            save_path = os.path.join(self.save_folder, self.file_name)
            with open(save_path, 'wb') as f:
                f.write(r.content)

            self.result_ready.emit(self.row, True, save_path, "")
        except Exception as e:
            self.result_ready.emit(self.row, False, "", str(e))


class ImageToolUI(QWidget):
    CONFIG_PATH = "config.json"

    def __init__(self):
        super().__init__()
        self.setGeometry(100, 100, 900, 600)
        self.threads = []
        self.convert_queue = []
        self.max_concurrent_threads = 2
        self.folder = ""
        self.file_loaded = False
        self.remaining = None  # Số lượt còn lại (int hoặc None nếu chưa biết)

        self.init_ui()
        self.load_config()
        self.update_start_button_state()  # Cập nhật trạng thái nút khi khởi tạo


    def update_start_button_state(self):
        # Nếu remaining == 0 thì disable nút Start, ngược lại enable
        if self.remaining == 0:
            self.start_btn.setEnabled(False)
        else:
            # Enable khi chưa load file hoặc có lượt còn
            self.start_btn.setEnabled(True if self.file_loaded else False)


    def init_ui(self):
        layout = QVBoxLayout()

        # Control panel
        ctrl_grp = QGroupBox("Control Panel")
        ctrl_layout = QHBoxLayout()

        self.start_btn = QPushButton("Start Rendering")
        self.start_btn.clicked.connect(self.convert_all)
        self.start_btn.setEnabled(False)  # Ban đầu disable vì chưa load file
        ctrl_layout.addWidget(self.start_btn)

        self.save_cfg_btn = QPushButton("Save Config")
        self.save_cfg_btn.clicked.connect(self.save_config)
        ctrl_layout.addWidget(self.save_cfg_btn)

        ctrl_grp.setLayout(ctrl_layout)
        layout.addWidget(ctrl_grp)

        # Prompt settings
        settings_grp = QGroupBox("Image Settings")
        st = QHBoxLayout()
        self.style_combo = QComboBox(); self.style_combo.addItems(["photorealistic", "anime", "digital painting"])
        self.theme_combo = QComboBox(); self.theme_combo.addItems(["fantasy", "sci‑fi", "nature", "urban"])
        self.ratio_combo = QComboBox(); self.ratio_combo.addItems(["1:1", "16:9", "9:16", "4:3"])
        self.mood_combo = QComboBox(); self.mood_combo.addItems(["happy", "dark", "peaceful"])
        self.lighting_combo = QComboBox(); self.lighting_combo.addItems(["natural", "studio", "moody"])
        self.detail_combo = QComboBox(); self.detail_combo.addItems(["low", "medium", "high"])

        for lbl, widget in [("Style:",self.style_combo),
                            ("Theme:",self.theme_combo),
                            ("Ratio:",self.ratio_combo),
                            ("Mood:",self.mood_combo),
                            ("Lighting:",self.lighting_combo),
                            ("Detail:",self.detail_combo)]:
            st.addWidget(QLabel(lbl)); st.addWidget(widget)
        settings_grp.setLayout(st)
        layout.addWidget(settings_grp)

        # File import
        file_layout = QHBoxLayout()
        self.import_file_btn = QPushButton("Import Excel (prompt)")
        self.import_file_btn.clicked.connect(self.import_file)
        file_layout.addWidget(self.import_file_btn)
        layout.addLayout(file_layout)

        # Table
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "Prompt", "Status", "Image Path", "Error"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        self.setLayout(layout)


    def load_config(self):
        default = {}
        if not os.path.exists(self.CONFIG_PATH):
            with open(self.CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(default, f, indent=4)
        try:
            with open(self.CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except:
            cfg = {}

        self.style_combo.setCurrentText(cfg.get("style", "photorealistic"))
        self.theme_combo.setCurrentText(cfg.get("theme", "fantasy"))
        self.ratio_combo.setCurrentText(cfg.get("ratio", "1:1"))
        self.mood_combo.setCurrentText(cfg.get("mood", "happy"))
        self.lighting_combo.setCurrentText(cfg.get("lighting", "natural"))
        self.detail_combo.setCurrentText(cfg.get("detail_level", "medium"))


    def save_config(self):
        cfg = {
            "style": self.style_combo.currentText(),
            "theme": self.theme_combo.currentText(),
            "ratio": self.ratio_combo.currentText(),
            "mood": self.mood_combo.currentText(),
            "lighting": self.lighting_combo.currentText(),
            "detail_level": self.detail_combo.currentText()
        }
        try:
            with open(self.CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4)
            QMessageBox.information(self, "Success", "Config saved successfully!")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save config:\n{str(e)}")


    def import_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose Excel", "", "Excel Files (*.xlsx)")
        if not path: return
        df = pd.read_excel(path)
        if "prompt" not in df.columns:
            QMessageBox.warning(self, "Format Error", "Excel must have a 'prompt' column.")
            return
        self.table.setRowCount(0)
        for _, row in df.iterrows():
            idv = row.iloc[0]
            try: idx = int(idv)
            except: continue
            p = str(row["prompt"]).strip()
            if not p: continue
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, centered_item(str(idx)))
            self.table.setItem(r, 1, centered_item(p))
            self.table.setItem(r, 2, centered_item("Pending"))
            self.table.setItem(r, 3, centered_item(""))
            self.table.setItem(r, 4, centered_item(""))

        self.file_loaded = True
        self.update_start_button_state()  # Cập nhật nút Start sau khi import file


    def convert_all(self):
        if not self.file_loaded:
            QMessageBox.warning(self, "No File", "Import Excel with prompts first.")
            return
        if self.remaining == 0:
            QMessageBox.warning(self, "No Remaining", "🚫 Đã dùng hết lượt (0/0). Không thể tiếp tục.")
            return

        self.folder = QFileDialog.getExistingDirectory(self, "Choose save folder")
        if not self.folder: return
        self.convert_queue.clear()
        self.threads.clear()
        self.start_btn.setEnabled(False)  # Disable khi bắt đầu render

        for row in range(self.table.rowCount()):
            prompt = self.table.item(row, 1).text()
            short = prompt[:30].replace(" ", "_")
            idx = self.table.item(row, 0).text()
            fname = f"{idx}_{short}.png"
            self.table.setItem(row, 2, centered_item("Processing"))
            job = dict(row=row, prompt=prompt, save_folder=self.folder,
                       file_name=fname, user_key=self.user_key,
                       ratio=self.ratio_combo.currentText(),
                       style=self.style_combo.currentText(),
                       theme=self.theme_combo.currentText(),
                       mood=self.mood_combo.currentText(),
                       lighting=self.lighting_combo.currentText(),
                       detail_level=self.detail_combo.currentText())
            self.convert_queue.append(job)
        self.try_start_next()


    def try_start_next(self):
        while len(self.threads) < self.max_concurrent_threads and self.convert_queue:
            job = self.convert_queue.pop(0)
            t = ImageGenerateThread(**job)
            t.result_ready.connect(self.on_result)
            t.finished.connect(lambda: self.cleanup(t))
            self.threads.append(t)
            t.start()


    def on_result(self, row, success, path, err):
        if success:
            item = centered_item("Done")
            item.setBackground(QBrush(QColor(144, 238, 144)))  # LightGreen
            self.table.setItem(row, 2, item)

            btn = QPushButton("🔍 Xem")
            btn.clicked.connect(lambda _, p=path: self.open_image_path(p))
            self.table.setCellWidget(row, 3, btn)

            self.table.setItem(row, 4, centered_item(""))

            # Giảm remaining mỗi lần thành công (nếu remaining tồn tại)
            if isinstance(self.remaining, int) and self.remaining > 0:
                self.remaining -= 1
                self.update_start_button_state()
                # Cập nhật title window nếu muốn
                self.setWindowTitle(f"CreativeRender Pro v{CURRENT_VERSION} - @huyit32 - KEY: {self.user_key} | Remaining: {self.remaining}")

        else:
            item = centered_item("Failed")
            item.setBackground(QBrush(QColor(255, 182, 193)))  # LightPink
            self.table.setItem(row, 2, item)
            self.table.setItem(row, 4, centered_item(err))


    def open_image_path(self, path):
        if path and os.path.exists(path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        else:
            QMessageBox.warning(self, "File Not Found", f"Không tìm thấy file:\n{path}")


    def cleanup(self, t):
        if t in self.threads:
            self.threads.remove(t)
        if not self.threads and not self.convert_queue:
            self.update_start_button_state()  # Enable lại khi hoàn tất nếu còn lượt
        self.try_start_next()


    def open_image(self, r, c):
        if c == 3:
            item = self.table.item(r, c)
            if item:
                p = item.data(Qt.UserRole)
                if p and os.path.exists(p):
                    QDesktopServices.openUrl(QUrl.fromLocalFile(p))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    if check_for_update(f"{API_URL}/api/version.json"):
        sys.exit(0)

    API_AUTH = f"{API_URL}/api/image/auth?sheet=images"
    login = KeyLoginDialog(API_AUTH)
    if login.exec_() == QDialog.Accepted and login.validated:
        key = login.key_info.get("key")
        expires_raw = login.key_info.get("expires", "")
        remaining = login.key_info.get("remaining", 0)
        ui = ImageToolUI()
        ui.user_key = key
        try:
            ui.remaining = int(remaining)
        except:
            ui.remaining = None
        expires = expires_raw if expires_raw else "Unknown"
        ui.setWindowTitle(f"CreativeRender Pro v{CURRENT_VERSION} - @huyit32 - KEY: {key} | Expires: {expires} | Remaining: {remaining}")
        ui.update_start_button_state()  # Cập nhật trạng thái nút Start khi load UI
        ui.show()
        sys.exit(app.exec_())
    else:
        sys.exit(0)

