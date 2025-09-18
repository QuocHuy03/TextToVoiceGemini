# Voice API Backend

Hệ thống API server cho chuyển đổi text thành giọng nói sử dụng Google Gemini TTS.

## Tính năng

- 🎤 Chuyển đổi text thành giọng nói chất lượng cao
- 🔐 Hệ thống xác thực API key với giới hạn sử dụng
- 📊 Theo dõi usage theo ngày/tháng
- 👨‍💼 Admin panel quản lý users và API keys
- 🗄️ Database SQLite lưu trữ dữ liệu
- 🔄 Proxy rotation cho API calls

## Cài đặt

1. Cài đặt dependencies:
```bash
pip install -r requirements.txt
```

2. Cài đặt FFmpeg (cần thiết cho xử lý audio):
- Windows: Tải từ https://ffmpeg.org/download.html
- Linux: `sudo apt install ffmpeg`
- macOS: `brew install ffmpeg`

3. Chạy server:
```bash
python api_server.py
```

Server sẽ chạy tại: http://localhost:5000

## Cấu trúc thư mục

```
backend/
├── api_server.py          # Flask API server chính
├── database.py            # Quản lý database SQLite
├── requirements.txt       # Python dependencies
├── templates/            # HTML templates
│   ├── index.html        # Trang chủ
│   ├── admin_login.html  # Đăng nhập admin
│   └── admin_dashboard.html # Dashboard admin
├── static/               # CSS, JS files
├── uploads/              # Thư mục upload (tự tạo)
└── outputs/              # Thư mục output audio (tự tạo)
```

## API Endpoints

### Authentication
- `POST /api/auth/login` - Đăng nhập
- `POST /api/auth/register` - Đăng ký

### API Keys
- `POST /api/keys/create` - Tạo API key
- `GET /api/keys/list` - Danh sách API keys

### Voice Generation
- `POST /api/voice/create` - Tạo voice từ text
- `GET /api/voice/download/<filename>` - Tải file audio

### Statistics
- `GET /api/stats` - Thống kê user

### Admin (cần quyền admin)
- `GET /api/admin/users` - Danh sách users
- `GET /api/admin/gemini-keys` - Danh sách Gemini keys
- `POST /api/admin/gemini-keys` - Thêm Gemini key

## Admin Panel

Truy cập: http://localhost:5000/admin

**Tài khoản mặc định:**
- Username: `admin`
- Password: `admin123`

## Cấu hình

### Thêm Gemini API Keys

1. Đăng nhập admin panel
2. Vào mục "Gemini Keys"
3. Thêm các API key Gemini của bạn

### Tạo API Key cho User

1. Đăng nhập với tài khoản user
2. Gọi API `/api/keys/create` để tạo key
3. Sử dụng key này để gọi API voice

## Sử dụng API

### Tạo Voice

```bash
curl -X POST "http://localhost:5000/api/voice/create" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "key=YOUR_API_KEY" \
  -d "text=Hello, world!" \
  -d "voice_code=en-US-Neural2-A"
```

### Response

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

## Database Schema

### Users Table
- `id` - Primary key
- `username` - Tên đăng nhập
- `email` - Email
- `password_hash` - Mật khẩu đã hash
- `role` - Vai trò (user/admin)
- `is_active` - Trạng thái hoạt động

### API Keys Table
- `id` - Primary key
- `user_id` - ID user sở hữu
- `key_name` - Tên key
- `api_key` - Key thực tế
- `daily_limit` - Giới hạn ngày
- `monthly_limit` - Giới hạn tháng
- `expires_at` - Ngày hết hạn

### Usage Logs Table
- `id` - Primary key
- `api_key_id` - ID API key
- `user_id` - ID user
- `text_length` - Độ dài text
- `voice_name` - Tên voice
- `duration` - Thời lượng audio
- `created_at` - Thời gian tạo

## Troubleshooting

### Lỗi FFmpeg
- Đảm bảo FFmpeg đã được cài đặt và có trong PATH
- Kiểm tra quyền ghi file trong thư mục outputs/

### Lỗi Gemini API
- Kiểm tra API key Gemini có hợp lệ
- Đảm bảo có ít nhất 1 Gemini key active trong database

### Lỗi Database
- Xóa file `voice_api.db` để reset database
- Server sẽ tự tạo lại database với dữ liệu mặc định

## License

MIT License