"""
test_dual_gate.py – Nhận diện ĐỒNG THỜI biển số + khuôn mặt với 2 webcam

Logic mở barrier (XÁC THỰC ĐÔI – Dual Auth):
  ✓ Biển số nhận diện được  +  có trong database
  ✓ Khuôn mặt nhận diện được  +  có trong database
  ✓ Cả hai CÙNG thuộc về MỘT USER

=> Chỉ mở barrier khi đủ cả 3 điều kiện trên.

Phím tắt:
  SPACE    – trigger nhận diện thủ công (giả lập cảm biến)
  Q / ESC  – thoát

Cấu hình webcam (env hoặc trực tiếp ở dưới):
  PLATE_CAM=0   – camera quay vào BIỂN SỐ
  FACE_CAM=1    – camera quay vào KHUÔN MẶT
  ARDUINO_PORT=COM6
"""

import sys, os, time, threading, concurrent.futures, uuid
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "ai_service"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "ai_service", "modules"))

import cv2
import numpy as np
import config

# ══════════════════════════════════════════════════════════════════════════════
# CẤU HÌNH – thay đổi ở đây hoặc dùng biến môi trường
# ══════════════════════════════════════════════════════════════════════════════
PLATE_CAM_INDEX  = int(os.getenv("PLATE_CAM",     "1"))    # USB webcam thứ 2 – biển số
FACE_CAM_INDEX   = int(os.getenv("FACE_CAM",      "0"))    # USB webcam thứ 1 – khuôn mặt
ARDUINO_PORT     = os.getenv("ARDUINO_PORT",      "COM6")
BAUD_RATE        = 9600
DEBOUNCE_SEC          = 5.0     # giây khóa sau khi mở barrier (tránh mở liên tục)
BARRIER_OPEN_SEC      = 4.0     # giây tự đóng barrier
PREVIEW_W             = 640
PREVIEW_H             = 480

# ── Chế độ cảm biến: chờ SENSOR:DETECTED / SPACE → nhận diện trong cửa sổ ────
AUTO_DETECT           = False   # False = chờ cảm biến / phím SPACE
SENSOR_WINDOW_SEC     = 8.0     # giây thử nhận diện sau khi cảm biến kích hoạt
DETECT_INTERVAL_SEC   = 0.3     # giây giữa mỗi lần thử trong cửa sổ
PLATE_MIN_CONF        = 0.45    # ngưỡng confidence biển số
FACE_SCAN_AFTER_PLATE = True    # (dự phòng cho auto_detect_loop nếu bật lại)

# Override đường dẫn plate model sang best.pt ở gốc dự án
_this_dir        = os.path.dirname(os.path.abspath(__file__))
config.PLATE_MODEL_PATH = os.path.abspath(os.path.join(_this_dir, "..", "best.pt"))

# Camera giữ mở liên tục để preview + capture realtime
config.CAPTURE_MODE = "KEEP"

# Backend
BACKEND_URL      = config.BACKEND_URL
HARDWARE_API_KEY = os.getenv("HARDWARE_API_KEY", "parking_hw_secret_change_this")
DB_RELOAD_SEC    = 30.0         # reload danh sách DB mỗi 30 giây

# Thư mục lưu ảnh chụp
CAPTURES_DIR = config.CAPTURES_DIR
os.makedirs(CAPTURES_DIR, exist_ok=True)

# ══════════════════════════════════════════════════════════════════════════════
# STATE TOÀN CỤC
# ══════════════════════════════════════════════════════════════════════════════
status_text   = "Dang khoi dong..."
status_color  = (0, 220, 220)
plate_ai      = None
face_ai       = None
arduino_ser   = None
last_trigger  = 0.0

# Bộ nhớ đệm danh sách xe đã đăng ký: plate → {user_id, full_name}
allowed_vehicles: dict[str, dict] = {}
allowed_lock = threading.Lock()

# Camera objects + lock riêng cho từng cam
cap_plate = None
cap_face  = None
lock_plate = threading.Lock()
lock_face  = threading.Lock()

# Khóa xử lý (tránh nhận diện chồng chéo)
processing_lock = threading.Lock()

# Event từ Arduino hoặc phím SPACE
trigger_event = threading.Event()

# Flag: đang trong thời gian barrier mở (không trigger lại)
barrier_active   = False
last_barrier_end = 0.0          # epoch time khi barrier đóng lần cuối


# ══════════════════════════════════════════════════════════════════════════════
# DB – FETCH DANH SÁCH XE ĐÃ ĐĂNG KÝ
# ══════════════════════════════════════════════════════════════════════════════
def fetch_allowed_vehicles():
    """Tải danh sách biển số + user_id từ backend về bộ đệm cục bộ."""
    import urllib.request, json as _json
    try:
        req = urllib.request.Request(
            f"{BACKEND_URL}/api/hardware/registered-plates",
            headers={"x-hardware-key": HARDWARE_API_KEY},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            rows = _json.loads(resp.read())
        new_dict = {
            r["license_plate"]: {"user_id": r["user_id"], "full_name": r["full_name"]}
            for r in rows
        }
        with allowed_lock:
            allowed_vehicles.clear()
            allowed_vehicles.update(new_dict)
        print(f"[DB] Tai {len(new_dict)} bien so da dang ky")
    except Exception as e:
        print(f"[DB] Loi tai danh sach bien so: {e}")


def db_reload_loop():
    while True:
        fetch_allowed_vehicles()
        time.sleep(DB_RELOAD_SEC)


# ══════════════════════════════════════════════════════════════════════════════
# LOAD AI MODELS
# ══════════════════════════════════════════════════════════════════════════════
def load_models():
    global plate_ai, face_ai, status_text, status_color
    try:
        from plate_recognizer import PlateRecognizer
        from face_recognizer  import FaceRecognizer

        plate_ai = PlateRecognizer.get()
        face_ai  = FaceRecognizer.get()

        if face_ai._ready:
            n = face_ai.reload_known_faces()
            print(f"[Model] Face model OK – {n} user da dang ky")
        else:
            print("[Model] CANH BAO: Face model chua san sang (kiem tra MODELS_DIR)")

        if plate_ai._ready:
            print(f"[Model] Plate model OK: {config.PLATE_MODEL_PATH}")
        else:
            print("[Model] CANH BAO: Plate model chua san sang (kiem tra best.pt)")

        if plate_ai._ready and face_ai._ready:
            status_text  = "San sang – cho cam bien hoac nhan SPACE"
            status_color = (0, 255, 0)
        elif plate_ai._ready or face_ai._ready:
            which = "Face" if not face_ai._ready else "Plate"
            status_text  = f"CANH BAO: {which} model chua san sang"
            status_color = (0, 165, 255)
        else:
            status_text  = "LOI: Ca 2 model deu chua san sang"
            status_color = (0, 0, 255)
    except Exception as e:
        status_text  = f"LOI load model: {e}"
        status_color = (0, 0, 255)
        print(f"[Model] LOI: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# ARDUINO
# ══════════════════════════════════════════════════════════════════════════════
def try_connect_arduino():
    global arduino_ser
    try:
        import serial
    except ImportError:
        print("[Arduino] pyserial chua cai – dung SPACE de gia lap cam bien")
        return
    for attempt in range(3):
        try:
            arduino_ser = serial.Serial(ARDUINO_PORT, BAUD_RATE, timeout=0.1)
            time.sleep(2)
            arduino_ser.reset_input_buffer()
            print(f"[Arduino] Ket noi {ARDUINO_PORT} thanh cong")
            return
        except Exception as e:
            print(f"[Arduino] Lan {attempt + 1}: {e}")
            time.sleep(1)
    print(f"[Arduino] Khong ket noi duoc {ARDUINO_PORT} – dung SPACE de gia lap")
    arduino_ser = None


def arduino_listener():
    """Lắng nghe SENSOR:DETECTED từ Arduino."""
    while True:
        if arduino_ser and arduino_ser.is_open:
            try:
                line = arduino_ser.readline().decode("utf-8", errors="ignore").strip()
                if line == "SENSOR:DETECTED":
                    print("[Arduino] SENSOR:DETECTED – kich hoat nhan dien")
                    trigger_event.set()
                elif line:
                    print(f"[Arduino] {line}")
            except Exception:
                pass
        time.sleep(0.03)


def send_barrier(cmd: str):
    """Gửi OPEN hoặc CLOSE tới Arduino Serial."""
    if arduino_ser and arduino_ser.is_open:
        arduino_ser.write(f"{cmd}\n".encode())
        print(f"[Arduino] >> {cmd}")
    else:
        print(f"[SIM]     >> {cmd} BARRIER  (Arduino chua ket noi)")


# ══════════════════════════════════════════════════════════════════════════════
# CAMERA HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def _open_cam(idx: int) -> cv2.VideoCapture | None:
    for backend, name in [(cv2.CAP_MSMF, "MSMF"), (cv2.CAP_DSHOW, "DSHOW")]:
        cap = cv2.VideoCapture(idx, backend)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH,  PREVIEW_W)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, PREVIEW_H)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            print(f"[Cam {idx}] Mo thanh cong [{name}]  {w}x{h}")
            return cap
        cap.release()
    print(f"[Cam {idx}] KHONG MO DUOC")
    return None


def open_cameras():
    global cap_plate, cap_face
    cap_plate = _open_cam(PLATE_CAM_INDEX)
    cap_face  = _open_cam(FACE_CAM_INDEX)
    # Warmup frames
    for _ in range(8):
        if cap_plate: cap_plate.grab()
        if cap_face:  cap_face.grab()
    time.sleep(0.15)


def _read_frame(cap: cv2.VideoCapture, lock: threading.Lock) -> np.ndarray | None:
    """Đọc frame mới nhất từ camera (thread-safe)."""
    with lock:
        cap.grab()          # flush buffer
        ret, frame = cap.read()
        return frame if ret else None


def _capture_to_bytes(cap: cv2.VideoCapture, lock: threading.Lock) -> bytes | None:
    """Chụp 1 frame → JPEG bytes."""
    frame = _read_frame(cap, lock)
    if frame is None:
        return None
    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return buf.tobytes()


def _save_capture(img_bytes: bytes, prefix: str) -> str:
    """Lưu ảnh vào CAPTURES_DIR, trả về đường dẫn tương đối (captures/…)."""
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    uid  = uuid.uuid4().hex[:6]
    name = f"{prefix}_{ts}_{uid}.jpg"
    path = os.path.join(CAPTURES_DIR, name)
    with open(path, "wb") as f:
        f.write(img_bytes)
    return f"captures/{name}"


# ══════════════════════════════════════════════════════════════════════════════
# NHẬN DIỆN SONG SONG + LOGIC MỞ BARRIER
# ══════════════════════════════════════════════════════════════════════════════
def _run_plate(img_bytes: bytes) -> dict:
    if plate_ai and plate_ai._ready:
        return plate_ai.recognize(img_bytes)
    return {"plate": "", "confidence": 0.0}


def _run_face(img_bytes: bytes) -> dict:
    if face_ai and face_ai._ready:
        return face_ai.recognize(img_bytes)
    return {"matched": False, "user_id": None, "confidence": 0.0}


# ══════════════════════════════════════════════════════════════════════════════
# AUTO-DETECT LOOP – chạy liên tục, không cần trigger thủ công
# ══════════════════════════════════════════════════════════════════════════════
def auto_detect_loop():
    """
    Vòng lặp tự động:
      1. Chụp frame từ camera biển số – thử nhận diện
      2. Nếu thấy biển số (conf >= PLATE_MIN_CONF) → chụp camera mặt – nhận diện
      3. Nếu cả 2 khớp cùng 1 user trong DB → mở barrier
      4. Sau khi mở barrier, chờ DEBOUNCE_SEC trước khi xét lại
    """
    global status_text, status_color, barrier_active, last_barrier_end

    # Chờ model load xong
    while plate_ai is None or face_ai is None:
        time.sleep(0.5)

    print("[AUTO] Vong lap tu dong bat dau")

    while True:
        # ── Trong thời gian barrier mở hoặc debounce → bỏ qua ────────────
        if barrier_active or (time.time() - last_barrier_end < DEBOUNCE_SEC):
            time.sleep(0.2)
            continue

        # ── 1. Đọc frame biển số ──────────────────────────────────────────
        if cap_plate is None:
            time.sleep(DETECT_INTERVAL_SEC)
            continue

        plate_bytes = _capture_to_bytes(cap_plate, lock_plate)
        if plate_bytes is None:
            time.sleep(DETECT_INTERVAL_SEC)
            continue

        # ── 2. Nhận diện biển số (nhanh) ──────────────────────────────────
        if not plate_ai._ready:
            time.sleep(DETECT_INTERVAL_SEC)
            continue

        plate_res  = _run_plate(plate_bytes)
        plate_str  = plate_res.get("plate", "").strip().upper()
        plate_conf = plate_res.get("confidence", 0.0)

        if not plate_str or plate_conf < PLATE_MIN_CONF:
            # Chưa thấy biển số → vẫn hiện trạng thái chờ
            if status_text != "San sang – dang cho xe vao...":
                status_text  = "San sang – dang cho xe vao..."
                status_color = (0, 200, 100)
            time.sleep(DETECT_INTERVAL_SEC)
            continue

        # ── Thấy biển số → kiểm tra DB trước khi quét mặt ────────────────
        with allowed_lock:
            vehicle_info = allowed_vehicles.get(plate_str)

        if vehicle_info is None:
            status_text  = f"Bien so '{plate_str}' CHUA DANG KY – cho xe tiep theo..."
            status_color = (0, 60, 200)
            time.sleep(DETECT_INTERVAL_SEC)
            continue

        # Biển số hợp lệ → quét khuôn mặt
        status_text  = f"Bien so OK: {plate_str} ({vehicle_info['full_name']}) – Dang quet khuon mat..."
        status_color = (0, 200, 255)
        print(f"[AUTO] Bien so OK: '{plate_str}'  conf={plate_conf:.2f} – quyet mat...")

        # ── 3. Đọc frame mặt + nhận diện ─────────────────────────────────
        face_bytes = _capture_to_bytes(cap_face, lock_face) if cap_face else None
        if face_bytes is None:
            time.sleep(DETECT_INTERVAL_SEC)
            continue

        t0       = time.time()
        face_res = _run_face(face_bytes)
        ms       = int((time.time() - t0) * 1000)

        face_uid     = face_res.get("user_id")
        face_conf    = face_res.get("confidence", 0.0)
        face_matched = face_res.get("matched", False)

        print(f"[AUTO] Khuon mat: matched={face_matched}  uid={face_uid}  conf={face_conf:.3f}  {ms}ms")

        # ── 4. Xét điều kiện mở barrier ──────────────────────────────────
        same_user = (
            face_matched and face_uid is not None
            and str(vehicle_info["user_id"]) == str(face_uid)
        )

        if same_user:
            full_name = vehicle_info["full_name"]
            print(f"[AUTO ✓ MO]  {full_name}  |  {plate_str}  |  P={plate_conf:.2f}  F={face_conf:.2f}")
            status_text  = f"MO BARRIER: {full_name} | {plate_str} | P={plate_conf:.2f} F={face_conf:.2f}"
            status_color = (0, 255, 60)
            # Lưu ảnh
            _save_capture(plate_bytes, "auto_plate")
            _save_capture(face_bytes,  "auto_face")
            # Mở barrier
            barrier_active = True
            send_barrier("OPEN")
            def _close_barrier():
                global barrier_active, last_barrier_end
                time.sleep(BARRIER_OPEN_SEC)
                send_barrier("CLOSE")
                barrier_active   = False
                last_barrier_end = time.time()
                status_text2 = "San sang – dang cho xe vao..."
                print("[AUTO] Barrier dong – tiep tuc giam sat")
            threading.Thread(target=_close_barrier, daemon=True).start()

        elif face_matched and face_uid != vehicle_info["user_id"]:
            status_text  = f"TU CHOI: Bien so ({plate_str}) va khuon mat khac nguoi!"
            status_color = (0, 0, 220)
            print(f"[AUTO ✗] Bien so vs mat khac nguoi: BS_uid={vehicle_info['user_id']}  mat_uid={face_uid}")
            time.sleep(DETECT_INTERVAL_SEC)

        else:
            status_text  = f"Khuon mat KHONG NHAN RA  (BS: {plate_str})  F={face_conf:.2f}"
            status_color = (0, 60, 200)
            time.sleep(DETECT_INTERVAL_SEC)


def run_dual_recognition():
    """
    Luồng xử lý nhận diện: chạy trong thread riêng.

    1. Chụp đồng thời cả 2 camera
    2. Nhận diện biển số + khuôn mặt song song
    3. Kiểm tra: cả 2 phải khớp cùng 1 user trong DB
    4. Mở hoặc từ chối barrier
    """
    global status_text, status_color

    if not processing_lock.acquire(blocking=False):
        print("[SKIP] Dang xu ly, bo qua trigger nay")
        return

    try:
        # ── 1. Chụp ảnh đồng thời ─────────────────────────────────────────
        status_text  = "Dang chup anh tu 2 camera..."
        status_color = (0, 220, 220)

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f_plate_bytes = executor.submit(
                _capture_to_bytes, cap_plate, lock_plate
            ) if cap_plate else None
            f_face_bytes  = executor.submit(
                _capture_to_bytes, cap_face, lock_face
            ) if cap_face else None

            plate_bytes = f_plate_bytes.result() if f_plate_bytes else None
            face_bytes  = f_face_bytes.result()  if f_face_bytes  else None

        if plate_bytes is None and face_bytes is None:
            status_text  = "LOI: Khong chup duoc anh tu ca 2 camera"
            status_color = (0, 0, 255)
            return

        # Lưu ảnh chụp
        plate_path = _save_capture(plate_bytes, "dual_plate") if plate_bytes else None
        face_path  = _save_capture(face_bytes,  "dual_face")  if face_bytes  else None

        # ── 2. Nhận diện song song ─────────────────────────────────────────
        t0 = time.time()
        status_text  = "Dang nhan dien..."
        status_color = (0, 200, 255)

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f_plate_res = executor.submit(_run_plate, plate_bytes) if plate_bytes else None
            f_face_res  = executor.submit(_run_face,  face_bytes)  if face_bytes  else None

            plate_res = f_plate_res.result() if f_plate_res else {"plate": "", "confidence": 0.0}
            face_res  = f_face_res.result()  if f_face_res  else {"matched": False, "user_id": None, "confidence": 0.0}

        ms = int((time.time() - t0) * 1000)

        plate_str    = plate_res.get("plate", "").strip().upper()
        plate_conf   = plate_res.get("confidence", 0.0)
        face_uid     = face_res.get("user_id")
        face_conf    = face_res.get("confidence", 0.0)
        face_matched = face_res.get("matched", False)

        print(f"\n{'─'*60}")
        print(f"[BIEN SO]   '{plate_str}'  conf={plate_conf:.3f}")
        print(f"[KHUON MAT] user_id={face_uid}  conf={face_conf:.3f}  matched={face_matched}")
        print(f"[THOI GIAN] {ms} ms")

        # ── 3. Kiểm tra DB ─────────────────────────────────────────────────
        with allowed_lock:
            vehicle_info = allowed_vehicles.get(plate_str) if plate_str else None

        plate_in_db = vehicle_info is not None
        face_in_db  = face_matched and face_uid is not None

        # Điều kiện cốt lõi: cùng 1 user
        same_user = (
            plate_in_db and face_in_db
            and str(vehicle_info["user_id"]) == str(face_uid)
        )

        # ── 4. Quyết định ──────────────────────────────────────────────────
        print(f"[KIEM TRA]  plate_in_db={plate_in_db}  face_in_db={face_in_db}  same_user={same_user}")

        if same_user:
            full_name = vehicle_info["full_name"]
            print(f"[✓ MO]  {full_name}  |  {plate_str}  |  Pconf={plate_conf:.2f}  Fconf={face_conf:.2f}")
            status_text  = (
                f"OK: {full_name} | {plate_str} | "
                f"P={plate_conf:.2f}  F={face_conf:.2f}  {ms}ms"
            )
            status_color = (0, 255, 0)
            send_barrier("OPEN")
            threading.Timer(BARRIER_OPEN_SEC, lambda: send_barrier("CLOSE")).start()

        elif plate_in_db and not face_in_db:
            owner = vehicle_info["full_name"]
            print(f"[✗ TU CHOI]  Bien so '{plate_str}' hop le ({owner})"
                  f" nhung khuon mat KHONG NHAN RA (conf={face_conf:.2f})")
            status_text  = (
                f"TU CHOI: Bien so OK ({owner}) | "
                f"Khuon mat khong nhan ra  F={face_conf:.2f}"
            )
            status_color = (0, 80, 255)

        elif not plate_in_db and face_in_db:
            print(f"[✗ TU CHOI]  Khuon mat nhan ra ({face_uid})"
                  f" nhung bien so '{plate_str}' KHONG CO TRONG DB")
            status_text  = (
                f"TU CHOI: Khuon mat OK | "
                f"Bien so '{plate_str}' chua dang ky"
            )
            status_color = (0, 80, 255)

        elif plate_in_db and face_in_db and not same_user:
            print(f"[✗ TU CHOI]  Bien so thuoc user {vehicle_info['user_id']}"
                  f" nhung khuon mat la user {face_uid} – KHONG CUNG CHU XE!")
            status_text  = "TU CHOI: Bien so va khuon mat thuoc 2 nguoi khac nhau!"
            status_color = (0, 0, 220)

        else:
            print(f"[✗ TU CHOI]  Ca bien so ('{plate_str}') va khuon mat"
                  f" deu KHONG NHAN RA hoac CHUA DANG KY")
            status_text  = (
                f"TU CHOI: Chua dang ky | "
                f"BS='{plate_str}' ({plate_conf:.2f})  MT=({face_conf:.2f})"
            )
            status_color = (0, 0, 200)

        print(f"{'─'*60}\n")

    finally:
        processing_lock.release()


def _recognition_window():
    """
    Cửa sổ nhận diện sau khi cảm biến kích hoạt.
    Liên tục thử nhận diện cả 2 cam trong SENSOR_WINDOW_SEC giây.
    Mở barrier ngay khi plate + face cùng khớp 1 user trong DB.
    """
    global status_text, status_color, barrier_active, last_barrier_end

    if not processing_lock.acquire(blocking=False):
        print("[SKIP] Dang xu ly, bo qua trigger nay")
        return

    try:
        deadline = time.time() + SENSOR_WINDOW_SEC
        status_text  = f"[{SENSOR_WINDOW_SEC:.0f}s] Dua mat + bien so vao camera..."
        status_color = (0, 220, 220)
        print(f"[SENSOR] Cua so nhan dien {SENSOR_WINDOW_SEC:.0f}s bat dau")

        while time.time() < deadline:
            remaining = deadline - time.time()

            # ── Chụp đồng thời 2 cam ──────────────────────────────────────
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
                fp = ex.submit(_capture_to_bytes, cap_plate, lock_plate) if cap_plate else None
                ff = ex.submit(_capture_to_bytes, cap_face,  lock_face)  if cap_face  else None
                plate_bytes = fp.result() if fp else None
                face_bytes  = ff.result() if ff else None

            if plate_bytes is None or face_bytes is None:
                time.sleep(0.3)
                continue

            # ── Nhận diện song song ───────────────────────────────────────
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
                pr = ex.submit(_run_plate, plate_bytes)
                fr = ex.submit(_run_face,  face_bytes)
                plate_res = pr.result()
                face_res  = fr.result()

            plate_str    = plate_res.get("plate", "").strip().upper()
            plate_conf   = plate_res.get("confidence", 0.0)
            face_uid     = face_res.get("user_id")
            face_conf    = face_res.get("confidence", 0.0)
            face_matched = face_res.get("matched", False)

            # ── Kiểm tra DB ───────────────────────────────────────────────
            with allowed_lock:
                vehicle_info = allowed_vehicles.get(plate_str)

            plate_in_db = vehicle_info is not None
            same_user   = (
                plate_in_db and face_matched and face_uid is not None
                and str(vehicle_info["user_id"]) == str(face_uid)
            )

            print(f"[WINDOW {remaining:.1f}s]  BS='{plate_str}'({plate_conf:.2f})"
                  f"  MT=matched:{face_matched}({face_conf:.2f})"
                  f"  same_user={same_user}")

            if same_user:
                # ✓ Mở barrier
                full_name    = vehicle_info["full_name"]
                status_text  = f"MO BARRIER: {full_name} | {plate_str} | P={plate_conf:.2f} F={face_conf:.2f}"
                status_color = (0, 255, 60)
                print(f"[✓ MO]  {full_name}  |  {plate_str}  |  P={plate_conf:.2f}  F={face_conf:.2f}")
                _save_capture(plate_bytes, "sensor_plate")
                _save_capture(face_bytes,  "sensor_face")
                barrier_active = True
                send_barrier("OPEN")
                def _close_barrier_w():
                    global barrier_active, last_barrier_end
                    time.sleep(BARRIER_OPEN_SEC)
                    send_barrier("CLOSE")
                    barrier_active   = False
                    last_barrier_end = time.time()
                    print("[SENSOR] Barrier dong – san sang nhan xe tiep theo")
                threading.Thread(target=_close_barrier_w, daemon=True).start()
                return  # thoát khỏi cửa sổ

            # ── Cập nhật trạng thái ───────────────────────────────────────
            if plate_in_db and not face_matched:
                owner        = vehicle_info["full_name"]
                status_text  = f"Bien so OK ({owner}) – cho nhan mat...  {remaining:.0f}s"
                status_color = (0, 200, 255)
            elif face_matched and not plate_in_db:
                status_text  = f"Khuon mat OK – cho bien so hop le...  {remaining:.0f}s"
                status_color = (0, 200, 255)
            elif plate_in_db and face_matched:
                status_text  = f"TU CHOI: Bien so & khuon mat khac nguoi!  {remaining:.0f}s"
                status_color = (0, 0, 220)
            else:
                status_text  = f"Dua mat + bien so vao camera...  {remaining:.0f}s"
                status_color = (0, 220, 220)

            time.sleep(DETECT_INTERVAL_SEC)

        # ── Hết cửa sổ → từ chối ─────────────────────────────────────────
        status_text  = "HET THOI GIAN – Khong nhan ra hoac chua dang ky"
        status_color = (0, 0, 200)
        print("[SENSOR] Het cua so nhan dien – tu choi")

    finally:
        processing_lock.release()


def trigger_recognition():
    """Debounce + khởi động cửa sổ nhận diện."""
    global last_trigger
    now = time.time()
    if now - last_trigger < DEBOUNCE_SEC:
        remaining = DEBOUNCE_SEC - (now - last_trigger)
        print(f"[DEBOUNCE] Cho them {remaining:.1f}s")
        return
    last_trigger = now
    threading.Thread(target=_recognition_window, daemon=True).start()


# ══════════════════════════════════════════════════════════════════════════════
# UI HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def _draw_cam_label(frame: np.ndarray, label: str, sub: str = "") -> np.ndarray:
    h, w = frame.shape[:2]
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, h - 52), (w, h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)
    cv2.putText(frame, label, (8, h - 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.58, (255, 255, 255), 1, cv2.LINE_AA)
    if sub:
        cv2.putText(frame, sub, (8, h - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 255, 180), 1, cv2.LINE_AA)
    return frame


def _make_status_bar(width: int, text: str, color: tuple) -> np.ndarray:
    bar = np.zeros((62, width, 3), np.uint8)
    cv2.rectangle(bar, (0, 0), (width, 62),
                  tuple(int(c * 0.28) for c in color), -1)
    # Timestamp nhỏ góc phải
    ts  = datetime.now().strftime("%H:%M:%S")
    cv2.putText(bar, ts, (width - 85, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (150, 150, 150), 1, cv2.LINE_AA)
    # Nội dung trạng thái
    cv2.putText(bar, text[:110], (10, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.62, color, 2, cv2.LINE_AA)
    return bar


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    print("=" * 62)
    print("  DUAL-CAM GATE  –  Xac thuc BIEN SO + KHUON MAT")
    print(f"  Cam bien so  : index {PLATE_CAM_INDEX}")
    print(f"  Cam khuon mat: index {FACE_CAM_INDEX}")
    print(f"  Backend      : {BACKEND_URL}")
    print(f"  Arduino      : {ARDUINO_PORT}")
    print("=" * 62)

    open_cameras()
    if cap_plate is None and cap_face is None:
        print("[FATAL] Khong mo duoc camera nao – kiem tra USB va thu lai")
        return

    # Khởi động các background thread
    threading.Thread(target=load_models,         daemon=True).start()
    threading.Thread(target=db_reload_loop,      daemon=True).start()
    threading.Thread(target=try_connect_arduino, daemon=True).start()
    threading.Thread(target=arduino_listener,    daemon=True).start()
    if AUTO_DETECT:
        threading.Thread(target=auto_detect_loop, daemon=True).start()

    print("\nPhim tat:")
    print("  SPACE    – gia lap tin hieu cam bien (mo cua so nhan dien)")
    print("  Q / ESC  – thoat")
    if not AUTO_DETECT:
        print(f"  [CHE DO CAM BIEN] Cho SENSOR:DETECTED tu Arduino hoac nhan SPACE")
        print(f"  Moi lan kich hoat se nhan dien trong {SENSOR_WINDOW_SEC:.0f} giay")
    print()

    EMPTY = np.zeros((PREVIEW_H, PREVIEW_W, 3), np.uint8)

    while True:
        # ── Đọc frame preview ────────────────────────────────────────────
        if cap_plate:
            pf = _read_frame(cap_plate, lock_plate)
        else:
            pf = None

        if cap_face:
            ff = _read_frame(cap_face, lock_face)
        else:
            ff = None

        plate_disp = cv2.resize(pf if pf is not None else EMPTY, (PREVIEW_W, PREVIEW_H))
        face_disp  = cv2.resize(ff if ff is not None else EMPTY, (PREVIEW_W, PREVIEW_H))

        if pf is None:
            cv2.putText(plate_disp, "CAM BIEN SO: Khong co tin hieu",
                        (10, PREVIEW_H // 2), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (0, 80, 200), 1)
        if ff is None:
            cv2.putText(face_disp, "CAM KHUON MAT: Khong co tin hieu",
                        (10, PREVIEW_H // 2), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (0, 80, 200), 1)

        _draw_cam_label(plate_disp,
                        f"[Cam {PLATE_CAM_INDEX}]  BIEN SO",
                        "Huong vao bien so xe")
        _draw_cam_label(face_disp,
                        f"[Cam {FACE_CAM_INDEX}]  KHUON MAT",
                        "Huong vao khuon mat lai xe")

        combined = np.hstack([plate_disp, face_disp])
        status_bar = _make_status_bar(combined.shape[1], status_text, status_color)
        full_frame = np.vstack([combined, status_bar])

        cv2.imshow("DUAL-CAM GATE  |  SPACE = Nhan dien   Q = Thoat", full_frame)

        # ── Nhận trigger từ Arduino thread ───────────────────────────────
        if trigger_event.is_set():
            trigger_event.clear()
            trigger_recognition()

        # ── Xử lý phím ───────────────────────────────────────────────────
        key = cv2.waitKey(1) & 0xFF
        if key in (ord('q'), 27):          # Q hoặc ESC
            break
        elif key == ord(' '):
            print("[KEY] SPACE – trigger nhan dien")
            trigger_recognition()

    # ── Dọn dẹp ──────────────────────────────────────────────────────────
    if cap_plate: cap_plate.release()
    if cap_face:  cap_face.release()
    cv2.destroyAllWindows()
    print("Da thoat.")


if __name__ == "__main__":
    main()
