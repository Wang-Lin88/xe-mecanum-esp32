# =====================================================================
#  XE MECANUM ESP32 - BẢN ĐIỀU KHIỂN QUAY VIDEO NỘP BÀI (KHÔNG DÒ LINE)
#  - Điều khiển xe Mecanum 8 hướng + Xoay tròn tại chỗ
#  - 3 Cảm biến siêu âm HC-SR04 (Trái: 1, 15 | Giữa: 6, 5 | Phải: 40, 17)
#    -> Tự phanh dừng thông minh khi gặp vật cản (< 15cm)
#  - 4 Encoder đếm xung 4 bánh (GPIO 14, 4, 20, 2)
#  - Hỗ trợ cả 2 cách điều khiển:
#      1. Qua Web WiFi trên điện thoại (http://192.168.4.1)
#      2. Qua bàn phím máy tính trong Thonny Shell (W, S, A, D, Q, E, Z, C, F)
# =====================================================================

import network
import socket
import time
import gc
import sys
import uselect
from machine import Pin, PWM, time_pulse_us
from time import sleep_ms, sleep_us

# ---------------------------------------------------------------------
# 1. CẤU HÌNH WIFI (ESP32 TỰ PHÁT WIFI)
# ---------------------------------------------------------------------
WIFI_MODE = "AP"
AP_SSID = "ESP32_XE_MECANUM"
AP_PASS = "12345678"          # Mật khẩu WiFi (tối thiểu 8 ký tự)
STA_SSID = "Ten_Wifi_Nha_Ban"
STA_PASS = "Mat_Khau_Wifi"

# ---------------------------------------------------------------------
# 2. KHỞI TẠO CHÂN ĐỘNG CƠ (Theo sơ đồ)
# ---------------------------------------------------------------------
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

# ---------------------------------------------------------------------
# 3. KHỞI TẠO 3 CẢM BIẾN SIÊU ÂM HC-SR04
# ---------------------------------------------------------------------
# Con 1: Ở GIỮA (Trig: 6, Echo: 5)
trig1 = Pin(6, Pin.OUT, value=0)
echo1 = Pin(5, Pin.IN)

# Con 2: BÊN PHẢI (Trig: 40 theo đính chính, Echo: 17)
trig2 = Pin(40, Pin.OUT, value=0)
echo2 = Pin(17, Pin.IN)

# Con 3: BÊN TRÁI (Trig: 1, Echo: 15)
trig3 = Pin(1, Pin.OUT, value=0)
echo3 = Pin(15, Pin.IN)

# ---------------------------------------------------------------------
# 4. KHỞI TẠO 4 ENCODER ĐẾM XUNG (GPIO 14, 4, 20, 2)
# ---------------------------------------------------------------------
pin_enc1 = Pin(14, Pin.IN)
pin_enc2 = Pin(4, Pin.IN)
pin_enc3 = Pin(20, Pin.IN)
pin_enc4 = Pin(2, Pin.IN)
enc_cnt = [0, 0, 0, 0]

def _irq_enc0(p): enc_cnt[0] += 1
def _irq_enc1(p): enc_cnt[1] += 1
def _irq_enc2(p): enc_cnt[2] += 1
def _irq_enc3(p): enc_cnt[3] += 1

pin_enc1.irq(trigger=Pin.IRQ_RISING, handler=_irq_enc0)
pin_enc2.irq(trigger=Pin.IRQ_RISING, handler=_irq_enc1)
pin_enc3.irq(trigger=Pin.IRQ_RISING, handler=_irq_enc2)
pin_enc4.irq(trigger=Pin.IRQ_RISING, handler=_irq_enc3)

# Biến trạng thái toàn cục
tocdo = 60           # Tốc độ mặc định 60%
lenh_dang_chay = "f" # "f" = dừng
kc_giua = None
kc_phai = None
kc_trai = None
khoa_giua = 1
khoa_phai = 1
khoa_trai = 1

# ---------------------------------------------------------------------
# 5. HÀM ĐO KHOẢNG CÁCH SIÊU ÂM
# ---------------------------------------------------------------------
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
    global kc_giua, kc_phai, kc_trai, khoa_giua, khoa_phai, khoa_trai
    try:
        g = do_khoang_cach(trig1, echo1)
        sleep_us(800)
        p = do_khoang_cach(trig2, echo2)
        sleep_us(800)
        t = do_khoang_cach(trig3, echo3)

        kc_giua = round(g, 1) if (g is not None and 2.0 <= g <= 400.0) else None
        kc_phai = round(p, 1) if (p is not None and 2.0 <= p <= 400.0) else None
        kc_trai = round(t, 1) if (t is not None and 2.0 <= t <= 400.0) else None

        khoa_giua = 0 if (kc_giua is not None and kc_giua < 15) else 1
        khoa_phai = 0 if (kc_phai is not None and kc_phai < 15) else 1
        khoa_trai = 0 if (kc_trai is not None and kc_trai < 15) else 1
    except Exception:
        pass


# ---------------------------------------------------------------------
# 6. CÁC HÀM ĐIỀU KHIỂN CHUYỂN ĐỘNG MECANUM
# ---------------------------------------------------------------------
def toc_do(trai, phai):
    t_val = max(0, min(100, trai))
    p_val = max(0, min(100, phai))
    EN1.duty_u16(int(t_val * 65535 / 100))
    EN2.duty_u16(int(p_val * 65535 / 100))
    EN3.duty_u16(int(t_val * 65535 / 100))
    EN4.duty_u16(int(p_val * 65535 / 100))


def dung():
    global lenh_dang_chay
    toc_do(0, 0)
    IN1A.value(0); IN1B.value(0)
    IN2A.value(0); IN2B.value(0)
    IN3A.value(0); IN3B.value(0)
    IN4A.value(0); IN4B.value(0)
    lenh_dang_chay = "f"


def dithang(spd=None):
    s = tocdo if spd is None else spd
    toc_do(0, 0); sleep_ms(30)
    IN1A.value(1); IN2A.value(1); IN3A.value(1); IN4A.value(1)
    IN1B.value(0); IN2B.value(0); IN3B.value(0); IN4B.value(0)
    toc_do(s, s)


def luixuong(spd=None):
    s = tocdo if spd is None else spd
    toc_do(0, 0); sleep_ms(30)
    IN1A.value(0); IN2A.value(0); IN3A.value(0); IN4A.value(0)
    IN1B.value(1); IN2B.value(1); IN3B.value(1); IN4B.value(1)
    toc_do(s, s)


def retrai(spd=None):  # Trượt ngang trái
    s = tocdo if spd is None else spd
    toc_do(0, 0); sleep_ms(30)
    IN1A.value(0); IN2A.value(1); IN3A.value(1); IN4A.value(0)
    IN1B.value(1); IN2B.value(0); IN3B.value(0); IN4B.value(1)
    toc_do(s, s)


def rephai(spd=None):  # Trượt ngang phải
    s = tocdo if spd is None else spd
    toc_do(0, 0); sleep_ms(30)
    IN1A.value(1); IN2A.value(0); IN3A.value(0); IN4A.value(1)
    IN1B.value(0); IN2B.value(1); IN3B.value(1); IN4B.value(0)
    toc_do(s, s)


def lentrai(spd=None):  # Tiến chéo trái
    s = tocdo if spd is None else spd
    toc_do(0, 0); sleep_ms(30)
    IN1A.value(0); IN2A.value(1); IN3A.value(1); IN4A.value(0)
    IN1B.value(0); IN2B.value(0); IN3B.value(0); IN4B.value(0)
    toc_do(s, s)


def lenphai(spd=None):  # Tiến chéo phải
    s = tocdo if spd is None else spd
    toc_do(0, 0); sleep_ms(30)
    IN1A.value(1); IN2A.value(0); IN3A.value(0); IN4A.value(1)
    IN1B.value(0); IN2B.value(0); IN3B.value(0); IN4B.value(0)
    toc_do(s, s)


def xuongtrai(spd=None):  # Lùi chéo trái
    s = tocdo if spd is None else spd
    toc_do(0, 0); sleep_ms(30)
    IN1A.value(0); IN2A.value(0); IN3A.value(0); IN4A.value(0)
    IN1B.value(1); IN2B.value(0); IN3B.value(0); IN4B.value(1)
    toc_do(s, s)


def xuongphai(spd=None):  # Lùi chéo phải
    s = tocdo if spd is None else spd
    toc_do(0, 0); sleep_ms(30)
    IN1A.value(0); IN2A.value(0); IN3A.value(0); IN4A.value(0)
    IN1B.value(0); IN2B.value(1); IN3B.value(1); IN4B.value(0)
    toc_do(s, s)


def xoaytrai(spd=None):  # Xoay trái tại chỗ (CCW)
    s = tocdo if spd is None else spd
    toc_do(0, 0); sleep_ms(30)
    IN1A.value(0); IN2A.value(1); IN3A.value(0); IN4A.value(1)
    IN1B.value(1); IN2B.value(0); IN3B.value(1); IN4B.value(0)
    toc_do(s, s)


def xoayphai(spd=None):  # Xoay phải tại chỗ (CW)
    s = tocdo if spd is None else spd
    toc_do(0, 0); sleep_ms(30)
    IN1A.value(1); IN2A.value(0); IN3A.value(1); IN4A.value(0)
    IN1B.value(0); IN2B.value(1); IN3B.value(0); IN4B.value(1)
    toc_do(s, s)


def thuc_hien_lenh(lenh, spd):
    global lenh_dang_chay
    if lenh == "f": dung()
    elif lenh == "w": dithang(spd)
    elif lenh == "s": luixuong(spd)
    elif lenh == "a": retrai(spd)
    elif lenh == "d": rephai(spd)
    elif lenh == "q": lentrai(spd)
    elif lenh == "e": lenphai(spd)
    elif lenh == "z": xuongtrai(spd)
    elif lenh == "c": xuongphai(spd)
    elif lenh == "rotl": xoaytrai(spd)
    elif lenh == "rotr": xoayphai(spd)
    lenh_dang_chay = lenh


# ---------------------------------------------------------------------
# 7. KHỞI TẠO WIFI
# ---------------------------------------------------------------------
def bat_wifi():
    if WIFI_MODE == "AP":
        ap = network.WLAN(network.AP_IF)
        ap.active(True)
        if AP_PASS and len(AP_PASS) >= 8:
            ap.config(essid=AP_SSID, password=AP_PASS)
        else:
            ap.config(essid=AP_SSID, authmode=network.AUTH_OPEN)
        ip = ap.ifconfig()[0]
        print("\n" + "=" * 60)
        print("  [WIFI AP] ĐÃ PHÁT WIFI THÀNH CÔNG!")
        print("  Tên mạng (SSID) :", AP_SSID)
        print("  Mật khẩu        :", AP_PASS if AP_PASS else "(Không có)")
        print("  👉 Mở trình duyệt vào : http://" + ip)
        print("=" * 60 + "\n")
        return ip
    else:
        sta = network.WLAN(network.STA_IF)
        sta.active(True)
        print("Đang kết nối WiFi:", STA_SSID, "...")
        sta.connect(STA_SSID, STA_PASS)
        retry = 20
        while not sta.isconnected() and retry > 0:
            time.sleep(0.4)
            retry -= 1
        if sta.isconnected():
            ip = sta.ifconfig()[0]
            print("\n  👉 Mở trình duyệt vào : http://" + ip)
            return ip
        else:
            ap = network.WLAN(network.AP_IF)
            ap.active(True)
            ap.config(essid=AP_SSID, password=AP_PASS)
            ip = ap.ifconfig()[0]
            print("  👉 Mở trình duyệt vào : http://" + ip)
            return ip


# ---------------------------------------------------------------------
# 8. GIAO DIỆN WEB ĐIỀU KHIỂN (HTML/CSS/JS NHÚNG SẴN)
# ---------------------------------------------------------------------
HTML_PAGE = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no">
<title>Điều Khiển Xe Mecanum ESP32</title>
<style>
:root{--bg:#0b1329;--card:#1c2744;--border:#2f3e66;--primary:#38bdf8;--accent:#06b6d4;--btn:#1e293b;--btn-act:#0284c7;--danger:#ef4444;--warning:#f59e0b;--safe:#10b981;--text:#f8fafc;--text-dim:#94a3b8}
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent;user-select:none}
body{background:var(--bg);color:var(--text);font-family:system-ui,-apple-system,sans-serif;padding:12px;min-height:100vh;display:flex;flex-direction:column;align-items:center}
.container{width:100%;max-width:440px;display:flex;flex-direction:column;gap:10px}
.header{text-align:center;padding:2px 0}
.header h1{font-size:1.3rem;font-weight:700;color:var(--primary);display:flex;align-items:center;justify-content:center;gap:6px}
.badge-bar{display:flex;justify-content:center;gap:6px;font-size:0.75rem;margin-top:4px}
.badge{padding:3px 9px;border-radius:12px;background:#243256;display:inline-flex;align-items:center;gap:4px;font-weight:600}
.pulse{width:7px;height:7px;border-radius:50%;background:var(--safe);box-shadow:0 0 6px var(--safe);animation:blink 1.5s infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:0.3}}
.card{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:12px;box-shadow:0 6px 18px rgba(0,0,0,0.3)}

/* 3 SIÊU ÂM */
.sensor-title{font-size:0.78rem;font-weight:700;color:var(--text-dim);margin-bottom:6px;text-align:center}
.sensors-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.s-box{background:#131d36;border:1px solid var(--border);border-radius:10px;padding:6px;display:flex;flex-direction:column;align-items:center;text-align:center}
.s-label{font-size:0.68rem;font-weight:700;color:var(--text-dim);margin-bottom:2px}
.s-dist{font-size:1.3rem;font-weight:800;color:var(--primary);line-height:1.1}
.s-unit{font-size:0.62rem;color:var(--text-dim)}
.s-bar{width:100%;height:5px;background:#243256;border-radius:3px;overflow:hidden;margin-top:4px}
.s-fill{height:100%;width:50%;background:var(--safe);transition:width 0.2s,background 0.2s}
.s-box.locked{border-color:var(--danger);background:rgba(239,68,68,0.12)}

/* ENCODER */
.enc-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-top:6px;font-size:0.72rem;text-align:center}
.enc-box{background:#131d36;padding:4px;border-radius:8px;border:1px solid var(--border)}
.enc-box b{color:var(--primary);font-size:0.85rem}

.speed-row{display:flex;align-items:center;justify-content:space-between;font-size:0.82rem;font-weight:600;margin-bottom:6px}
.speed-slider{width:100%;height:7px;-webkit-appearance:none;background:#243256;border-radius:4px;outline:none}
.speed-slider::-webkit-slider-thumb{-webkit-appearance:none;width:22px;height:22px;border-radius:50%;background:var(--primary);cursor:pointer;border:2px solid #fff}
.speed-presets{display:flex;gap:6px;margin-top:6px}
.speed-presets button{flex:1;background:#243256;border:1px solid var(--border);border-radius:8px;color:var(--text);padding:4px 0;font-size:0.72rem;cursor:pointer;font-weight:600}

/* D-PAD MECANUM */
.dpad{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:4px}
.btn-pad{background:#243256;border:1px solid var(--border);color:var(--text);font-size:1.3rem;font-weight:700;height:64px;border-radius:12px;cursor:pointer;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;touch-action:none;transition:transform 0.05s,background 0.1s}
.btn-pad span{font-size:0.62rem;color:var(--text-dim);font-weight:700}
.btn-pad:active,.btn-pad.active{background:var(--btn-act);transform:scale(0.94);border-color:var(--primary)}
.btn-pad.locked-btn{opacity:0.35;border-color:var(--danger);cursor:not-allowed}
.btn-stop{background:linear-gradient(135deg,#b91c1c,#dc2626);border-color:#ef4444;color:#fff}
.btn-stop:active,.btn-stop.active{background:#7f1d1d}
.btn-stop span{color:#fecaca}

.rot-row{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px}
.rot-btn{height:48px;font-size:1rem;background:#243256;border:1px solid var(--border);border-radius:10px;color:var(--text);display:flex;align-items:center;justify-content:center;gap:6px;font-weight:600;touch-action:none;cursor:pointer}
.rot-btn:active,.rot-btn.active{background:var(--btn-act);transform:scale(0.95)}

.opt-row{display:flex;justify-content:space-between;align-items:center;font-size:0.78rem;color:var(--text-dim);margin-top:8px;padding-top:8px;border-top:1px solid var(--border)}
.switch{position:relative;display:inline-block;width:38px;height:20px}
.switch input{opacity:0;width:0;height:0}
.slider{position:absolute;cursor:pointer;top:0;left:0;right:0;bottom:0;background-color:#243256;border-radius:20px;transition:.2s}
.slider:before{position:absolute;content:"";height:14px;width:14px;left:3px;bottom:3px;background-color:white;border-radius:50%;transition:.2s}
input:checked + .slider{background-color:var(--accent)}
input:checked + .slider:before{transform:translateX(18px)}
.kbd-hint{text-align:center;font-size:0.68rem;color:var(--text-dim);margin-top:2px}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>🚗 XE MECANUM ESP32</h1>
    <div class="badge-bar">
      <span class="badge"><span class="pulse"></span> ONLINE</span>
      <span class="badge" id="cmdBadge">LỆNH: DỪNG</span>
      <span class="badge" id="speedBadge">TỐC ĐỘ: 60%</span>
    </div>
  </div>

  <!-- 3 CẢM BIẾN SIÊU ÂM (TRÁI - GIỮA - PHẢI) -->
  <div class="card">
    <div class="sensor-title">KHOẢNG CÁCH SIÊU ÂM HC-SR04 (cm)</div>
    <div class="sensors-grid">
      <div class="s-box" id="box_trai">
        <div class="s-label">👈 TRÁI (3)</div>
        <div class="s-dist" id="dist_t">--</div>
        <div class="s-unit">cm</div>
        <div class="s-bar"><div class="s-fill" id="bar_t"></div></div>
      </div>
      <div class="s-box" id="box_giua">
        <div class="s-label">☝️ GIỮA (1)</div>
        <div class="s-dist" id="dist_g">--</div>
        <div class="s-unit">cm</div>
        <div class="s-bar"><div class="s-fill" id="bar_g"></div></div>
      </div>
      <div class="s-box" id="box_phai">
        <div class="s-label">👉 PHẢI (2)</div>
        <div class="s-dist" id="dist_p">--</div>
        <div class="s-unit">cm</div>
        <div class="s-bar"><div class="s-fill" id="bar_p"></div></div>
      </div>
    </div>
  </div>

  <!-- 4 ENCODER ĐẾM XUNG -->
  <div class="card" style="padding:10px 12px">
    <div style="display:flex;justify-content:space-between;align-items:center;font-size:0.75rem;font-weight:700;color:var(--text-dim)">
      <span>ENCODER 4 BÁNH (Xung)</span>
      <button onclick="fetch('/reset_enc')" style="background:#243256;border:1px solid var(--border);border-radius:6px;color:var(--text);padding:2px 8px;font-size:0.68rem;cursor:pointer">Reset</button>
    </div>
    <div class="enc-grid">
      <div class="enc-box"><div style="color:var(--text-dim)">M1 (T-T)</div><b id="enc1">0</b></div>
      <div class="enc-box"><div style="color:var(--text-dim)">M2 (T-P)</div><b id="enc2">0</b></div>
      <div class="enc-box"><div style="color:var(--text-dim)">M3 (S-T)</div><b id="enc3">0</b></div>
      <div class="enc-box"><div style="color:var(--text-dim)">M4 (S-P)</div><b id="enc4">0</b></div>
    </div>
  </div>

  <!-- ĐIỀU CHỈNH TỐC ĐỘ -->
  <div class="card">
    <div class="speed-row">
      <span>TỐC ĐỘ ĐỘNG CƠ (tocdo)</span>
      <span id="speedVal" style="color:var(--primary);font-weight:700">60%</span>
    </div>
    <input type="range" class="speed-slider" id="speedSlider" min="25" max="100" value="60" oninput="setSpeed(this.value)">
    <div class="speed-presets">
      <button onclick="setSpeed(35)">35% Chậm</button>
      <button onclick="setSpeed(60)">60% Vừa</button>
      <button onclick="setSpeed(80)">80% Nhanh</button>
      <button onclick="setSpeed(100)">100% MAX</button>
    </div>
  </div>

  <!-- CỤM PHÍM MECANUM -->
  <div class="card">
    <div class="dpad">
      <button class="btn-pad" data-key="q" id="btn_q">↖<span>Q: Lên-T</span></button>
      <button class="btn-pad" data-key="w" id="btn_w">⬆<span>W: Tiến</span></button>
      <button class="btn-pad" data-key="e" id="btn_e">↗<span>E: Lên-P</span></button>

      <button class="btn-pad" data-key="a" id="btn_a">⬅<span>A: Trượt T</span></button>
      <button class="btn-pad btn-stop" data-key="f" id="btn_f">⏹<span>F: DỪNG</span></button>
      <button class="btn-pad" data-key="d" id="btn_d">➡<span>D: Trượt P</span></button>

      <button class="btn-pad" data-key="z" id="btn_z">↙<span>Z: Xuống-T</span></button>
      <button class="btn-pad" data-key="s" id="btn_s">⬇<span>S: Lùi</span></button>
      <button class="btn-pad" data-key="c" id="btn_c">↘<span>C: Xuống-P</span></button>
    </div>

    <div class="rot-row">
      <button class="rot-btn" data-key="rotl">↺ Xoay Trái (CCW)</button>
      <button class="rot-btn" data-key="rotr">↻ Xoay Phải (CW)</button>
    </div>

    <div class="opt-row">
      <span>Giữ nút để chạy (Nhả tay tự dừng)</span>
      <label class="switch">
        <input type="checkbox" id="holdToggle" checked>
        <span class="slider"></span>
      </label>
    </div>
  </div>

  <div class="kbd-hint">
    Phím máy tính: W/S (Tiến/Lùi) • A/D (Trượt) • Q/E (Lên T/P) • Z/C (Xuống T/P) • Space/F (Dừng)
  </div>
</div>

<script>
let curSpeed = 60;
let k_g = 1, k_p = 1, k_t = 1;

function sendKey(k) {
  const nameMap = {
    'w':'TIẾN (W)', 's':'LÙI (S)', 'a':'TRƯỢT T (A)', 'd':'TRƯỢT P (D)',
    'q':'LÊN T (Q)', 'e':'LÊN P (E)', 'z':'XUỐNG T (Z)', 'c':'XUỐNG P (C)',
    'f':'DỪNG (F)', 'rotl':'XOAY TRÁI', 'rotr':'XOAY PHẢI'
  };
  document.getElementById('cmdBadge').innerText = 'LỆNH: ' + (nameMap[k] || k.toUpperCase());
  fetch('/cmd?key=' + k + '&speed=' + curSpeed).catch(()=>{});
}

function setSpeed(v) {
  curSpeed = parseInt(v);
  document.getElementById('speedSlider').value = curSpeed;
  document.getElementById('speedVal').innerText = curSpeed + '%';
  document.getElementById('speedBadge').innerText = 'TỐC ĐỘ: ' + curSpeed + '%';
  fetch('/speed?val=' + curSpeed).catch(()=>{});
}

// Bắt sự kiện chạm giữ
const buttons = document.querySelectorAll('[data-key]');
buttons.forEach(btn => {
  const k = btn.getAttribute('data-key');
  btn.addEventListener('pointerdown', (e) => {
    e.preventDefault();
    if (k === 'w' && k_g === 0) return;
    if (k === 'a' && k_t === 0) return;
    if (k === 'd' && k_p === 0) return;
    if (k === 'q' && (k_g === 0 || k_t === 0)) return;
    if (k === 'e' && (k_g === 0 || k_p === 0)) return;
    btn.classList.add('active');
    sendKey(k);
  });
  btn.addEventListener('pointerup', (e) => {
    e.preventDefault();
    btn.classList.remove('active');
    const isHold = document.getElementById('holdToggle').checked;
    if (isHold && k !== 'f') sendKey('f');
  });
});

// Điều khiển bàn phím Laptop
const keyMap = {'KeyW':'w','KeyS':'s','KeyA':'a','KeyD':'d','KeyQ':'q','KeyE':'e','KeyZ':'z','KeyC':'c','KeyF':'f','Space':'f'};
window.addEventListener('keydown', (e) => {
  if (keyMap[e.code]) sendKey(keyMap[e.code]);
});
window.addEventListener('keyup', (e) => {
  const isHold = document.getElementById('holdToggle').checked;
  if (isHold && keyMap[e.code] && keyMap[e.code] !== 'f') sendKey('f');
});

function updateBar(val, prefix, boxId) {
  const distEl = document.getElementById('dist_' + prefix);
  const barEl = document.getElementById('bar_' + prefix);
  const box = document.getElementById(boxId);
  if (val === null || val < 0) {
    distEl.innerText = '> 100';
    barEl.style.width = '100%';
    barEl.style.background = 'var(--safe)';
    box.classList.remove('locked');
  } else {
    distEl.innerText = val.toFixed(1);
    const pct = Math.min(100, Math.max(5, (val / 80) * 100));
    barEl.style.width = pct + '%';
    if (val < 15) {
      barEl.style.background = 'var(--danger)';
      box.classList.add('locked');
    } else if (val < 25) {
      barEl.style.background = 'var(--warning)';
      box.classList.remove('locked');
    } else {
      barEl.style.background = 'var(--safe)';
      box.classList.remove('locked');
    }
  }
}

// Cập nhật cảm biến định kỳ mỗi 250ms
setInterval(() => {
  fetch('/sensor')
    .then(r => r.json())
    .then(data => {
      k_g = data.kg; k_p = data.kp; k_t = data.kt;
      updateBar(data.g, 'g', 'box_giua');
      updateBar(data.p, 'p', 'box_phai');
      updateBar(data.t, 't', 'box_trai');

      if (data.enc) {
        document.getElementById('enc1').innerText = data.enc[0];
        document.getElementById('enc2').innerText = data.enc[1];
        document.getElementById('enc3').innerText = data.enc[2];
        document.getElementById('enc4').innerText = data.enc[3];
      }

      document.getElementById('btn_w').classList.toggle('locked-btn', k_g === 0);
      document.getElementById('btn_a').classList.toggle('locked-btn', k_t === 0);
      document.getElementById('btn_d').classList.toggle('locked-btn', k_p === 0);
      document.getElementById('btn_q').classList.toggle('locked-btn', k_g === 0 || k_t === 0);
      document.getElementById('btn_e').classList.toggle('locked-btn', k_g === 0 || k_p === 0);
    })
    .catch(()=>{});
}, 250);
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------
# 9. PHỤC VỤ HTTP
# ---------------------------------------------------------------------
def gui_phan_hoi(client, noi_dung, kieu_noi_dung="text/html; charset=utf-8", ma_loi="200 OK"):
    du_lieu = noi_dung.encode("utf-8") if isinstance(noi_dung, str) else noi_dung
    dau_trang = (
        "HTTP/1.1 %s\r\nContent-Type: %s\r\nContent-Length: %d\r\nConnection: close\r\nAccess-Control-Allow-Origin: *\r\n\r\n"
    ) % (ma_loi, kieu_noi_dung, len(du_lieu))
    client.sendall(dau_trang.encode("utf-8"))
    chunk = 1024
    for i in range(0, len(du_lieu), chunk):
        client.sendall(du_lieu[i:i + chunk])


# ---------------------------------------------------------------------
# 10. VÒNG LẶP CHÍNH
# ---------------------------------------------------------------------
def main():
    global tocdo, lenh_dang_chay

    print("=" * 60)
    print("  KHỞI ĐỘNG XE MECANUM ESP32 - BẢN QUAY VIDEO NỘP BÀI")
    print("  - Điều khiển 8 hướng Mecanum + Xoay tại chỗ")
    print("  - 3 Siêu âm HC-SR04 tự phanh bảo vệ an toàn")
    print("  - 4 Encoder đếm xung thời gian thực")
    print("=" * 60)

    dung()
    esp_ip = bat_wifi()

    # Socket Web Server
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('', 80))
    s.listen(4)
    s.settimeout(0.02)

    # Đọc phím bàn phím Shell Thonny
    poll = uselect.poll()
    poll.register(sys.stdin, uselect.POLLIN)

    last_sensor_time = time.ticks_ms()
    loop_cnt = 0
    dem_in = 0

    try:
        while True:
            loop_cnt += 1
            now = time.ticks_ms()

            # (A) ĐỌC 3 SIÊU ÂM ĐỊNH KỲ MỖI 80ms
            if time.ticks_diff(now, last_sensor_time) > 80:
                last_sensor_time = now
                doc_3_cam_bien()

                # Tự phanh dừng nếu phát hiện vật cản sát nút
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
                    print("[XE] Siêu âm -> T:%5s | G:%5s | P:%5s cm | Xung: %s | Lệnh: %s" % (
                        t_str, g_str, p_str, str(enc_cnt), lenh_dang_chay
                    ))

            # (B) ĐỌC LỆNH TỪ BÀN PHÍM SHELL THONNY
            if poll.poll(0):
                phim = sys.stdin.read(1)
                if phim:
                    phim = phim.lower()
                    if phim == "r":
                        for i in range(4): enc_cnt[i] = 0
                        print(">>> ĐÃ RESET ENCODER VỀ 0 <<<")
                    elif phim in "wsadqezcf":
                        if phim == "w" and not khoa_giua: dung()
                        elif phim == "a" and not khoa_trai: dung()
                        elif phim == "d" and not khoa_phai: dung()
                        elif phim == "q" and (not khoa_giua or not khoa_trai): dung()
                        elif phim == "e" and (not khoa_giua or not khoa_phai): dung()
                        else: thuc_hien_lenh(phim, tocdo)

            # (C) TIẾP NHẬN YÊU CẦU TỪ WEB TRÊN ĐIỆN THOẠI
            try:
                client, addr = s.accept()
            except OSError:
                client = None

            if client:
                try:
                    client.settimeout(1.0)
                    yeu_cau = client.recv(1024)
                    if yeu_cau:
                        dong_dau = yeu_cau.decode("utf-8", "ignore").split("\r\n")[0]
                        cac_phan = dong_dau.split(" ")
                        duong_dan = cac_phan[1] if len(cac_phan) > 1 else "/"

                        if duong_dan == "/" or duong_dan.startswith("/index"):
                            gui_phan_hoi(client, HTML_PAGE)

                        elif duong_dan.startswith("/sensor"):
                            g_s = ("%.1f" % kc_giua) if kc_giua is not None else "null"
                            p_s = ("%.1f" % kc_phai) if kc_phai is not None else "null"
                            t_s = ("%.1f" % kc_trai) if kc_trai is not None else "null"
                            json_str = '{"g":%s,"p":%s,"t":%s,"kg":%d,"kp":%d,"kt":%d,"enc":[%d,%d,%d,%d]}' % (
                                g_s, p_s, t_s, khoa_giua, khoa_phai, khoa_trai,
                                enc_cnt[0], enc_cnt[1], enc_cnt[2], enc_cnt[3]
                            )
                            gui_phan_hoi(client, json_str, kieu_noi_dung="application/json")

                        elif duong_dan.startswith("/reset_enc"):
                            for i in range(4): enc_cnt[i] = 0
                            gui_phan_hoi(client, '{"status":"ok"}', kieu_noi_dung="application/json")

                        elif duong_dan.startswith("/cmd"):
                            query = duong_dan.split("?")[1] if "?" in duong_dan else ""
                            params = dict(p.split("=") for p in query.split("&") if "=" in p)
                            key = params.get("key", "")
                            if key:
                                if key == "f":
                                    dung()
                                elif key == "w" and not khoa_giua: dung()
                                elif key == "a" and not khoa_trai: dung()
                                elif key == "d" and not khoa_phai: dung()
                                elif key == "q" and (not khoa_giua or not khoa_trai): dung()
                                elif key == "e" and (not khoa_giua or not khoa_phai): dung()
                                else:
                                    thuc_hien_lenh(key, tocdo)
                            gui_phan_hoi(client, '{"status":"ok"}', kieu_noi_dung="application/json")

                        elif duong_dan.startswith("/speed"):
                            query = duong_dan.split("?")[1] if "?" in duong_dan else ""
                            params = dict(p.split("=") for p in query.split("&") if "=" in p)
                            val = params.get("val", "")
                            if val:
                                try:
                                    tocdo = int(val)
                                    if lenh_dang_chay != "f":
                                        toc_do(tocdo, tocdo)
                                except ValueError:
                                    pass
                            gui_phan_hoi(client, '{"status":"ok"}', kieu_noi_dung="application/json")

                        else:
                            gui_phan_hoi(client, "404 Not Found", ma_loi="404 Not Found")
                except Exception:
                    pass
                finally:
                    try:
                        client.close()
                    except Exception:
                        pass

            if loop_cnt % 50 == 0:
                gc.collect()

    except KeyboardInterrupt:
        print("\n[STOP] Đã dừng chương trình an toàn...")
    finally:
        dung()
        s.close()
        print("[XONG] Đã ngắt động cơ và đóng Web Server an toàn!")


if __name__ == "__main__":
    main()
