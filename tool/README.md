# Voice Tool (PyQt5 Application)

Ứng dụng desktop PyQt5 để tạo voice từ text sử dụng Voice API server.

## Tính năng

- 🖥️ Giao diện desktop thân thiện
- 📝 Nhập text từ file Excel hoặc thủ công
- 🎤 Tạo voice với nhiều giọng khác nhau
- 📁 Quản lý file output
- 🔄 Kiểm tra proxy
- 🔐 Xác thực API key
- 📊 Theo dõi tiến trình

## Cài đặt

1. Cài đặt dependencies:
```bash
pip install -r requirements.txt
```

2. Đảm bảo Voice API server đang chạy tại: http://localhost:5000

3. Chạy ứng dụng:
```bash
python main.py
```

## Cấu trúc thư mục

```
tool/
├── main.py              # Ứng dụng PyQt5 chính
├── auth_guard.py        # Xác thực và bảo mật
├── proxy_manager.py     # Quản lý proxy
├── version_checker.py   # Kiểm tra phiên bản
├── updater.py          # Cập nhật ứng dụng
├── requirements.txt    # Python dependencies
├── config.json         # Cấu hình ứng dụng
├── proxies.txt         # Danh sách proxy
├── text_voice.xlsx     # File Excel mẫu
└── icon.ico           # Icon ứng dụng
```

## Sử dụng

### 1. Đăng nhập API Key
- Nhập API key đã tạo từ admin panel
- Hệ thống sẽ xác thực key

### 2. Nhập Text
- **Từ Excel**: Chọn file Excel với cột text
- **Thủ công**: Nhập text trực tiếp

### 3. Cấu hình Voice
- Chọn giọng nói
- Đặt tốc độ phát
- Chọn thư mục lưu

### 4. Tạo Voice
- Nhấn "Start" để bắt đầu
- Theo dõi tiến trình
- Kiểm tra kết quả

## Cấu hình

### File config.json
```json
{
  "api_url": "http://localhost:5000",
  "default_voice": "en-US-Neural2-A",
  "default_speed": 1.0,
  "output_folder": "./outputs"
}
```

### File proxies.txt
```
http://proxy1:port
http://proxy2:port
socks5://proxy3:port
```

## Troubleshooting

### Lỗi kết nối API
- Kiểm tra Voice API server có đang chạy
- Kiểm tra URL trong config.json
- Kiểm tra firewall/antivirus

### Lỗi API Key
- Kiểm tra key có hợp lệ trong admin panel
- Kiểm tra giới hạn sử dụng
- Thử tạo key mới

### Lỗi Proxy
- Kiểm tra file proxies.txt
- Sử dụng chức năng "Check Proxy" để test
- Thử không dùng proxy

### Lỗi File Excel
- Đảm bảo file có cột text
- Kiểm tra định dạng file (.xlsx)
- Thử với file mẫu text_voice.xlsx

## API Integration

Ứng dụng này sử dụng Voice API server với các endpoint:

- `POST /api/voice/create` - Tạo voice
- `GET /api/voice/download/<filename>` - Tải file

### Request Format
```
POST /api/voice/create
Content-Type: application/x-www-form-urlencoded

key=API_KEY
text=TEXT_TO_CONVERT
voice_code=VOICE_NAME
```

### Response Format
```json
{
  "success": true,
  "file_url": "/api/voice/download/filename.mp3",
  "duration": 2.5,
  "text_length": 13,
  "remaining_daily": 99,
  "remaining_monthly": 2999
}
```

## Development

### Thêm Voice mới
1. Cập nhật danh sách voice trong `main.py`
2. Thêm option vào ComboBox
3. Test với API server

### Thêm tính năng
1. Tạo UI component mới
2. Implement logic trong class tương ứng
3. Kết nối với API endpoint

## License

MIT License