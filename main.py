import sys
import os
import requests
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox,
    QFileDialog, QTableWidget, QHeaderView,QTableWidgetItem, QGroupBox, QMessageBox,
    QDialog
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtCore import QUrl
from mutagen.mp3 import MP3
from functools import partial
from proxy_manager import parse_proxy_line, check_and_filter_proxies
import pandas as pd
import json
from auth_guard import KeyLoginDialog, get_device_id
from version_checker import check_for_update, CURRENT_VERSION
import re
from pathlib import Path


# API_URL="http://sofin.quochuy.io.vn"
API_URL="http://192.168.0.193:5000"


class ProxyCheckThread(QThread):
    result_ready = pyqtSignal(list)

    def __init__(self, file_path, proxy_type):
        super().__init__()
        self.file_path = file_path
        self.proxy_type = proxy_type

    def run(self):
        live_proxies, _ = check_and_filter_proxies(
            self.file_path,
            proxy_type=self.proxy_type,
            max_workers=20,
            output_to_file=True
        )
        self.result_ready.emit(live_proxies)


class VoiceConvertThread(QThread):
    result_ready = pyqtSignal(int, bool, str, str, str, str, str)
    file_downloaded = pyqtSignal(int, str)

    def __init__(self, row, text, save_folder, file_name, user_key, speed, voice_name, proxies, stt):
        super().__init__()
        self.row = row
        self.text = text
        self.save_folder = save_folder     # ✅ đúng biến mới
        self.file_name = file_name         # ✅ đúng biến mới
        self.user_key = user_key
        self.speed = speed
        self.voice_name = voice_name
        self.proxies = proxies
        self.stt = stt  # ✅ lưu số thứ tự từ Excel


    def clean_filename(self, text):
        text = re.sub(r'[\\/*?:"<>|]', "", text)
        return text.strip().replace(" ", "_")[:100] + ".mp3"

    def run(self):
        try:
            device_id, _, _ = get_device_id()
            payload = {
                "key": self.user_key,
                "text": self.text,
                "device_id": device_id,
                "voice_code": self.voice_name
            }

            print(f"Gửi request tạo voice với key {self.user_key[:8]}... voice: {self.voice_name}")
            response = requests.post(f"{API_URL}/api/voice/create", data=payload, timeout=30)

            try:
                res = response.json()
            except Exception:
                res = {}

            # Xử lý nếu thất bại hoặc response != 200
            if not response.ok or not res.get("success", False):
                error_msg = res.get("message", f"Lỗi HTTP: {response.status_code}")
                print(f"❌ Voice tạo thất bại: {error_msg}")
                self.result_ready.emit(self.row, False, "", "", "", "", error_msg)
                return

            # Nếu thành công và có file mp3
            if res.get("file_url", "").endswith(".mp3"):
                file_url = res.get("file_url")
                file_name = f"{self.stt}_{self.clean_filename(self.text)}"
                output_dir = self.save_folder
                os.makedirs(output_dir, exist_ok=True)
                save_path = os.path.join(output_dir, self.file_name)
                print(f"[🔧 DEBUG] Saving file to: {save_path}")
                r = requests.get(file_url, timeout=15)
                if r.status_code == 200:
                   
                    if os.path.exists(save_path):
                        try:
                            os.remove(save_path)
                            print(f"[🧹 DELETE] Đã xóa file cũ: {save_path}")
                        except Exception as e:
                            print(f"[❌ ERROR] Không thể xóa file cũ: {e}")
                            self.result_ready.emit(self.row, False, "", "", "", "", f"Lỗi xóa file cũ: {str(e)}")
                            return

                    # Tiếp tục ghi file mới
                    with open(save_path, 'wb') as f:
                        f.write(r.content)



                    print(f"[✅ SAVED] File saved successfully: {save_path}")
                    duration_sec = res.get("duration", 0)
                    timing_str = f"{int(duration_sec // 60):02}:{int(duration_sec % 60):02}"
                    self.result_ready.emit(self.row, True, timing_str, self.speed, "N/A", save_path, save_path)
                    self.file_downloaded.emit(self.row, file_url)
                    return
                else:
                    self.result_ready.emit(self.row, False, "", "", "", "", f"Tạo OK nhưng tải lỗi: HTTP {r.status_code}")
                    return
            else:
                self.result_ready.emit(self.row, False, "", "", "", "", "Phản hồi không hợp lệ hoặc không phải file .mp3")
                return

        except Exception as e:
            print(f"❌ Voice tạo thất bại: {e}")
            self.result_ready.emit(self.row, False, "", "", "", "", str(e))



def centered_item(text):
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignCenter)
        return item



class VoiceToolUI(QWidget):
    CONFIG_PATH = "config.json"


    def __init__(self):
        super().__init__()
        self.setGeometry(100, 100, 900, 750)


        self.proxies = []
        self.voice_data = []  # Mảng lưu trữ dữ liệu về giọng nói
        self.selected_voice_code = None  # Ensure we initialize selected_voice_code

        self.threads = []  # ✅ Fix lỗi AttributeError
        self.convert_queue = []  # ✅ Hàng đợi nếu đang giới hạn luồng

        self.pending_rows = []
        self.active_threads = 0
        self.max_concurrent_threads = 2
        self.folder = ""

        self.file_loaded = False

        self.player = QMediaPlayer()
        self.init_ui()
        self.load_config()



    def init_ui(self):
            layout = QVBoxLayout()

            # Control panel
            ctrl_grp = QGroupBox("Control Panel")
            ctrl_layout = QHBoxLayout()
            self.start_btn = QPushButton("Start")
            self.start_btn.clicked.connect(self.convert_all)

            self.reload_config_btn = QPushButton("Reload Config")
            self.reload_config_btn.clicked.connect(self.load_config)

            ctrl_layout.addWidget(self.start_btn)
            ctrl_layout.addWidget(self.reload_config_btn)
            ctrl_grp.setLayout(ctrl_layout)

            # Proxy settings
            proxy_grp = QGroupBox("Proxy Settings")
            proxy_layout = QHBoxLayout()
            self.proxy_type_combo = QComboBox()
            self.proxy_type_combo.addItems(["http", "socks5"])
            self.proxy_type_combo.currentIndexChanged.connect(self.save_config)

            self.proxy_load_btn = QPushButton("Load Proxy")
            self.proxy_load_btn.clicked.connect(self.load_proxy_file)
            proxy_layout.addWidget(QLabel("Type:"))
            proxy_layout.addWidget(self.proxy_type_combo)
            proxy_layout.addWidget(self.proxy_load_btn)
            proxy_grp.setLayout(proxy_layout)

            # File Import
            file_layout = QHBoxLayout()
            self.import_file_btn = QPushButton("Import Excel")
            self.import_file_btn.clicked.connect(self.import_file)
            file_layout.addWidget(self.import_file_btn)

            # Setting Voice
            voice_settings_grp = QGroupBox("Setting Voices")
            voice_settings_layout = QVBoxLayout()
            
            text_input_layout = QHBoxLayout()
            self.voice_combo = QComboBox()
            self.voice_combo.currentIndexChanged.connect(self.on_voice_changed)  # Add voice change handler
            text_input_layout.addWidget(self.voice_combo)

            self.listen_btn = QPushButton("▶️ Listen")
            self.listen_btn.clicked.connect(self.play_fixed_audio)
            text_input_layout.addWidget(self.listen_btn)
            
            voice_settings_layout.addLayout(text_input_layout)
            voice_settings_grp.setLayout(voice_settings_layout)

            # Table
            self.table = QTableWidget(0, 8)
            self.table.setHorizontalHeaderLabels(["ID", "Output", "Timing", "Content", "Status", "Speed", "Proxy", "🔊 Listen"])
            self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            self.table.verticalHeader().setVisible(False)

            layout.addWidget(ctrl_grp)
            layout.addWidget(voice_settings_grp)
            layout.addWidget(proxy_grp)
            layout.addLayout(file_layout)
            layout.addWidget(self.table)
            self.setLayout(layout)

            self.load_voices()



    def load_voices(self):
        try:
            response = requests.get(f"{API_URL}/api/voice/list", timeout=10)

            if response.status_code != 200:
                raise Exception(f"Server trả về mã lỗi HTTP {response.status_code}")

            data = response.json()
            if not data.get("success"):
                raise Exception(data.get("message", "Không thành công"))

            self.voice_data = data.get("voices", [])
            self.voice_combo.clear()  # Xóa combo cũ nếu có

            for voice in self.voice_data:
                self.voice_combo.addItem(voice["name"], voice["code"])

            if self.voice_data:
                self.selected_voice_code = self.voice_data[0]["code"]  # Chọn voice đầu tiên

        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "Lỗi kết nối", f"Không thể kết nối tới API:\n{e}")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể tải danh sách giọng nói:\n{e}")



    def on_voice_changed(self):
        """ When a voice is selected, store the selected voice code """
        voice_name = self.voice_combo.currentText()
        voice_code = next(voice['code'] for voice in self.voice_data if voice['name'] == voice_name)
        self.selected_voice_code = voice_code  # Store selected voice code
        


    def play_fixed_audio(self):

        voice_code = self.selected_voice_code
        voice_info = next((v for v in self.voice_data if v["code"] == voice_code), None)

        if not voice_info or not voice_info.get("sample_url"):
            QMessageBox.warning(self, "Voice Error", "❌ Không tìm thấy sample_url.")
            return

        sample_url = voice_info["sample_url"]

        # ✅ Phát trực tiếp từ sample_url
        self.play_audio(sample_url, is_url=True)



    def handle_audio_finished(self, state):
        if state == QMediaPlayer.StoppedState:
            # ✅ Bật lại nút Listen sau khi phát xong
            self.listen_btn.setEnabled(True)

            if hasattr(self, "is_listen_mode") and self.is_listen_mode:
                # Không cần xóa nếu phát từ URL (trực tiếp từ sample_url)
                self.is_listen_mode = False



    def handle_audio_result(self, success, result):
        self.listen_btn.setEnabled(True)
        
        if success:
            self.play_audio(result)
        else:
            QMessageBox.critical(self, "Lỗi", f"❌ Không thể tạo giọng nói: {result}")



    def play_audio(self, audio_path, is_url=False):
        if is_url:
            url = QUrl(audio_path)
        else:
            audio_path = str(Path(audio_path).resolve())
            if not os.path.exists(audio_path):
                QMessageBox.critical(self, "Lỗi", f"Không tìm thấy file: {audio_path}")
                return
            url = QUrl.fromLocalFile(audio_path)

        self.player.setMedia(QMediaContent(url))
        self.player.play()
        print(f"🎧 Đang phát file: {audio_path}")



    def load_config(self):
        default_config = {
            "proxy_type": "http"
        }

        if not os.path.exists(self.CONFIG_PATH):
            # ⚠️ Chưa có file → tự tạo với giá trị mặc định
            with open(self.CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=4)
            print("🆕 Tạo mới config.json với giá trị mặc định.")

        try:
            with open(self.CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
                self.proxy_type_combo.setCurrentText(config.get("proxy_type", default_config["proxy_type"]))
                print("✅ Đã load cấu hình từ config.json")
        except Exception as e:
            print(f"❌ Lỗi khi đọc config: {e}")



    def save_config(self):
        config = {
            "proxy_type": self.proxy_type_combo.currentText()
        }

        try:
            with open(self.CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)
            print("💾 Đã lưu config.json")
        except Exception as e:
            print(f"❌ Lỗi khi lưu config: {e}")



    def load_proxy_file(self):
            file_path, _ = QFileDialog.getOpenFileName(self, "Chọn file proxy", "", "Text Files (*.txt)")
            if file_path:
                proxy_type = self.proxy_type_combo.currentText().lower()
                self.proxy_load_btn.setEnabled(False)
                self.proxy_load_btn.setText("Đang kiểm tra...")
                self.thread = ProxyCheckThread(file_path, proxy_type)
                self.thread.result_ready.connect(self.proxy_check_done)
                self.thread.start()



    def proxy_check_done(self, live_proxies):
        proxy_type = self.proxy_type_combo.currentText().lower()
        self.proxies = [
            parse_proxy_line(p, proxy_type) for p in live_proxies if parse_proxy_line(p, proxy_type)
        ]
        print("✅ Proxy chuẩn sau parse:", self.proxies)
        QMessageBox.information(self, "Proxy Loaded", f"Số lượng proxy live: {len(self.proxies)}")
        self.proxy_load_btn.setEnabled(True)
        self.proxy_load_btn.setText("Load Proxy")



    def key_check_done(self, valid_keys, status_map, error_message):
        self.valid_keys = valid_keys
        self.key_status_map = status_map

        message = f"🔑 Tổng: {len(self.api_keys)} | ✅ Hợp lệ: {len(self.valid_keys)}"

        if error_message:
            message += f" | ❗ {error_message}"

        self.key_status_summary.setText(message)

        if self.valid_keys:
            color = "green" if len(self.valid_keys) == len(self.api_keys) else "orange"
        else:
            color = "red"

        self.key_status_summary.setStyleSheet(f"color: {color}; font-weight: bold;")
        self.load_keys_btn.setEnabled(True)
        self.load_keys_btn.setText("Reload Keys")
        self.keys_loaded = True



    def play_audio_from_row(self, row):
        item = self.table.item(row, 1)
        if not item:
            QMessageBox.warning(self, "Lỗi", "Không lấy được thông tin file.")
            return

        file_path = item.data(Qt.UserRole)  # Lấy đường dẫn đã lưu
        print(f"[🎧 PLAY] Attempt to play file from path: {file_path}")
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "File không tồn tại", f"Không tìm thấy: {file_path or 'Không rõ'}")
            return

        if not hasattr(self, "media_player"):
            self.media_player = QMediaPlayer()

        self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(file_path)))
        self.media_player.play()



    def import_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Chọn Excel File", "", "Excel Files (*.xlsx)")
        if not file_path:
            return

        df = pd.read_excel(file_path)

        if "text" not in df.columns:
            QMessageBox.warning(self, "Sai định dạng", "Excel cần có cột 'text'.")
            return

        self.texts = []

        self.table.setRowCount(0)

        for i, row in df.iterrows():
            # Lấy số thứ tự từ cột A (cột 0) và văn bản từ cột B (cột "text")
            try:
                stt = int(row.iloc[0])  # Chuyển đổi số thứ tự từ cột A thành số nguyên
            except (ValueError, TypeError):
                stt = None  # Nếu không phải số, gán None để bỏ qua

            text = str(row["text"]).strip()  # Văn bản từ cột B

            # Kiểm tra nếu cả cột A (stt) và cột B (text) đều có dữ liệu hợp lệ
            if stt is None or not text:
                continue  # Bỏ qua các hàng không có dữ liệu hợp lệ

            self.texts.append(text)

            # Tạo tên file dựa trên số thứ tự và văn bản
            short_text = (text[:50] + "..." if len(text) > 50 else text).replace(" ", "_").replace("\n", "")  # Thay thế khoảng trắng và xuống dòng
            filename = f"{stt}_{short_text}.mp3"  # Tên file theo số thứ tự (stt) và văn bản

            # Thêm tên file vào bảng
            self.table.insertRow(len(self.texts) - 1)
            self.table.setItem(len(self.texts) - 1, 0, centered_item(str(stt)))  # Số thứ tự lấy từ cột A
            self.table.setItem(len(self.texts) - 1, 1, centered_item(filename))
            self.table.setItem(len(self.texts) - 1, 2, centered_item("00:00"))
            item = centered_item(text[:50] + ("..." if len(text) > 50 else ""))
            item.setData(Qt.UserRole, text)  # Lưu text đầy đủ vào vùng ẩn
            self.table.setItem(len(self.texts) - 1, 3, item)
            self.table.setItem(len(self.texts) - 1, 4, centered_item("Pending"))
            self.table.setItem(len(self.texts) - 1, 5, centered_item(""))

            play_btn = QPushButton("▶️ Play")
            play_btn.setEnabled(False)
            play_btn.clicked.connect(partial(self.play_audio_from_row, len(self.texts) - 1))
            self.table.setCellWidget(len(self.texts) - 1, 7, play_btn)

        self.file_loaded = True



    def make_cleanup_callback(self, thread):
        def callback():
            self.cleanup_thread(thread)
        return callback



    def convert_all(self):
        if not self.file_loaded:
            QMessageBox.warning(self, "Chưa Import File", "⚠️ Vui lòng import file Excel trước khi bắt đầu.")
            return

        if not self.selected_voice_code:
            QMessageBox.warning(self, "Thiếu Giọng Nói", "❌ Vui lòng chọn giọng nói.")
            return

        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu")
        self.folder = folder
        if not folder:
            return

        self.start_converting()



    def start_converting(self):
        self.convert_queue.clear()
        self.threads = []

        for row in range(self.table.rowCount()):
            text = self.table.item(row, 3).data(Qt.UserRole)
            # Rút gọn tên file nếu văn bản quá dài
            short_text = (text[:50] + "..." if len(text) > 50 else text).replace(" ", "_").replace("\n", "")  # Thay thế khoảng trắng và xuống dòng
            stt = self.table.item(row, 0).text()  # Lấy số thứ tự (stt) từ cột A
            filename = f"{stt}_{short_text}.mp3"  # Tên file theo số thứ tự (stt) và văn bản

            # Tạo đường dẫn đầy đủ của file
            save_folder = self.folder
            file_name = filename

            self.table.setItem(row, 4, centered_item("Processing..."))

            job = {
                "row": row,
                "text": text,
                "save_folder": save_folder,
                "file_name": file_name,
                "user_key": self.user_key,
                "speed": "1.0",
                "voice_name": self.selected_voice_code,
                "proxies": self.proxies,
                "stt": self.table.item(row, 0).text() 
            }



            self.convert_queue.append(job)

        self.try_start_next_convert()



    def try_start_next_convert(self):
        """ Try to start the next conversion thread if the active threads are less than the limit """
        while len(self.threads) < self.max_concurrent_threads and self.convert_queue:
            job = self.convert_queue.pop(0)
            thread = VoiceConvertThread(**job)
            thread.result_ready.connect(self.handle_convert_result)
            thread.finished.connect(partial(self.cleanup_thread, thread))
            self.threads.append(thread)
            thread.start()



    def handle_convert_result(self, row, success, timing, speed, proxy, unused_param1, real_file_path_or_error):
        if success:
            self.table.setItem(row, 2, centered_item(timing))
            absolute_path = str(Path(real_file_path_or_error).resolve())
            self.table.item(row, 1).setText(os.path.basename(absolute_path))
            self.table.item(row, 1).setData(Qt.UserRole, absolute_path)
            print(f"[💾 SET] Set UserRole with absolute path: {absolute_path}")
            done_item = centered_item("DONE")
            done_item.setBackground(QColor("lightgreen"))
            self.table.setItem(row, 4, done_item)
            self.table.setItem(row, 5, centered_item(speed))
            self.table.setItem(row, 6, centered_item(proxy))
            self.table.cellWidget(row, 7).setEnabled(True)
        else:
            fail_item = centered_item(real_file_path_or_error)
            fail_item.setBackground(QColor("red"))
            fail_item.setForeground(QColor("white"))
            self.table.setItem(row, 4, fail_item)

        self.cleanup_thread(self.sender())



    def cleanup_thread(self, thread):
        """ Clean up the thread after it finishes """
        if thread in self.threads:
            self.threads.remove(thread)
        self.try_start_next_convert()



if __name__ == "__main__":

    # ⚠️ Phải tạo QApplication trước mọi QWidget
    app = QApplication(sys.argv)

    # ✅ Kiểm tra update
    if check_for_update(f"{API_URL}/api/version.json"):
        sys.exit(0)  # Dừng nếu có update (ví dụ: đã mở link tải rồi)

    # ✅ Gọi API auth
    API_URL_AUTH = f"{API_URL}/api/voice/auth?sheet=voices"
    login = KeyLoginDialog(API_URL_AUTH)

    # ✅ Nếu xác thực thành công
    if login.exec_() == QDialog.Accepted and login.validated:
        key_info = login.key_info
        VoiceToolUI.user_key = key_info.get("key")
        # Format lại ngày hết hạn
        expires_raw = key_info.get("expires", "")
        remaining = key_info.get("remaining", "")
        print(key_info)

       
        # ✅ Load UI chính
        ui = VoiceToolUI()
        expires = expires_raw if expires_raw else "Unknown"

        ui.setWindowTitle(f"Voice Tool Pro v{CURRENT_VERSION} - @huyit32 - KEY: {key_info.get('key')} | Expires: {expires} | Remaining: {remaining}")
        ui.show()

        # ✅ Khởi động app
        sys.exit(app.exec_())

    else:
        # Nếu thất bại thì thoát
        sys.exit(0)