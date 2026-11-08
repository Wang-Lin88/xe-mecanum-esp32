# =====================================================================
#  FILE KIỂM TRA ĐỘNG CƠ ĐỘC LẬP (TEST_DONGCO.PY)
#  Không dùng cảm biến - Chỉ quay từng bánh để kiểm tra nguồn và dây
# =====================================================================
from machine import Pin, PWM
from time import sleep

print("=" * 50)
print("  KIỂM TRA 4 ĐỘNG CƠ L298N (MỖI BÁNH QUAY 2 GIÂY)")
print("  Kê 4 bánh xe hổng khỏi mặt đất để kiểm tra!")
print("=" * 50)

# Khởi tạo chân IN
IN1A = Pin(48, Pin.OUT, value=0)
IN1B = Pin(42, Pin.OUT, value=0)
IN2A = Pin(16, Pin.OUT, value=0)
IN2B = Pin(8, Pin.OUT, value=0)
IN3A = Pin(38, Pin.OUT, value=0)
IN3B = Pin(47, Pin.OUT, value=0)
IN4A = Pin(7, Pin.OUT, value=0)
IN4B = Pin(9, Pin.OUT, value=0)

# Khởi tạo chân EN (PWM)
EN1 = PWM(Pin(36), freq=1000, duty_u16=0)
EN2 = PWM(Pin(18), freq=1000, duty_u16=0)
EN3 = PWM(Pin(35), freq=1000, duty_u16=0)
EN4 = PWM(Pin(10), freq=1000, duty_u16=0)

def dung_het():
    EN1.duty_u16(0); EN2.duty_u16(0); EN3.duty_u16(0); EN4.duty_u16(0)
    IN1A.value(0); IN1B.value(0)
    IN2A.value(0); IN2B.value(0)
    IN3A.value(0); IN3B.value(0)
    IN4A.value(0); IN4B.value(0)

dung_het()
sleep(1)

# TEST BÁNH 1
print("\n>>> BÁNH 1 (Trước - Trái) QUAY TIẾN 2 GIÂY...")
IN1A.value(1); IN1B.value(0)
EN1.duty_u16(45000) # ~70% tốc độ
sleep(2)
dung_het()
sleep(1)

# TEST BÁNH 2
print(">>> BÁNH 2 (Trước - Phải) QUAY TIẾN 2 GIÂY...")
IN2A.value(1); IN2B.value(0)
EN2.duty_u16(45000)
sleep(2)
dung_het()
sleep(1)

# TEST BÁNH 3
print(">>> BÁNH 3 (Sau - Trái) QUAY TIẾN 2 GIÂY...")
IN3A.value(1); IN3B.value(0)
EN3.duty_u16(45000)
sleep(2)
dung_het()
sleep(1)

# TEST BÁNH 4
print(">>> BÁNH 4 (Sau - Phải) QUAY TIẾN 2 GIÂY...")
IN4A.value(1); IN4B.value(0)
EN4.duty_u16(45000)
sleep(2)
dung_het()

print("\n[HOÀN THÀNH] Đã test xong 4 bánh!")
