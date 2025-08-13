# Voice Tool Pro - Tối ưu hóa với tính năng SRT

## 🚀 Tính năng mới

### ✨ Tính năng SRT
- **Xuất SRT từng file**: Mỗi hàng có nút "📝 SRT" để xuất file SRT riêng lẻ
- **Xuất SRT tất cả**: Nút "📝 Export SRT" để xuất file SRT cho tất cả audio đã convert
- **Tự động tính timing**: SRT được tạo tự động dựa trên duration của audio
- **🆕 Tự động xuất SRT**: SRT được tự động xuất sau khi convert xong
- **🆕 SRT ngay lập tức**: Có thể xuất SRT ngay sau khi import Excel (không cần chờ convert)
- **🆕 Lưu cùng thư mục**: File SRT được lưu cùng thư mục với audio đã convert

### 🔧 Tối ưu hóa đã thực hiện

#### 1. **Cải thiện UI/UX**
- Thêm progress bar tổng thể với gradient đẹp
- Cải thiện giao diện với màu sắc và icon hiện đại
- Thêm cột SRT vào bảng
- Tối ưu hóa kích thước cột
- **Style đẹp cho tất cả controls:**
  - Button với hover effects và màu sắc đẹp
  - ComboBox với border và focus states
  - SpinBox với up/down buttons đẹp
  - Table với header màu xanh và alternating rows
  - GroupBox với border và title đẹp
  - Progress bar với gradient màu

#### 2. **Cải thiện Performance**
- Thêm progress tracking cho từng thread
- Tối ưu hóa quản lý thread
- Cải thiện error handling
- Auto-save config mỗi 30 giây

#### 3. **Tính năng mới**
- Có thể điều chỉnh số lượng thread tối đa
- Lưu trữ duration cho mỗi audio
- Hỗ trợ xuất SRT với timing chính xác

## 📋 Cách sử dụng

### 1. **Import Excel**
- File Excel cần có cột "text" chứa nội dung cần convert
- Cột đầu tiên (A) chứa số thứ tự
- Cột thứ hai (B) chứa nội dung text

### 2. **Chọn giọng nói**
- Chọn giọng nói từ dropdown
- Có thể nghe thử bằng nút "▶️ Listen"

### 3. **Convert Audio**
- Nhấn "🚀 Start Convert"
- Chọn thư mục lưu
- Theo dõi tiến trình qua progress bar

### 4. **Xuất SRT**
- **🆕 Xuất ngay lập tức**: Nhấn nút "📝 SRT" ở mỗi hàng ngay sau khi import Excel
- **🆕 Tự động xuất**: SRT được tự động xuất sau khi convert xong
- **Xuất tất cả**: Nhấn nút "📝 Export SRT" ở control panel
- **Lưu tự động**: File SRT được lưu cùng thư mục với audio (ví dụ: `1_text.mp3` → `1_text.srt`)

## 🎯 Cấu trúc file SRT

File SRT được tạo với format chuẩn:
```
1
00:00:00,000 --> 00:00:05,250
Nội dung text thứ nhất

2
00:00:05,250 --> 00:00:10,500
Nội dung text thứ hai
```

## ⚙️ Cấu hình

### **config.json**
```json
{
    "proxy_type": "http",
    "max_concurrent_threads": 2
}
```

### **Tùy chỉnh**
- **Proxy Type**: Chọn loại proxy (http/socks5)
- **Max Threads**: Điều chỉnh số lượng thread đồng thời (1-10)
- **Auto-save**: Config được lưu tự động mỗi 30 giây

## 🔍 Troubleshooting

### **Lỗi thường gặp**
1. **"Không thể đọc file Excel"**
   - Kiểm tra định dạng file (.xlsx)
   - Đảm bảo có cột "text"

2. **"Thiếu Giọng Nói"**
   - Chọn giọng nói từ dropdown
   - Kiểm tra kết nối internet

3. **"Thiếu API Key"**
   - Đảm bảo đã đăng nhập thành công
   - Kiểm tra kết nối internet

4. **"Lỗi khi xuất SRT"**
   - Đảm bảo audio đã convert thành công
   - Kiểm tra quyền ghi file

5. **"QMediaPlayer finished signal error"**
   - Đã được sửa trong phiên bản mới
   - Sử dụng stateChanged signal thay thế

## 📁 Cấu trúc thư mục

```
VoiceGoogleV1/
├── main.py              # File chính đã tối ưu hóa
├── config.json          # Cấu hình
├── proxies.txt          # Danh sách proxy
├── voices/              # Thư mục chứa audio đã convert
├── auth_guard.py        # Xác thực
├── proxy_manager.py     # Quản lý proxy
├── version_checker.py   # Kiểm tra version
└── updater.py           # Cập nhật
```

## 🚀 Khởi chạy

### **Chạy chính**
```bash
python main.py
```

### **Test tính năng**
```bash
# Test import và các class
python test_main.py

# Test tính năng SRT
python demo_srt.py

# Test giao diện UI (không cần login)
python test_ui.py

# Test tính năng tự động xuất SRT
python demo_auto_srt.py
```

## 📝 Ghi chú

- **Tối ưu hóa**: Code đã được refactor và tối ưu hóa để dễ bảo trì
- **Error Handling**: Cải thiện xử lý lỗi và thông báo
- **Performance**: Tối ưu hóa quản lý thread và memory
- **User Experience**: Giao diện thân thiện và dễ sử dụng hơn

## 🔄 Cập nhật

- Tự động kiểm tra version mới
- Thông báo khi có update
- Hướng dẫn cập nhật

---

**Phiên bản**: Tối ưu hóa với SRT  
**Tác giả**: @huyit32  
**Ngày cập nhật**: $(date +%Y-%m-%d) 