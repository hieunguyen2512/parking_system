"""
Test nhận diện biển số xe + mở barrier

Flow: Cảm biến (hoặc phím SPACE) -> Chụp ảnh -> Nhận diện biển số -> So khớp DB -> Mở barrier

Phím tắt:
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
CAM_INDEX        = 1          # 0 = webcam máy tính, 1 = USB webcam ngoài
ARDUINO_PORT     = "COM6"
BAUD_RATE        = 9600
DEBOUNCE_SEC     = 3.0        # giây giữa 2 lần nhận diện liên tiếp
BARRIER_OPEN_SEC = 4.0        # giây rồi tự đóng barrier
AUTO_TRIGGER_SEC = 10.0       # tự động trigger mỗi N giây (0 = tắt)

# Override đường dẫn model biển số sang best.pt ở gốc dự án
PLATE_MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "best.pt")
config.PLATE_MODEL_PATH = os.path.abspath(PLATE_MODEL_PATH)

# Dùng KEEP mode để preview mượt
config.CAPTURE_MODE = "KEEP"

# ─── Kết nối backend ────────────────────────────────────────────────────────
BACKEND_URL      = config.BACKEND_URL          # mặc định http://localhost:4000
HARDWARE_API_KEY = os.getenv("HARDWARE_API_KEY", "parking_hw_secret_change_this")
PLATES_RELOAD_SEC = 30.0   # reload danh sách biển số mỗi 30 giây

# ─── State toàn cục ──────────────────────────────────────────────────────────
status_text    = "Dang khoi dong model..."
status_color   = (0, 220, 220)
recognizer     = None
arduino_ser    = None
last_trigger   = 0.0
last_plate     = ""
last_ocr_raw   = ""    # OCR text thô chưa xử lý
last_roi_img   = None  # numpy array ảnh crop biển số
allowed_plates = {}   # dict: plate -> full_name
allowed_lock   = threading.Lock()


# ─── Fetch danh sách biển số từ backend ─────────────────────────────────────
def fetch_plates():
    global allowed_plates
    try:
        import urllib.request, json as _json
        req = urllib.request.Request(
            f"{BACKEND_URL}/api/hardware/registered-plates",
            headers={"x-hardware-key": HARDWARE_API_KEY},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = _json.loads(resp.read())
        new_dict = {row["license_plate"]: row["full_name"] for row in data}
        with allowed_lock:
            allowed_plates.update(new_dict)
            # xóa biển không còn trong DB
            for k in list(allowed_plates):
                if k not in new_dict:
                    del allowed_plates[k]
        print(f"[DB] Tai {len(new_dict)} bien so hop le tu backend")
    except Exception as e:
        print(f"[DB] Khong lay duoc danh sach bien so: {e}")

def plates_reload_loop():
    while True:
        fetch_plates()
        time.sleep(PLATES_RELOAD_SEC)


# ─── Load model ──────────────────────────────────────────────────────────────
def load_models():
    global recognizer, status_text, status_color
    from plate_recognizer import PlateRecognizer
    recognizer = PlateRecognizer.get()
    if recognizer._ready:
        status_text  = "San sang   [SPACE] nhan dien bien so"
        status_color = (0, 255, 0)
        print(f"[Model] Plate model OK: {config.PLATE_MODEL_PATH}")
    else:
        status_text  = "LOI: Plate model chua san sang"
        status_color = (0, 0, 255)
        print("[Model] LOI: plate model chua ready")


# ─── Arduino ─────────────────────────────────────────────────────────────────
trigger_event = threading.Event()

def try_connect_arduino():
    global arduino_ser
    try:
        import serial
    except ImportError:
        print("[Arduino] pyserial chua cai. Dung phim SPACE de gia lap.")
        return
    for attempt in range(3):
        try:
            arduino_ser = serial.Serial(ARDUINO_PORT, BAUD_RATE, timeout=0.1)
            time.sleep(2)
            arduino_ser.reset_input_buffer()
            print(f"[Arduino] Ket noi {ARDUINO_PORT} thanh cong")
            return
        except Exception as e:
            print(f"[Arduino] Lan {attempt+1}: {e}")
            time.sleep(1)
    print(f"[Arduino] Khong ket noi duoc {ARDUINO_PORT} sau 3 lan")
    print("[Arduino] Dung phim SPACE de gia lap cam bien")
    arduino_ser = None

def auto_trigger_loop():
    """Tự động trigger nhận diện mỗi AUTO_TRIGGER_SEC giây."""
    if AUTO_TRIGGER_SEC <= 0:
        return
    time.sleep(AUTO_TRIGGER_SEC)
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
    global status_text, status_color, last_plate, last_ocr_raw, last_roi_img

    if not recognizer or not recognizer._ready:
        status_text  = "LOI: Model chua san sang"
        status_color = (0, 0, 255)
        return

    status_text  = "Dang nhan dien bien so..."
    status_color = (0, 220, 220)

    _, buf     = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
    img_bytes  = buf.tobytes()

    t0     = time.time()
    result = recognizer.recognize(img_bytes)
    ms     = int((time.time() - t0) * 1000)

    plate   = result.get("plate", "")
    conf    = result.get("confidence", 0.0)
    ocr_raw = result.get("ocr_raw", "")
    roi_bytes = result.get("roi_image", None)

    # Hiển thị ảnh ROI crop
    if roi_bytes:
        roi_arr = cv2.imdecode(np.frombuffer(roi_bytes, np.uint8), cv2.IMREAD_COLOR)
        if roi_arr is not None:
            # Phóng to ảnh ROI để dễ nhìn
            roi_show = cv2.resize(roi_arr, (400, 120), interpolation=cv2.INTER_CUBIC)
            last_roi_img = roi_show
            cv2.imshow("ROI - Bien so crop", roi_show)
            cv2.waitKey(1)

    if not plate:
        print(f"[--] Khong phat hien bien so  ocr='{ocr_raw}'  {ms}ms")
        status_text  = f"Khong phat hien bien so  {ms}ms"
        status_color = (0, 60, 255)
        return

    last_plate   = plate
    last_ocr_raw = ocr_raw
    print(f"[OCR] raw='{ocr_raw}'  ->  plate='{plate}'  conf={conf:.3f}  {ms}ms")

    # Kiểm tra whitelist lấy từ DB
    with allowed_lock:
        owner = allowed_plates.get(plate)

    if owner is not None:
        print(f"[OK] Bien so: {plate}  chu xe: {owner}  conf={conf:.3f}  {ms}ms -> MO BARRIER")
        status_text  = f"OK: {plate} ({owner})  conf={conf:.2f} -> MO BARRIER"
        status_color = (0, 255, 0)
        send_barrier("OPEN")
        threading.Timer(BARRIER_OPEN_SEC, lambda: send_barrier("CLOSE")).start()
    else:
        print(f"[XX] Bien so CHUA DANG KY: {plate}  conf={conf:.3f}  {ms}ms")
        status_text  = f"TU CHOI: {plate}  conf={conf:.2f}  {ms}ms  (chua dang ky)"
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
def draw_ui(frame: np.ndarray) -> np.ndarray:
    h, w = frame.shape[:2]
    out  = frame.copy()

    # Khung nhắc vùng biển số (hình chữ nhật ngang)
    cx, cy = w // 2, h // 2
    bw, bh = w // 3, h // 8
    cv2.rectangle(out, (cx - bw, cy - bh), (cx + bw, cy + bh),
                  (80, 200, 255), 2, cv2.LINE_AA)
    cv2.putText(out, "Dat bien so vao day", (cx - 90, cy - bh - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (80, 200, 255), 1, cv2.LINE_AA)

    # Header
    cv2.rectangle(out, (0, 0), (w, 38), (20, 20, 20), -1)
    with allowed_lock:
        n_plates = len(allowed_plates)
    top = f"[SPACE] Nhan dien  [Q] Thoat   Auto: {AUTO_TRIGGER_SEC:.0f}s   DB: {n_plates} bien so"
    cv2.putText(out, top, (8, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (200, 200, 200), 1)

    # Arduino status
    ard_txt   = f"Arduino: {ARDUINO_PORT} {'OK' if arduino_ser else 'KHONG KET NOI'}"
    ard_color = (0, 255, 0) if arduino_ser else (60, 60, 255)
    cv2.putText(out, ard_txt, (w - 300, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.48, ard_color, 1)

    # Biển số vừa nhận diện + OCR raw
    if last_plate:
        cv2.putText(out, last_plate, (cx - 80, cy + bh + 32),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 220, 255), 2, cv2.LINE_AA)
    if last_ocr_raw:
        cv2.putText(out, f"OCR: {last_ocr_raw}", (8, h - 58),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, (180, 180, 100), 1, cv2.LINE_AA)

    # Status bar bottom
    cv2.rectangle(out, (0, h - 50), (w, h), (20, 20, 20), -1)
    cv2.putText(out, status_text, (10, h - 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.62, status_color, 2, cv2.LINE_AA)
    return out


# ─── Main ────────────────────────────────────────────────────────────────────
def main():
    # Load model ngầm
    threading.Thread(target=load_models, daemon=True).start()

    # Load danh sách biển số từ backend (reload định kỳ)
    threading.Thread(target=plates_reload_loop, daemon=True).start()

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

        display = draw_ui(frame)
        cv2.imshow("Plate Gate Test", display)

        key = cv2.waitKey(1) & 0xFF

        if key in (ord('q'), 27):    # Q / ESC
            break

        elif key == ord(' '):
            print("[SPACE] Manual trigger")
            trigger_recognition(frame)

    cap.release()
    cv2.destroyAllWindows()
    print("[EXIT] Da thoat.")


if __name__ == "__main__":
    main()
