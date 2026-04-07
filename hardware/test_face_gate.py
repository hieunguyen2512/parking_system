"""
Test nhận diện khuôn mặt + mở barrier

Flow: Cảm biến (hoặc phím SPACE) -> Chụp ảnh -> Nhận diện mặt -> Mở barrier

Phím tắt:
  R     - Chụp và đăng ký khuôn mặt hiện tại (dùng để test)
  SPACE - Trigger nhận diện thủ công (giả lập cảm biến)
  Q/ESC - Thoát

Nếu Arduino COM6 kết nối: tự nhận SENSOR:DETECTED để trigger
"""

import sys, os, time, threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "ai_service"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "ai_service", "modules"))

import cv2
import numpy as np
import config

# ─── Cấu hình test ───────────────────────────────────────────────────────────
CAM_INDEX     = 1          # 0 = webcam máy tính, 1 = USB webcam ngoài
ARDUINO_PORT  = "COM6"
BAUD_RATE     = 9600
TEST_USER_ID  = "dce2fc0d-dfc1-4098-b67e-cb8790951c07"  # Luong Minh Hieu
DEBOUNCE_SEC  = 3.0               # giây giữa 2 lần nhận diện liên tiếp
BARRIER_OPEN_SEC = 4.0            # giây rồi tự đóng barrier
AUTO_TRIGGER_SEC = 10.0           # tự động trigger mỗi N giây (0 = tắt)

# Đảm bảo dùng KEEP mode để preview mượt
config.CAPTURE_MODE = "KEEP"

# Thư mục lưu ảnh đăng ký test
REGISTER_DIR = os.path.join(config.FACES_DIR, TEST_USER_ID)
os.makedirs(REGISTER_DIR, exist_ok=True)

# ─── State toàn cục ───────────────────────────────────────────────────────────
status_text   = "Dang khoi dong model..."
status_color  = (0, 220, 220)
recognizer    = None
arduino_ser   = None
last_trigger  = 0.0          # thời điểm trigger cuối


# ─── Load model ──────────────────────────────────────────────────────────────
def load_models():
    global recognizer, status_text, status_color
    from face_recognizer import FaceRecognizer
    recognizer = FaceRecognizer.get()
    if recognizer._ready:
        n = recognizer.reload_known_faces()
        status_text  = f"San sang   {n} user da dang ky    [R] dang ky  [SPACE] nhan dien"
        status_color = (0, 255, 0)
        print(f"[Model] Face model OK, {n} user da load")
    else:
        status_text  = "LOI: Face model chua san sang"
        status_color = (0, 0, 255)
        print("[Model] LOI: face model chua ready")


# ─── Arduino ─────────────────────────────────────────────────────────────────
trigger_event = threading.Event()

def try_connect_arduino():
    global arduino_ser
    import serial
    for attempt in range(3):
        try:
            arduino_ser = serial.Serial(ARDUINO_PORT, BAUD_RATE, timeout=0.1)
            time.sleep(2)
            arduino_ser.reset_input_buffer()
            print(f"[Arduino] Ket noi {ARDUINO_PORT} thanh cong")
            return
        except serial.SerialException as e:
            print(f"[Arduino] Lan {attempt+1}: {e}")
            time.sleep(1)
    print(f"[Arduino] Khong ket noi duoc {ARDUINO_PORT} sau 3 lan")
    print("[Arduino] Dung phim SPACE de gia lap cam bien")
    arduino_ser = None

def auto_trigger_loop():
    """Tự động trigger nhận diện mỗi AUTO_TRIGGER_SEC giây."""
    if AUTO_TRIGGER_SEC <= 0:
        return
    time.sleep(AUTO_TRIGGER_SEC)   # chờ lần đầu để model kịp load
    while True:
        print(f"[AUTO] Tu dong trigger sau {AUTO_TRIGGER_SEC:.0f}s")
        trigger_event.set()
        time.sleep(AUTO_TRIGGER_SEC)


def arduino_listener():
    """Đọc serial từ Arduino, trigger khi SENSOR:DETECTED."""
    while True:
        if arduino_ser and arduino_ser.is_open:
            try:
                line = arduino_ser.readline().decode("utf-8", errors="ignore").strip()
                if line == "SENSOR:DETECTED":
                    print("[Arduino] SENSOR:DETECTED")
                    trigger_event.set()
                elif line:
                    print(f"[Arduino] {line}")
            except Exception:
                pass
        time.sleep(0.03)

def send_barrier(cmd: str):
    """Gửi OPEN hoặc CLOSE tới Arduino."""
    if arduino_ser and arduino_ser.is_open:
        arduino_ser.write(f"{cmd}\n".encode())
        print(f"[Arduino] >> {cmd}")
    else:
        print(f"[SIM] {cmd} BARRIER (Arduino chua ket noi)")


# ─── Nhận diện ───────────────────────────────────────────────────────────────
def run_recognition(frame: np.ndarray):
    global status_text, status_color

    if not recognizer or not recognizer._ready:
        status_text  = "LOI: Model chua san sang"
        status_color = (0, 0, 255)
        return

    status_text  = "Dang nhan dien..."
    status_color = (0, 220, 220)

    _, buf     = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
    img_bytes  = buf.tobytes()

    t0     = time.time()
    result = recognizer.recognize(img_bytes)
    ms     = int((time.time() - t0) * 1000)

    if result["matched"]:
        uid  = result["user_id"]
        conf = result["confidence"]
        print(f"[OK] Nhan dien: {uid}  conf={conf:.3f}  {ms}ms -> MO BARRIER")
        status_text  = f"OK: {uid[:16]}  conf={conf:.2f}  {ms}ms  -> MO BARRIER"
        status_color = (0, 255, 0)
        send_barrier("OPEN")
        threading.Timer(BARRIER_OPEN_SEC, lambda: send_barrier("CLOSE")).start()
    else:
        conf = result["confidence"]
        print(f"[--] Khong nhan ra  conf={conf:.3f}  {ms}ms")
        status_text  = f"Khong nhan ra  conf={conf:.2f}  {ms}ms"
        status_color = (0, 60, 255)


def trigger_recognition(frame: np.ndarray):
    global last_trigger
    now = time.time()
    if now - last_trigger < DEBOUNCE_SEC:
        remaining = DEBOUNCE_SEC - (now - last_trigger)
        print(f"[Debounce] Bo qua, cho them {remaining:.1f}s")
        return
    last_trigger = now
    threading.Thread(target=run_recognition, args=(frame.copy(),), daemon=True).start()


# ─── Vẽ UI ───────────────────────────────────────────────────────────────────
def draw_ui(frame: np.ndarray, reg_count: int) -> np.ndarray:
    h, w = frame.shape[:2]
    out  = frame.copy()

    # Khung nhắc vùng khuôn mặt
    cx, cy   = w // 2, h // 2
    half     = min(w, h) // 3
    cv2.rectangle(out, (cx - half, cy - half), (cx + half, cy + half),
                  (80, 255, 120), 2, cv2.LINE_AA)
    cv2.putText(out, "Dat khuon mat vao day", (cx - 110, cy - half - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (80, 255, 120), 1, cv2.LINE_AA)

    # Header
    cv2.rectangle(out, (0, 0), (w, 38), (20, 20, 20), -1)
    top = f"[R] Dang ky mat  [SPACE] Nhan dien  [Q] Thoat   Auto: {AUTO_TRIGGER_SEC:.0f}s   Registered: {reg_count}"
    cv2.putText(out, top, (8, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (200, 200, 200), 1)

    # Arduino status
    ard_txt   = f"Arduino: {ARDUINO_PORT} {'OK' if arduino_ser else 'KHONG KET NOI'}"
    ard_color = (0, 255, 0) if arduino_ser else (60, 60, 255)
    cv2.putText(out, ard_txt, (w - 300, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.48, ard_color, 1)

    # Status bar bottom
    cv2.rectangle(out, (0, h - 50), (w, h), (20, 20, 20), -1)
    cv2.putText(out, status_text, (10, h - 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.62, status_color, 2, cv2.LINE_AA)
    return out


# ─── Main ────────────────────────────────────────────────────────────────────
def main():
    # Load model ngầm
    threading.Thread(target=load_models, daemon=True).start()

    # Kết nối Arduino
    try_connect_arduino()
    if arduino_ser:
        threading.Thread(target=arduino_listener, daemon=True).start()

    # Auto trigger liên tục
    threading.Thread(target=auto_trigger_loop, daemon=True).start()

    # Mở camera
    print(f"[CAM] Mo camera {CAM_INDEX}...")
    cap = cv2.VideoCapture(CAM_INDEX, cv2.CAP_MSMF)
    if not cap.isOpened():
        cap = cv2.VideoCapture(CAM_INDEX, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("[LOI] Khong mo duoc camera! Kiem tra lai ket noi.")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    print("[CAM] Camera mo thanh cong.")

    frame = None
    while True:
        ret, raw = cap.read()
        if ret:
            frame = raw

        if frame is None:
            continue

        # Trigger từ Arduino sensor
        if trigger_event.is_set():
            trigger_event.clear()
            trigger_recognition(frame)

        reg_count = len([f for f in os.listdir(REGISTER_DIR)
                         if f.lower().endswith(('.jpg', '.png'))]) \
                    if os.path.exists(REGISTER_DIR) else 0

        display = draw_ui(frame, reg_count)
        cv2.imshow("Face Gate Test", display)

        key = cv2.waitKey(1) & 0xFF

        if key in (ord('q'), 27):    # Q / ESC
            break

        elif key in (ord('r'), ord('R')):
            # Đăng ký khuôn mặt
            fpath = os.path.join(REGISTER_DIR, f"face_{int(time.time())}.jpg")
            cv2.imwrite(fpath, frame)
            print(f"[REG] Da luu anh: {fpath}")

            def reload_after_reg():
                global status_text, status_color
                if recognizer and recognizer._ready:
                    n = recognizer.reload_known_faces()
                    status_text  = f"Da dang ky! Tong {n} user  [SPACE] de test nhan dien"
                    status_color = (0, 220, 255)
                    print(f"[REG] Reload OK: {n} user")
            threading.Thread(target=reload_after_reg, daemon=True).start()

        elif key == ord(' '):
            # Trigger thủ công
            print("[SPACE] Manual trigger")
            trigger_recognition(frame)

    cap.release()
    cv2.destroyAllWindows()
    print("[EXIT] Da thoat.")


if __name__ == "__main__":
    main()
