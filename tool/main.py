import sys
import os
import requests
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox,
    QFileDialog, QTableWidget, QHeaderView, QTableWidgetItem, QGroupBox, QMessageBox,
    QDialog, QProgressBar, QSpinBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from mutagen.mp3 import MP3
from functools import partial
from proxy_manager import parse_proxy_line, check_and_filter_proxies
import pandas as pd
import json
from auth_guard import KeyLoginDialog, get_device_id
from version_checker import check_for_update, CURRENT_VERSION
import re
from pathlib import Path
from datetime import datetime

# Load API URL from config
try:
    with open('config.json', 'r') as f:
        config = json.load(f)
        API_URL = config.get('api_url', 'http://localhost:5000')
except:
    API_URL = "http://localhost:5000"

class ProxyCheckThread(QThread):
    result_ready = pyqtSignal(list)
    progress_updated = pyqtSignal(int)

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
    result_ready = pyqtSignal(int, bool, str, str, str, str, str, float)
    file_downloaded = pyqtSignal(int, str)
    progress_updated = pyqtSignal(int, int)

    def __init__(self, row, text, save_folder, file_name, user_key, speed, voice_name, proxies, stt):
        super().__init__()
        self.row = row
        self.text = text
        self.save_folder = save_folder
        self.file_name = file_name
        self.user_key = user_key
        self.speed = speed
        self.voice_name = voice_name
        self.proxies = proxies
        self.stt = stt
        self.duration = 0.0

    def clean_filename(self, text):
        """Clean filename for safe file creation"""
        text = re.sub(r'[\\/*?:"<>|]', "", text)
        return text.strip().replace(" ", "_")[:100] + ".mp3"

    def run(self):
        try:
            device_id, _, _ = get_device_id()
            payload = {
                "api_key": self.user_key,
                "text": self.text,
                "voice_name": self.voice_name
            }

            print(f"🔄 Gửi request tạo voice với key {self.user_key[:8]}... voice: {self.voice_name}")
            self.progress_updated.emit(self.row, 25)
            
            response = requests.post(f"{API_URL}/api/voice/create", json=payload, timeout=30)

            try:
                res = response.json()
            except Exception:
                res = {}

            if not response.ok or not res.get("success", False):
                error_msg = res.get("error") or res.get("message") or f"Lỗi HTTP: {response.status_code}"
                print(f"❌ Voice tạo thất bại: {error_msg}")
                self.result_ready.emit(self.row, False, "", "", "", "", error_msg, 0.0)
                return

            if res.get("download_url", "").endswith(".mp3"):
                file_url = res.get("download_url")
                # Convert relative URL to absolute URL
                if file_url.startswith('/'):
                    file_url = f"{API_URL}{file_url}"
                
                file_name = f"{self.stt}_{self.clean_filename(self.text)}"
                output_dir = self.save_folder
                os.makedirs(output_dir, exist_ok=True)
                save_path = os.path.join(output_dir, self.file_name)
                
                self.progress_updated.emit(self.row, 50)
                print(f"[🔧 DEBUG] Downloading from: {file_url}")
                print(f"[🔧 DEBUG] Saving file to: {save_path}")
                
                # Download with retry logic
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        print(f"[🔄 ATTEMPT] Download attempt {attempt + 1}/{max_retries}")
                        r = requests.get(file_url, timeout=60)  # Increased timeout to 60 seconds
                        
                        if r.status_code == 200:
                            break
                        else:
                            print(f"[❌ HTTP ERROR] Status: {r.status_code}")
                            if attempt == max_retries - 1:
                                raise Exception(f"HTTP {r.status_code}")
                    except requests.exceptions.Timeout:
                        print(f"[⏰ TIMEOUT] Attempt {attempt + 1} timed out")
                        if attempt == max_retries - 1:
                            raise Exception("Download timeout after 3 attempts")
                    except Exception as e:
                        print(f"[❌ ERROR] Attempt {attempt + 1} failed: {e}")
                        if attempt == max_retries - 1:
                            raise Exception(f"Download failed: {str(e)}")
                
                if r.status_code == 200:
                    if os.path.exists(save_path):
                        try:
                            os.remove(save_path)
                            print(f"[🧹 DELETE] Đã xóa file cũ: {save_path}")
                        except Exception as e:
                            print(f"[❌ ERROR] Không thể xóa file cũ: {e}")
                            self.result_ready.emit(self.row, False, "", "", "", "", f"Lỗi xóa file cũ: {str(e)}", 0.0)
                            return

                    with open(save_path, 'wb') as f:
                        f.write(r.content)

                    self.progress_updated.emit(self.row, 75)
                    print(f"[✅ SAVED] File saved successfully: {save_path}")
                    
                    duration_sec = res.get("duration", 0)
                    if duration_sec == 0:
                        try:
                            audio = MP3(save_path)
                            duration_sec = audio.info.length
                        except:
                            duration_sec = 0
                    
                    self.duration = duration_sec
                    timing_str = f"{int(duration_sec // 60):02}:{int(duration_sec % 60):02}"
                    
                    self.progress_updated.emit(self.row, 100)
                    self.result_ready.emit(self.row, True, timing_str, self.speed, "N/A", save_path, save_path, duration_sec)
                    self.file_downloaded.emit(self.row, file_url)
                    return
                else:
                    self.result_ready.emit(self.row, False, "", "", "", "", f"Tạo OK nhưng tải lỗi: HTTP {r.status_code}", 0.0)
                    return
            else:
                self.result_ready.emit(self.row, False, "", "", "", "", "Phản hồi không hợp lệ hoặc không phải file .mp3", 0.0)
                return

        except Exception as e:
            print(f"❌ Voice tạo thất bại: {e}")
            self.result_ready.emit(self.row, False, "", "", "", "", str(e), 0.0)

def centered_item(text):
    """Create centered table item"""
    item = QTableWidgetItem(text)
    item.setTextAlignment(Qt.AlignCenter)
    return item

class SRTExporter:
    """Class để xử lý xuất file SRT"""
    
    @staticmethod
    def format_time(seconds):
        """Convert seconds to SRT time format (HH:MM:SS,mmm)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"
    
    @staticmethod
    def create_srt_content(texts, durations, start_times=None):
        """Create SRT content from texts and durations"""
        if start_times is None:
            start_times = []
            current_time = 0.0
            for duration in durations:
                start_times.append(current_time)
                current_time += duration
        
        srt_content = ""
        for i, (text, duration, start_time) in enumerate(zip(texts, durations, start_times), 1):
            end_time = start_time + duration
            srt_content += f"{i}\n"
            srt_content += f"{SRTExporter.format_time(start_time)} --> {SRTExporter.format_time(end_time)}\n"
            srt_content += f"{text}\n\n"
        
        return srt_content
    
    @staticmethod
    def save_srt_file(content, file_path):
        """Save SRT content to file"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception as e:
            print(f"❌ Lỗi khi lưu file SRT: {e}")
            return False 


class VoiceToolUI(QWidget):
    CONFIG_PATH = "config.json"

    def __init__(self):
        super().__init__()
        self.setGeometry(100, 100, 1200, 800)
        font = QFont("Roboto", 10)
        self.setFont(font)

        # Initialize variables
        self.proxies = []
        self.voice_data = []
        self.selected_voice_code = None
        self.threads = []
        self.convert_queue = []
        self.pending_rows = []
        self.active_threads = 0
        self.max_concurrent_threads = 2
        self.folder = ""
        self.file_loaded = False
        self.texts = []
        self.durations = []
        self.start_times = []
        self.user_key = None

        # Media player
        self.player = QMediaPlayer()
        self.player.stateChanged.connect(self.handle_audio_state_changed)
        self.player.setVolume(50)
        
        # Initialize UI
        self.init_ui()
        self.load_config()
        
        # Auto-save timer
        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(self.save_config)
        self.auto_save_timer.start(30000)

    def init_ui(self):
        layout = QVBoxLayout()
        
        # Style chung cho GroupBox
        groupbox_style = """
            QGroupBox {
                font-family: Roboto;
                font-weight: bold;
                font-size: 14px;
                color: #333;
                border: 2px solid #ddd;
                border-radius: 10px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #fafafa;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px 0 8px;
                color: #2196F3;
                font-family: Roboto;
                font-weight: bold;
                font-size: 15px;
            }
        """

        # Control panel
        ctrl_grp = QGroupBox("Control Panel")
        ctrl_grp.setStyleSheet(groupbox_style)
        ctrl_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("🚀 Start Convert")
        self.start_btn.setStyleSheet("""
            QPushButton {
                font-family: Roboto;
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #ccc;
                color: #666;
            }
        """)
        self.start_btn.clicked.connect(self.convert_all)

        self.reload_config_btn = QPushButton("🔄 Reload Config")
        self.reload_config_btn.setStyleSheet("""
            QPushButton {
                font-family: Roboto;
                background-color: #9C27B0;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
        """)
        self.reload_config_btn.clicked.connect(self.load_config)

        self.export_srt_btn = QPushButton("📝 Export SRT")
        self.export_srt_btn.setStyleSheet("""
            QPushButton {
                font-family: Roboto;
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #ccc;
                color: #666;
            }
        """)
        self.export_srt_btn.clicked.connect(self.export_srt_all)
        self.export_srt_btn.setEnabled(False)

        ctrl_layout.addWidget(self.start_btn)
        ctrl_layout.addWidget(self.reload_config_btn)
        ctrl_layout.addWidget(self.export_srt_btn)
        ctrl_grp.setLayout(ctrl_layout)

        # Voice settings
        voice_settings_grp = QGroupBox("Setting Voices")
        voice_settings_grp.setStyleSheet(groupbox_style)
        voice_settings_layout = QVBoxLayout()
        
        text_input_layout = QHBoxLayout()
        
        # Voice combo
        self.voice_combo = QComboBox()
        self.voice_combo.currentIndexChanged.connect(self.on_voice_changed)
        self.voice_combo.setStyleSheet("""
            QComboBox {
                font-family: Roboto;
                background-color: #f0f0f0;
                border: 2px solid #ddd;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 14px;
                font-weight: bold;
                min-width: 200px;
            }
            QComboBox:hover {
                border-color: #4CAF50;
                background-color: #e8f5e8;
            }
        """)
        text_input_layout.addWidget(self.voice_combo)

        # Player controls layout
        player_layout = QHBoxLayout()
        
        # Listen button
        self.listen_btn = QPushButton("▶️ Listen")
        self.listen_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #ccc;
                color: #666;
            }
        """)
        self.listen_btn.clicked.connect(self.play_fixed_audio)
        player_layout.addWidget(self.listen_btn)
        
        # Stop button
        self.stop_btn = QPushButton("⏹️ Stop")
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
            QPushButton:disabled {
                background-color: #ccc;
                color: #666;
            }
        """)
        self.stop_btn.clicked.connect(self.stop_audio)
        self.stop_btn.setEnabled(False)
        player_layout.addWidget(self.stop_btn)
        
        # Volume control
        volume_label = QLabel("🔊 Volume:")
        volume_label.setStyleSheet("""
            QLabel {
                color: #333;
                font-weight: bold;
                font-size: 12px;
                padding: 8px 4px;
                min-width: 60px;
            }
        """)
        player_layout.addWidget(volume_label)
        
        self.volume_slider = QSpinBox()
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.volume_slider.setSuffix("%")
        self.volume_slider.valueChanged.connect(self.set_volume)
        self.volume_slider.setStyleSheet("""
            QSpinBox {
                background-color: #f0f0f0;
                border: 2px solid #ddd;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
                font-weight: bold;
                min-width: 70px;
            }
            QSpinBox:hover {
                border-color: #4CAF50;
                background-color: #e8f5e8;
            }
        """)
        player_layout.addWidget(self.volume_slider)
        
        # Audio progress info
        self.audio_info_label = QLabel("Ready to play")
        self.audio_info_label.setStyleSheet("""
            QLabel {
                color: #666;
                font-size: 11px;
                padding: 8px;
                min-width: 120px;
                background-color: #f8f9fa;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
        """)
        player_layout.addWidget(self.audio_info_label)
        
        text_input_layout.addLayout(player_layout)
        voice_settings_layout.addLayout(text_input_layout)
        voice_settings_grp.setLayout(voice_settings_layout)

        # File Import
        file_layout = QHBoxLayout()
        self.import_file_btn = QPushButton("📊 Import Excel")
        self.import_file_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)
        self.import_file_btn.clicked.connect(self.import_file)
        file_layout.addWidget(self.import_file_btn)

        # Thread control and progress bar
        progress_layout = QHBoxLayout()
        
        # Thread control
        thread_label = QLabel("Threads:")
        thread_label.setStyleSheet("""
            QLabel {
                color: #333;
                font-weight: bold;
                font-size: 14px;
                padding: 8px;
                min-width: 80px;
            }
        """)
        progress_layout.addWidget(thread_label)
        
        self.thread_spinbox = QSpinBox()
        self.thread_spinbox.setRange(1, 10)
        self.thread_spinbox.setValue(self.max_concurrent_threads)
        self.thread_spinbox.valueChanged.connect(self.on_thread_count_changed)
        self.thread_spinbox.setStyleSheet("""
            QSpinBox {
                background-color: #f0f0f0;
                border: 2px solid #ddd;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
                font-weight: bold;
                min-width: 60px;
            }
            QSpinBox:hover {
                border-color: #4CAF50;
                background-color: #e8f5e8;
            }
        """)
        progress_layout.addWidget(self.thread_spinbox)
        
        # Progress bar
        progress_label = QLabel("Overall Progress:")
        progress_label.setStyleSheet("""
            QLabel {
                color: #333;
                font-weight: bold;
                font-size: 14px;
                padding: 8px;
                min-width: 120px;
            }
        """)
        
        self.overall_progress = QProgressBar()
        self.overall_progress.setVisible(False)
        self.overall_progress.setStyleSheet("""
            QProgressBar {
                border: 2px solid #ddd;
                border-radius: 8px;
                text-align: center;
                font-weight: bold;
                font-size: 12px;
                color: #333;
                background-color: #f0f0f0;
                min-height: 25px;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4CAF50, stop:0.5 #8BC34A, stop:1 #CDDC39);
                border-radius: 6px;
                margin: 2px;
            }
        """)
        
        progress_layout.addWidget(progress_label)
        progress_layout.addWidget(self.overall_progress)
        
        # Table with 8 columns (added Player column)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "ID", "OUTPUT", "TIMING", "CONTENT", "STATUS", "SPEED", "PROXY", "PLAYER"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        
        # Set column widths
        self.table.setColumnWidth(0, 50)   # ID
        self.table.setColumnWidth(1, 200)  # Output
        self.table.setColumnWidth(2, 80)   # Timing
        self.table.setColumnWidth(3, 300)  # Content
        self.table.setColumnWidth(4, 100)  # Status
        self.table.setColumnWidth(5, 80)   # Speed
        self.table.setColumnWidth(6, 100)  # Proxy
        self.table.setColumnWidth(7, 120)  # Player
        
        # Style cho table
        self.table.setStyleSheet("""
            QTableWidget {
                font-family: Roboto;
                background-color: #ffffff;
                alternate-background-color: #f8f9fa;
                gridline-color: #dee2e6;
                border: 2px solid #ddd;
                border-radius: 8px;
                font-size: 12px;
            }
            QTableWidget::item {
                font-family: Roboto;
                padding: 4px;
                border-bottom: 1px solid #eee;
                text-align: center;
            }
            QTableWidget::item:selected {
                background-color: #e3f2fd;
                color: #1976d2;
            }
            QHeaderView::section {
                font-family: Roboto;
                background-color: #2196F3;
                color: white;
                padding: 8px 4px;
                border: none;
                font-weight: bold;
                font-size: 12px;
            }
            QHeaderView::section:hover {
                background-color: #1976D2;
            }
        """)
        
        # Enable alternating row colors
        self.table.setAlternatingRowColors(True)

        layout.addWidget(ctrl_grp)
        layout.addWidget(voice_settings_grp)
        layout.addLayout(file_layout)
        layout.addLayout(progress_layout)
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
            self.voice_combo.clear()

            for voice in self.voice_data:
                self.voice_combo.addItem(voice["name"], voice["code"])

            if self.voice_data:
                self.selected_voice_code = self.voice_data[0]["code"]

        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "Lỗi kết nối", f"Không thể kết nối tới API:\n{e}")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể tải danh sách giọng nói:\n{e}")

    def on_voice_changed(self):
        """When a voice is selected, store the selected voice code"""
        voice_name = self.voice_combo.currentText()
        voice_code = next(voice['code'] for voice in self.voice_data if voice['name'] == voice_name)
        self.selected_voice_code = voice_code

    def play_fixed_audio(self):
        voice_code = self.selected_voice_code
        voice_info = next((v for v in self.voice_data if v["code"] == voice_code), None)

        if not voice_info or not voice_info.get("sample_url"):
            QMessageBox.warning(self, "Voice Error", "❌ Không tìm thấy sample_url.")
            return

        sample_url = voice_info["sample_url"]
        self.play_audio(sample_url, is_url=True)

    def handle_audio_state_changed(self, state):
        """Handle audio player state changes"""
        if state == QMediaPlayer.StoppedState:
            self.listen_btn.setEnabled(True)
            self.listen_btn.setText("▶️ Listen")
            self.stop_btn.setEnabled(False)
            # Reset audio info
            if hasattr(self, 'audio_info_label'):
                self.audio_info_label.setText("Ready to play")
            # Reset all table player buttons when audio stops
            if hasattr(self, 'current_playing_button'):
                self.reset_all_player_buttons()
                self.current_playing_button = None
        elif state == QMediaPlayer.PlayingState:
            self.listen_btn.setEnabled(False)
            self.listen_btn.setText("⏸️ Playing...")
            self.stop_btn.setEnabled(True)
        elif state == QMediaPlayer.PausedState:
            self.listen_btn.setEnabled(True)
            self.listen_btn.setText("▶️ Listen")
            self.stop_btn.setEnabled(False)

    def play_audio(self, audio_path, is_url=False):
        """Play audio file with better error handling and status updates"""
        try:
            if is_url:
                url = QUrl(audio_path)
                print(f"🎧 Đang phát URL: {audio_path}")
            else:
                audio_path = str(Path(audio_path).resolve())
                if not os.path.exists(audio_path):
                    QMessageBox.critical(self, "Lỗi", f"Không tìm thấy file: {audio_path}")
                    return
                url = QUrl.fromLocalFile(audio_path)
                print(f"🎧 Đang phát file: {audio_path}")

            # Stop any currently playing audio
            if self.player.state() == QMediaPlayer.PlayingState:
                self.player.stop()
            
            self.player.setMedia(QMediaContent(url))
            self.player.play()
            
            # Update button states
            self.listen_btn.setEnabled(False)
            self.listen_btn.setText("⏸️ Playing...")
            self.stop_btn.setEnabled(True)
            
            # Update audio info
            if hasattr(self, 'audio_info_label'):
                filename = os.path.basename(audio_path) if not is_url else "Sample Audio"
                self.audio_info_label.setText(f"Playing: {filename[:20]}...")
            
        except Exception as e:
            QMessageBox.critical(self, "Lỗi phát audio", f"Không thể phát file audio:\n{str(e)}")
            print(f"❌ Lỗi phát audio: {e}")

    def stop_audio(self):
        """Stop currently playing audio"""
        if self.player.state() == QMediaPlayer.PlayingState:
            self.player.stop()
            print("⏹️ Đã dừng phát audio")
        
        # Reset button states
        self.listen_btn.setEnabled(True)
        self.listen_btn.setText("▶️ Listen")
        self.stop_btn.setEnabled(False)
        
        # Reset audio info
        if hasattr(self, 'audio_info_label'):
            self.audio_info_label.setText("Ready to play")
        
        # Reset all table player buttons
        if hasattr(self, 'current_playing_button'):
            self.reset_all_player_buttons()
            self.current_playing_button = None

    def set_volume(self, volume):
        """Set audio volume"""
        self.player.setVolume(volume)
        print(f"🔊 Volume set to: {volume}%")

    def on_thread_count_changed(self, value):
        """Handle thread count change"""
        self.max_concurrent_threads = value
        print(f"🔄 Thread count changed to: {value}")
        # Auto-save config when thread count changes
        self.save_config()

    def play_table_audio(self, button):
        """Play audio from table with pause/resume functionality"""
        file_path = button.property("file_path")
        if not file_path:
            return
            
        # Check if this is the currently playing audio
        if (self.player.state() == QMediaPlayer.PlayingState and 
            hasattr(self, 'current_playing_button') and 
            self.current_playing_button == button):
            # Pause current audio
            self.player.pause()
            button.setText("▶️ Resume")
            button.setStyleSheet("""
                QPushButton {
                    background-color: #FF9800;
                    color: white;
                    font-weight: bold;
                    padding: 6px 12px;
                    border: none;
                    border-radius: 6px;
                    font-size: 11px;
                    min-width: 80px;
                }
                QPushButton:hover {
                    background-color: #F57C00;
                }
            """)
        else:
            # Play new audio or resume
            if self.player.state() == QMediaPlayer.PlayingState:
                self.player.stop()
            
            # Update all buttons to show Play state
            self.reset_all_player_buttons()
            
            # Set current playing button
            self.current_playing_button = button
            
            # Play the audio
            self.play_audio(file_path)
            
            # Update button to show Pause state
            button.setText("⏸️ Pause")
            button.setStyleSheet("""
                QPushButton {
                    background-color: #FF9800;
                    color: white;
                    font-weight: bold;
                    padding: 6px 12px;
                    border: none;
                    border-radius: 6px;
                    font-size: 11px;
                    min-width: 80px;
                }
                QPushButton:hover {
                    background-color: #F57C00;
                }
            """)

    def reset_all_player_buttons(self):
        """Reset all player buttons to Play state"""
        for row in range(self.table.rowCount()):
            button = self.table.cellWidget(row, 7)
            if button and isinstance(button, QPushButton):
                button.setText("▶️ Play")
                button.setStyleSheet("""
                    QPushButton {
                        background-color: #4CAF50;
                        color: white;
                        font-weight: bold;
                        padding: 6px 12px;
                        border: none;
                        border-radius: 6px;
                        font-size: 11px;
                        min-width: 80px;
                    }
                    QPushButton:hover {
                        background-color: #45a049;
                    }
                    QPushButton:pressed {
                        background-color: #3d8b40;
                    }
                    QPushButton:disabled {
                        background-color: #ccc;
                        color: #666;
                    }
                """)

    def load_config(self):
        default_config = {
            "proxy_type": "http",
            "max_concurrent_threads": 2
        }

        if not os.path.exists(self.CONFIG_PATH):
            with open(self.CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=4)
            print("🆕 Tạo mới config.json với giá trị mặc định.")

        try:
            with open(self.CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
                self.max_concurrent_threads = config.get("max_concurrent_threads", default_config["max_concurrent_threads"])
                print("✅ Đã load cấu hình từ config.json")
        except Exception as e:
            print(f"❌ Lỗi khi đọc config: {e}")
        
        # Update thread spinbox if it exists
        if hasattr(self, 'thread_spinbox'):
            self.thread_spinbox.setValue(self.max_concurrent_threads)

    def save_config(self):
        config = {
            "max_concurrent_threads": self.max_concurrent_threads
        }

        try:
            with open(self.CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)
            print("💾 Đã lưu config.json")
        except Exception as e:
            print(f"❌ Lỗi khi lưu config: {e}")

    def export_srt_all(self):
        """Export SRT for all completed rows"""
        try:
            if not self.durations or not self.texts:
                QMessageBox.warning(self, "Lỗi", "Không có dữ liệu để xuất SRT.")
                return
            
            # Tạo nội dung SRT cho tất cả
            srt_content = SRTExporter.create_srt_content(self.texts, self.durations)
            
            # Lưu file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"voice_export_{timestamp}.srt"
            file_path, _ = QFileDialog.getSaveFileName(self, "Lưu file SRT", file_name, "SRT Files (*.srt)")
            
            if file_path:
                if SRTExporter.save_srt_file(srt_content, file_path):
                    QMessageBox.information(self, "Thành công", f"Đã xuất SRT thành công: {file_path}")
                else:
                    QMessageBox.critical(self, "Lỗi", "Không thể lưu file SRT.")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Lỗi khi xuất SRT: {str(e)}")

    def import_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Chọn Excel File", "", "Excel Files (*.xlsx)")
        if not file_path:
            return

        try:
            df = pd.read_excel(file_path)
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể đọc file Excel: {str(e)}")
            return

        if "text" not in df.columns:
            QMessageBox.warning(self, "Sai định dạng", "Excel cần có cột 'text'.")
            return

        self.texts = []
        self.durations = []
        self.start_times = []

        self.table.setRowCount(0)

        for i, row in df.iterrows():
            try:
                stt = int(row.iloc[0])
            except (ValueError, TypeError):
                stt = None

            text = str(row["text"]).strip()

            if stt is None or not text:
                continue

            self.texts.append(text)
            self.durations.append(0.0)
            self.start_times.append(0.0)

            short_text = (text[:50] + "..." if len(text) > 50 else text).replace(" ", "_").replace("\n", "")
            filename = f"{stt}_{short_text}.mp3"

            # Thêm vào bảng
            table_row = len(self.texts) - 1
            self.table.insertRow(table_row)
            self.table.setRowHeight(table_row, 45)
            self.table.setItem(table_row, 0, centered_item(str(stt)))
            self.table.setItem(table_row, 1, centered_item(filename))
            self.table.setItem(table_row, 2, centered_item("00:00"))
            
            item = centered_item(text[:50] + ("..." if len(text) > 50 else ""))
            item.setData(Qt.UserRole, text)
            self.table.setItem(table_row, 3, item)
            
            self.table.setItem(table_row, 4, centered_item("Pending"))
            self.table.setItem(table_row, 5, centered_item(""))
            self.table.setItem(table_row, 6, centered_item(""))
            
            # Add disabled Player button initially
            player_btn = QPushButton("▶️ Play")
            player_btn.setEnabled(False)
            player_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    font-weight: bold;
                    padding: 5px 16px;
                    border: none;
                    border-radius: 8px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
                QPushButton:disabled {
                    background-color: #cccccc;
                    color: #666666;
                }
            """)
            self.table.setCellWidget(table_row, 7, player_btn)

        self.file_loaded = True
        self.export_srt_btn.setEnabled(True)
        
        # QMessageBox.information(self, "Thành công", f"Đã import {len(self.texts)} dòng dữ liệu.\n\n💡 Bây giờ bạn có thể:\n- Nhấn '🚀 Start Convert' để convert audio\n- Sau khi convert xong, SRT sẽ được tự động xuất!")

    def convert_all(self):
        if not self.file_loaded:
            QMessageBox.warning(self, "Chưa Import File", "⚠️ Vui lòng import file Excel trước khi bắt đầu.")
            return

        if not self.selected_voice_code:
            QMessageBox.warning(self, "Thiếu Giọng Nói", "❌ Vui lòng chọn giọng nói.")
            return

        if not self.user_key:
            QMessageBox.warning(self, "Thiếu API Key", "❌ Vui lòng đăng nhập trước khi convert.")
            return

        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu")
        self.folder = folder
        if not folder:
            return

        self.start_converting()

    def start_converting(self):
        self.convert_queue.clear()
        self.threads = []
        self.overall_progress.setVisible(True)
        self.overall_progress.setMaximum(self.table.rowCount())
        self.overall_progress.setValue(0)

        for row in range(self.table.rowCount()):
            text = self.table.item(row, 3).data(Qt.UserRole)
            short_text = (text[:50] + "..." if len(text) > 50 else text).replace(" ", "_").replace("\n", "")
            stt = self.table.item(row, 0).text()
            filename = f"{stt}_{short_text}.mp3"

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
        """Try to start the next conversion thread if the active threads are less than the limit"""
        while len(self.threads) < self.max_concurrent_threads and self.convert_queue:
            job = self.convert_queue.pop(0)
            thread = VoiceConvertThread(**job)
            thread.result_ready.connect(self.handle_convert_result)
            thread.progress_updated.connect(self.handle_progress_update)
            thread.finished.connect(partial(self.cleanup_thread, thread))
            self.threads.append(thread)
            thread.start()

    def handle_progress_update(self, row, progress):
        """Handle progress update from conversion thread"""
        pass

    def handle_convert_result(self, row, success, timing, speed, proxy, unused_param1, real_file_path_or_error, duration):
        if success:
            self.table.setItem(row, 2, centered_item(timing))
            absolute_path = str(Path(real_file_path_or_error).resolve())
            self.table.item(row, 1).setText(os.path.basename(absolute_path))
            self.table.item(row, 1).setData(Qt.UserRole, absolute_path)
            
            # Cập nhật duration cho SRT
            if row < len(self.durations):
                self.durations[row] = duration
            
            print(f"[💾 SET] Set UserRole with absolute path: {absolute_path}")
            done_item = centered_item("DONE")
            done_item.setBackground(QColor("lightgreen"))
            self.table.setItem(row, 4, done_item)
            self.table.setItem(row, 5, centered_item(speed))
            self.table.setItem(row, 6, centered_item(proxy))
            
            # Create and add Player button for the completed row
            player_btn = QPushButton("▶️ Play")
            player_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    font-weight: bold;
                    padding: 6px 12px;
                    border: none;
                    border-radius: 6px;
                    font-size: 11px;
                    min-width: 80px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
                QPushButton:pressed {
                    background-color: #3d8b40;
                }
                QPushButton:disabled {
                    background-color: #ccc;
                    color: #666;
                }
            """)
            # Store the file path in the button for later use
            player_btn.setProperty("file_path", absolute_path)
            player_btn.clicked.connect(lambda checked, btn=player_btn: self.play_table_audio(btn))
            self.table.setCellWidget(row, 7, player_btn)
            
            # Update overall progress
            self.overall_progress.setValue(self.overall_progress.value() + 1)

        else:
            fail_item = centered_item(real_file_path_or_error)
            fail_item.setBackground(QColor("lightpink"))
            fail_item.setForeground(QColor("red"))
            self.table.setItem(row, 4, fail_item)

        self.cleanup_thread(self.sender())

    def cleanup_thread(self, thread):
        """Clean up the thread after it finishes"""
        if thread in self.threads:
            self.threads.remove(thread)
        self.try_start_next_convert()
        
        # Hide progress bar when all conversions are done
        if not self.threads and not self.convert_queue:
            self.overall_progress.setVisible(False)



if __name__ == "__main__":
    # ⚠️ Phải tạo QApplication trước mọi QWidget
    app = QApplication(sys.argv)

    # ✅ Kiểm tra update
    if check_for_update(f"{API_URL}/api/version.json"):
        sys.exit(0)  # Dừng nếu có update (ví dụ: đã mở link tải rồi)

    # ✅ Gọi API auth
    API_URL_AUTH = f"{API_URL}/api/voice/auth"
    login = KeyLoginDialog(API_URL_AUTH)

    # ✅ Nếu xác thực thành công
    if login.exec_() == QDialog.Accepted and login.validated:
        key_info = login.key_info
        user_key = key_info.get("key")
        # Format lại ngày hết hạn
        expires_raw = key_info.get("expires", "")
        remaining = key_info.get("remaining", "")

       
        # ✅ Load UI chính
        ui = VoiceToolUI()
        ui.user_key = user_key  # Gán key cho instance
        expires = expires_raw if expires_raw else "Unknown"

        ui.setWindowTitle(f"Voice Tool Pro v{CURRENT_VERSION} - @huyit32 - KEY: {key_info.get('key')} | Expires: {expires} | Remaining: {remaining}")
        ui.show()

        # ✅ Khởi động app
        sys.exit(app.exec_())

    else:
        # Nếu thất bại thì thoát
        sys.exit(0)