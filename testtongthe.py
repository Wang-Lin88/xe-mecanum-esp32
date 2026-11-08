import sys
import uselect
from machine import PWM, Pin, time_pulse_us
from time import sleep, sleep_us

# =====================================================================
# 1. KHỞI TẠO CHÂN ĐIỀU KHIỂN ĐỘNG CƠ (Theo sơ đồ)
# =====================================================================
IN1A = Pin(48, Pin.OUT, value=0)  # tien banh 1
IN1B = Pin(42, Pin.OUT, value=0)  # lui banh 1
IN2A = Pin(16, Pin.OUT, value=0)  # tien banh 2
IN2B = Pin(8, Pin.OUT, value=0)   # lui banh 2
IN3A = Pin(38, Pin.OUT, value=0)  # tien banh 3
IN3B = Pin(47, Pin.OUT, value=0)  # lui banh 3
IN4A = Pin(7, Pin.OUT, value=0)   # tien banh 4
IN4B = Pin(9, Pin.OUT, value=0)   # lui banh 4

EN1 = PWM(Pin(36), freq=1000, duty_u16=0)  # EN banh 1
EN2 = PWM(Pin(18), freq=1000, duty_u16=0)  # EN banh 2
EN3 = PWM(Pin(35), freq=1000, duty_u16=0)  # EN banh 3
EN4 = PWM(Pin(10), freq=1000, duty_u16=0)  # EN banh 4

# =====================================================================
# 2. KHỞI TẠO 3 CẢM BIẾN SIÊU ÂM HC-SR04
# =====================================================================
# Con 1: Ở GIỮA (Trig: GPIO 6, Echo: GPIO 5)
trig1 = Pin(6, Pin.OUT, value=0)
echo1 = Pin(5, Pin.IN)

# Con 2: BÊN PHẢI (Trig: GPIO 40 theo đính chính, Echo: GPIO 17)
trig2 = Pin(40, Pin.OUT, value=0)
echo2 = Pin(17, Pin.IN)

# Con 3: BÊN TRÁI (Trig: GPIO 1, Echo: GPIO 15)
trig3 = Pin(1, Pin.OUT, value=0)
echo3 = Pin(15, Pin.IN)

# =====================================================================
# 3. KHỞI TẠO CẢM BIẾN DÒ LINE (HÌNH DẤU CỘNG)
#    - Con 1: Đầu xe (Trước) -> GPIO 13
#    - Con 2: Bên Phải       -> GPIO 12
#    - Con 3: Ở dưới (Sau)   -> GPIO 11 (BỊ HỎNG - KHÔNG DÙNG)
#    - Con 4: Bên Trái       -> GPIO 21
# =====================================================================
pin_line1_truoc = Pin(13, Pin.IN)  # Con 1: Đầu xe
pin_line2_phai  = Pin(12, Pin.IN)  # Con 2: Bên phải
pin_line4_trai  = Pin(21, Pin.IN)  # Con 4: Bên trái

# =====================================================================
# 4. KHỞI TẠO 4 ENCODER ĐẾM XUNG (Theo sơ đồ)
#    - Encoder 1 (Bánh 1 - Trước Trái): GPIO 14
#    - Encoder 2 (Bánh 2 - Trước Phải): GPIO 4
#    - Encoder 3 (Bánh 3 - Sau Trái)  : GPIO 20
#    - Encoder 4 (Bánh 4 - Sau Phải)  : GPIO 2
# =====================================================================
pin_enc1 = Pin(14, Pin.IN)
pin_enc2 = Pin(4, Pin.IN)
pin_enc3 = Pin(20, Pin.IN)
pin_enc4 = Pin(2, Pin.IN)

enc_cnt = [0, 0, 0, 0]  # Số xung cộng dồn [M1, M2, M3, M4]

def _irq_enc0(p): enc_cnt[0] += 1
def _irq_enc1(p): enc_cnt[1] += 1
def _irq_enc2(p): enc_cnt[2] += 1
def _irq_enc3(p): enc_cnt[3] += 1

pin_enc1.irq(trigger=Pin.IRQ_RISING, handler=_irq_enc0)
pin_enc2.irq(trigger=Pin.IRQ_RISING, handler=_irq_enc1)
pin_enc3.irq(trigger=Pin.IRQ_RISING, handler=_irq_enc2)
pin_enc4.irq(trigger=Pin.IRQ_RISING, handler=_irq_enc3)

# Mức logic khi chạm vạch đen: Bạn đã test thực tế Tối = 0, Sáng = 1 -> Đặt là 0
LINE_BLACK = 0

# =====================================================================
# CẤU HÌNH CHẾ ĐỘ HOẠT ĐỘNG
# =====================================================================
# "LINE"   : TỰ ĐỘNG CHẠY DÒ LINE NGAY KHI KHỞI ĐỘNG (Khuyên dùng khi đặt xe xuống sàn)
# "MANUAL" : Chờ lệnh điều khiển qua phím W, S, A, D, L trên Thonny Shell
che_do = "LINE"

tocdo = 50                 # Tốc độ chế độ lái thủ công (50%)
tocdo_line = 38            # Tốc độ khi dò line (35 - 45% để bám vạch tốt)
huong_sua_line = "thang"   # Hướng sửa lệch gần nhất
lenh_line_cu = ""          # Lệnh dò line trước đó để tránh ngắt giật PWM

khoa_giua = 1
khoa_phai = 1
khoa_trai = 1


# =====================================================================
# 4. CÁC HÀM ĐIỀU KHIỂN CHUYỂN ĐỘNG
# =====================================================================
def toc_do(trai, phai):
    EN1.duty_u16(int(trai * 65535 / 100))
    EN2.duty_u16(int(phai * 65535 / 100))
    EN3.duty_u16(int(trai * 65535 / 100))
    EN4.duty_u16(int(phai * 65535 / 100))


def dung():
    toc_do(0, 0)
    IN1A.value(0); IN1B.value(0)
    IN2A.value(0); IN2B.value(0)
    IN3A.value(0); IN3B.value(0)
    IN4A.value(0); IN4B.value(0)


def dithang(spd=None):
    s = tocdo if spd is None else spd
    IN1A.value(1); IN2A.value(1); IN3A.value(1); IN4A.value(1)
    IN1B.value(0); IN2B.value(0); IN3B.value(0); IN4B.value(0)
    toc_do(s, s)


def luixuong(spd=None):
    s = tocdo if spd is None else spd
    IN1A.value(0); IN2A.value(0); IN3A.value(0); IN4A.value(0)
    IN1B.value(1); IN2B.value(1); IN3B.value(1); IN4B.value(1)
    toc_do(s, s)


def retrai(spd=None):
    s = tocdo if spd is None else spd
    IN1A.value(0); IN2A.value(1); IN3A.value(1); IN4A.value(0)
    IN1B.value(1); IN2B.value(0); IN3B.value(0); IN4B.value(1)
    toc_do(s, s)


def rephai(spd=None):
    s = tocdo if spd is None else spd
    IN1A.value(1); IN2A.value(0); IN3A.value(0); IN4A.value(1)
    IN1B.value(0); IN2B.value(1); IN3B.value(1); IN4B.value(0)
    toc_do(s, s)


def lentrai(spd=None):
    s = tocdo if spd is None else spd
    IN1A.value(0); IN2A.value(1); IN3A.value(1); IN4A.value(0)
    IN1B.value(0); IN2B.value(0); IN3B.value(0); IN4B.value(0)
    toc_do(s, s)


def lenphai(spd=None):
    s = tocdo if spd is None else spd
    IN1A.value(1); IN2A.value(0); IN3A.value(0); IN4A.value(1)
    IN1B.value(0); IN2B.value(0); IN3B.value(0); IN4B.value(0)
    toc_do(s, s)


def xuongtrai(spd=None):
    s = tocdo if spd is None else spd
    IN1A.value(0); IN2A.value(0); IN3A.value(0); IN4A.value(0)
    IN1B.value(1); IN2B.value(0); IN3B.value(0); IN4B.value(1)
    toc_do(s, s)


def xuongphai(spd=None):
    s = tocdo if spd is None else spd
    IN1A.value(0); IN2A.value(0); IN3A.value(0); IN4A.value(0)
    IN1B.value(0); IN2B.value(1); IN3B.value(1); IN4B.value(0)
    toc_do(s, s)


# =====================================================================
# 5. HÀM ĐO KHOẢNG CÁCH SIÊU ÂM
# =====================================================================
def do_khoang_cach(trig_pin, echo_pin):
    trig_pin.value(0)
    sleep_us(2)
    trig_pin.value(1)
    sleep_us(10)
    trig_pin.value(0)

    thoi_gian = time_pulse_us(echo_pin, 1, 30000)
    if thoi_gian < 0:
        return None

    return (thoi_gian * 0.0343) / 2


def doc_3_cam_bien():
    kc_g = do_khoang_cach(trig1, echo1)
    sleep_us(800)
    kc_p = do_khoang_cach(trig2, echo2)
    sleep_us(800)
    kc_t = do_khoang_cach(trig3, echo3)
    return kc_g, kc_p, kc_t


# =====================================================================
# 6. HÀM DÒ LINE
# =====================================================================
def doc_line():
    """
    Trả về (trai, truoc, phai): 1 = gặp vạch đen, 0 = nền trắng
    """
    t = 1 if pin_line4_trai.value() == LINE_BLACK else 0
    g = 1 if pin_line1_truoc.value() == LINE_BLACK else 0
    p = 1 if pin_line2_phai.value() == LINE_BLACK else 0
    return t, g, p


def dat_chuyen_dong_line(cmd, spd):
    """Chuyển hướng mượt mà, chỉ đổi trạng thái chân khi lệnh thay đổi"""
    global lenh_line_cu
    if cmd == lenh_line_cu:
        return
    if cmd == "thang":
        dithang(spd)
    elif cmd == "lentrai":
        lentrai(spd)
    elif cmd == "retrai":
        retrai(spd)
    elif cmd == "lenphai":
        lenphai(spd)
    elif cmd == "rephai":
        rephai(spd)
    elif cmd == "dung":
        dung()
    lenh_line_cu = cmd


def xu_ly_do_line(kc_g):
    global huong_sua_line

    # 1. Bảo vệ vật cản: Nếu có chướng ngại vật phía trước < 15cm -> Dừng ngay
    if kc_g is not None and kc_g < 15:
        dat_chuyen_dong_line("dung", 0)
        return "CẢNH BÁO: VẬT CẢN PHÍA TRƯỚC -> DỪNG!"

    # 2. Đọc 3 mắt line: Trái (Con 4), Trước (Con 1), Phải (Con 2)
    s_trai, s_truoc, s_phai = doc_line()

    # TH1: Đúng line (Chỉ con 1 ở giữa chạm vạch) -> Đi thẳng
    if s_truoc == 1 and s_trai == 0 and s_phai == 0:
        dat_chuyen_dong_line("thang", tocdo_line)
        huong_sua_line = "thang"
        return "Đi thẳng (Đúng line)"

    # TH2: Vạch nằm bên TRÁI (Con 4 chạm vạch -> Xe bị lệch sang phải)
    elif s_trai == 1 and s_phai == 0:
        huong_sua_line = "trai"
        if s_truoc == 1:
            dat_chuyen_dong_line("lentrai", tocdo_line)
            return "Lệch nhẹ trái -> Lên-Trái"
        else:
            dat_chuyen_dong_line("retrai", tocdo_line)
            return "Lệch sâu trái -> Trượt Trái"

    # TH3: Vạch nằm bên PHẢI (Con 2 chạm vạch -> Xe bị lệch sang trái)
    elif s_phai == 1 and s_trai == 0:
        huong_sua_line = "phai"
        if s_truoc == 1:
            dat_chuyen_dong_line("lenphai", tocdo_line)
            return "Lệch nhẹ phải -> Lên-Phải"
        else:
            dat_chuyen_dong_line("rephai", tocdo_line)
            return "Lệch sâu phải -> Trượt Phải"

    # TH4: Cả 3 mắt chạm vạch (Ngã ba / Ngã tư / Vạch dừng ngang)
    elif s_trai == 1 and s_truoc == 1 and s_phai == 1:
        dat_chuyen_dong_line("thang", tocdo_line)
        return "Ngã tư / Vạch ngang -> Đi thẳng qua"

    # TH5: Mất line (Cả 3 mắt đều = 0) -> Sửa theo hướng lệch gần nhất
    else:
        if huong_sua_line == "trai":
            dat_chuyen_dong_line("retrai", tocdo_line)
            return "Mất vạch -> Trượt Trái tìm lại line"
        elif huong_sua_line == "phai":
            dat_chuyen_dong_line("rephai", tocdo_line)
            return "Mất vạch -> Trượt Phải tìm lại line"
        else:
            dat_chuyen_dong_line("thang", int(tocdo_line * 0.7))
            return "Mất vạch -> Tiến chậm dò tiếp"


# =====================================================================
# 7. KHỞI ĐỘNG VÀ VÒNG LẶP CHÍNH
# =====================================================================
poll = uselect.poll()
poll.register(sys.stdin, uselect.POLLIN)

dung()
print("=" * 65)
print("  XE MECANUM ESP32 - CHUẨN BỊ CHẠY...")
print("  Chế độ ban đầu:", che_do)
print("  Xe sẽ bắt đầu sau 2 giây (hãy đặt xe lên vạch đen)...")
print("=" * 65)
sleep(2)

lenh_dang_chay = "f" if che_do == "MANUAL" else "w"
lenh_cu = ""
khoa_giua_cu = 1
khoa_phai_cu = 1
khoa_trai_cu = 1
dem_in = 0

while True:
    # 1. Đọc 3 cảm biến siêu âm
    kc_giua, kc_phai, kc_trai = doc_3_cam_bien()

    # 2. Khóa an toàn theo từng hướng (< 15 cm thì khóa)
    khoa_giua = 0 if (kc_giua is not None and kc_giua < 15) else 1
    khoa_phai = 0 if (kc_phai is not None and kc_phai < 15) else 1
    khoa_trai = 0 if (kc_trai is not None and kc_trai < 15) else 1

    # 3. Đọc phím từ Shell Thonny nếu người dùng bấm
    if poll.poll(0):
        lenh = sys.stdin.read(1)
        if lenh:
            lenh = lenh.lower()
            if lenh == "l":
                che_do = "LINE"
                lenh_line_cu = ""
                print("\n>>> ĐÃ CHUYỂN SANG DÒ LINE TỰ ĐỘNG! <<<\n")
            elif lenh == "r":
                for i in range(4): enc_cnt[i] = 0
                print("\n>>> ĐÃ RESET BỘ ĐẾM ENCODER VỀ 0! <<<\n")
            elif lenh in "wsadqezcf":
                che_do = "MANUAL"
                lenh_dang_chay = lenh

    # 4. Thực thi theo chế độ
    if che_do == "LINE":
        hanh_dong = xu_ly_do_line(kc_giua)
        dem_in += 1
        if dem_in % 12 == 0:
            st, sg, sp = doc_line()
            print("[DÒ LINE] T:%d G:%d P:%d | %-24s | Xung: M1:%d M2:%d M3:%d M4:%d" % (
                st, sg, sp, hanh_dong, enc_cnt[0], enc_cnt[1], enc_cnt[2], enc_cnt[3]
            ))

    else:
        # Chế độ điều khiển thủ công
        trang_thai_khoa_doi = (khoa_giua != khoa_giua_cu) or (khoa_phai != khoa_phai_cu) or (khoa_trai != khoa_trai_cu)

        if lenh_dang_chay != lenh_cu or trang_thai_khoa_doi:
            if lenh_dang_chay == "w":
                if khoa_giua: dithang()
                else: dung()
            elif lenh_dang_chay == "a":
                if khoa_trai: retrai()
                else: dung()
            elif lenh_dang_chay == "d":
                if khoa_phai: rephai()
                else: dung()
            elif lenh_dang_chay == "s":
                luixuong()
            elif lenh_dang_chay == "q":
                if khoa_giua and khoa_trai: lentrai()
                else: dung()
            elif lenh_dang_chay == "e":
                if khoa_giua and khoa_phai: lenphai()
                else: dung()
            elif lenh_dang_chay == "z":
                xuongtrai()
            elif lenh_dang_chay == "c":
                xuongphai()
            elif lenh_dang_chay == "f":
                dung()

            lenh_cu = lenh_dang_chay
            khoa_giua_cu = khoa_giua
            khoa_phai_cu = khoa_phai
            khoa_trai_cu = khoa_trai

        if (lenh_dang_chay == "w" and not khoa_giua) or \
           (lenh_dang_chay == "q" and (not khoa_giua or not khoa_trai)) or \
           (lenh_dang_chay == "e" and (not khoa_giua or not khoa_phai)) or \
           (lenh_dang_chay == "a" and not khoa_trai) or \
           (lenh_dang_chay == "d" and not khoa_phai):
            dung()

        dem_in += 1
        if dem_in % 20 == 0:
            t_str = ("%.1f" % kc_trai) if kc_trai is not None else "--"
            g_str = ("%.1f" % kc_giua) if kc_giua is not None else "--"
            p_str = ("%.1f" % kc_phai) if kc_phai is not None else "--"
            print("[THỦ CÔNG] Siêu âm: T:%5s G:%5s P:%5s cm | Lệnh: %s | Xung M1..M4: %s" % (
                t_str, g_str, p_str, lenh_dang_chay, str(enc_cnt)
            ))

    sleep(0.02)
