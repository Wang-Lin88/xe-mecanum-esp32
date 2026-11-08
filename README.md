# Xe tự hành bánh Mecanum – ESP32-S3 (MicroPython)

Final Project: xe 4 bánh Mecanum điều khiển qua WiFi, dò line và tự phanh khi gặp vật cản.

## Các file
| File | Chức năng |
|---|---|
| `xe_dieukhien.py` | Điều khiển tay: web qua WiFi + bàn phím trong Thonny, tự phanh khi vật cản phía trước < 15 cm (không dò line). |
| `web_control.py` | Như trên, thêm chế độ **dò line** bằng 3 cảm biến TCRT5000 (trước/phải/trái) theo luật 3 bit. |

## Phần cứng
- ESP32-S3, 2 driver L298N, 4 động cơ V1 + bánh Mecanum, 3 HC-SR04, 4 encoder chữ U, TCRT5000, nguồn 3×18650 + LM2596.
- Chân IN (chiều quay): 1A/1B = 48/42, 2A/2B = 16/8, 3A/3B = 38/47, 4A/4B = 7/9. Chân EN (PWM 1 kHz): 36, 18, 35, 10.
- HC-SR04 (Trig/Echo): giữa 6/5, phải 40/17, trái 1/15.
- Encoder: GPIO 14, 4, 20, 2 (đếm xung bằng ngắt).
- TCRT5000 (web_control.py): trước 13, phải 12, trái 21 (cảm biến sau GPIO 11 hỏng, không dùng).

## Cách chạy
1. Nạp MicroPython cho ESP32-S3, mở Thonny.
2. Mở `web_control.py` (hoặc `xe_dieukhien.py`) → Run (F5) hoặc lưu thành `main.py` trên board.
3. Điện thoại kết nối WiFi **ESP32_XE_MECANUM**, mở trình duyệt vào **http://192.168.4.1**.
4. Điều khiển bằng nút trên web; chuyển chế độ Thủ công / Dò line; chỉnh tốc độ bằng thanh trượt.

## Giao diện HTTP
`/` giao diện · `/sensor` JSON cảm biến · `/reset_enc` · `/cmd?key=` · `/mode?val=manual|line` · `/speed?val=`
