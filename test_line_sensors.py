# =====================================================================
#  KIỂM TRA 3 MẮT CẢM BIẾN DÒ LINE TCRT5000
#  - Con 1 (Trước): GPIO 13
#  - Con 2 (Phải) : GPIO 12
#  - Con 4 (Trái) : GPIO 21
# =====================================================================
from machine import Pin
from time import sleep

s_truoc = Pin(13, Pin.IN)  # Con 1
s_phai  = Pin(12, Pin.IN)  # Con 2
s_trai  = Pin(21, Pin.IN)  # Con 4

print("=" * 55)
print("  KIỂM TRA 3 CẢM BIẾN DÒ LINE (ĐẶT XE LÊN NỀN TRẮNG VÀ VẠCH ĐEN)")
print("=" * 55)

while True:
    val_t = s_trai.value()
    val_g = s_truoc.value()
    val_p = s_phai.value()
    
    # In ra giá trị raw (0 hoặc 1) của từng chân GPIO
    print("Trái (Con 4): %d  |  Trước (Con 1): %d  |  Phải (Con 2): %d" % (val_t, val_g, val_p))
    sleep(0.3)
