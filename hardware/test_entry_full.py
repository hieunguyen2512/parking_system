"""
=============================================================
  TEST ĐẦY ĐỦ LUỒNG LỐI VÀO (Entry Gate End-to-End Test)
=============================================================

Kiểm tra từng bước của quy trình:
  [1] Arduino COM6 – kết nối và nhận SENSOR:DETECTED
  [2] Camera 1     – chụp ảnh (khuôn mặt)
  [3] AI Service   – gọi /recognize/face  →  nhận diện khuôn mặt
  [4] Camera 0     – chụp ảnh (biển số) [tuỳ chọn]
  [5] AI Service   – gọi /recognize/plate →  nhận diện biển số
  [6] Backend      – POST /api/hardware/entry → lấy phán quyết
  [7] Arduino      – gửi OPEN nếu allowed

Chạy:  python test_entry_full.py
       python test_entry_full.py --no-sensor   (bỏ qua chờ sensor, test ngay)
       python test_entry_full.py --plate 51A12345  (dùng biển số thủ công)
"""

import sys, os, time, argparse, threading, json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "ai_service"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "ai_service", "modules"))

import cv2, requests
import config

# ────── Config ──────────────────────────────────────────────────────────────
ARDUINO_PORT  = "COM6"
BAUD_RATE     = 9600
CAM_FACE      = 1
CAM_PLATE     = 0
BACKEND_URL   = "http://localhost:4000"
AI_URL        = "http://localhost:5001"
HW_KEY        = "parking_hw_secret_change_this"
DEVICE_ID     = "8605967a-0c82-4d85-bd65-b89d22268d13"   # entry Arduino UUID

SEP  = "=" * 60
STEP = lambda n, t: print(f"\n[{n}] {t}")
OK   = lambda t: print(f"    OK  {t}")
FAIL = lambda t: print(f"    FAIL {t}")
INFO = lambda t: print(f"    --  {t}")


# ════════════════════════════════════════════════════════════════════════════
# 1. Arduino
# ════════════════════════════════════════════════════════════════════════════
def test_arduino(no_sensor: bool):
    STEP(1, "Arduino – kết nối COM6")
    try:
        import serial
        ser = serial.Serial(ARDUINO_PORT, BAUD_RATE, timeout=1)
        time.sleep(1.5)
        ser.reset_input_buffer()
        OK(f"Kết nối {ARDUINO_PORT} thành công")
    except Exception as e:
        FAIL(f"Không kết nối được: {e}")
        return None

    if no_sensor:
        INFO("--no-sensor: bỏ qua chờ SENSOR:DETECTED")
        return ser

    INFO("Đang chờ SENSOR:DETECTED (đi vào vùng cảm biến)…")
    deadline = time.time() + 30
    while time.time() < deadline:
        line = ser.readline().decode("utf-8", errors="ignore").strip()
        if line:
            INFO(f"Arduino: {line}")
        if line == "SENSOR:DETECTED":
            OK("Cảm biến phát hiện phương tiện!")
            return ser
    FAIL("Hết 30s – không nhận được SENSOR:DETECTED")
    return ser   # trả về dù không có sensor để chạy các bước tiếp


def _open_camera(idx):
    """Thử mở camera với MSMF rồi DSHOW, kiểm tra grab thực tế."""
    for backend, name in [(cv2.CAP_MSMF, "MSMF"), (cv2.CAP_DSHOW, "DSHOW")]:
        cap = cv2.VideoCapture(idx, backend)
        if cap.isOpened():
            time.sleep(0.3)
            ok = cap.grab()
            if ok:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                INFO(f"Camera {idx} ok [{name}]")
                return cap
            else:
                INFO(f"Camera {idx} [{name}] mở được nhưng không grab (đang bị process khác chiếm)")
        cap.release()
    return None

def _grab_frame(cap):
    """Warm-up 5 frame rồi đọc."""
    for _ in range(5):
        cap.grab()
        time.sleep(0.05)
    ret, frm = cap.read()
    return frm if ret else None


# ════════════════════════════════════════════════════════════════════════════
# 2-3. Camera + AI Face
# ════════════════════════════════════════════════════════════════════════════
def test_capture_face(cam_idx=None):
    idx = cam_idx if cam_idx is not None else CAM_FACE
    STEP(2, f"Camera {idx} – chụp ảnh khuôn mặt")
    cap = _open_camera(idx)
    if not cap:
        FAIL("Không mở được camera")
        return None
    frame = _grab_frame(cap)
    cap.release()
    if frame is None:
        FAIL("Không đọc được frame")
        return None
    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
    img_bytes = buf.tobytes()
    size_kb = len(img_bytes) // 1024
    OK(f"Đã chụp {size_kb} KB  ({frame.shape[1]}x{frame.shape[0]})")

    STEP(3, "AI Service – nhận diện khuôn mặt")
    try:
        import base64
        b64 = base64.b64encode(img_bytes).decode()
        t0  = time.time()
        r   = requests.post(f"{AI_URL}/recognize/face",
                            json={"image_b64": b64}, timeout=30)
        ms  = int((time.time() - t0) * 1000)
        d   = r.json()
        matched = d.get("matched", False)
        uid     = d.get("user_id")
        conf    = d.get("confidence", 0)
        if matched:
            OK(f"Nhận diện OK  user={uid}  conf={conf:.3f}  {ms}ms")
        else:
            INFO(f"Không khớp  conf={conf:.3f}  {ms}ms")
        return d
    except Exception as e:
        FAIL(f"AI lỗi: {e}")
        return None


# ════════════════════════════════════════════════════════════════════════════
# 4-5. Camera + AI Plate
# ════════════════════════════════════════════════════════════════════════════
def test_capture_plate(manual_plate: str = None, cam_idx=None):
    if manual_plate:
        STEP(4, f"Biển số thủ công: {manual_plate}")
        OK(f"Sử dụng biển số: {manual_plate}")
        return {"plate": manual_plate, "confidence": 1.0, "roi_image": None}

    idx = cam_idx if cam_idx is not None else CAM_PLATE
    STEP(4, f"Camera {idx} – chụp ảnh biển số")
    cap = _open_camera(idx)
    if not cap:
        INFO("Không mở được camera biển số – bỏ qua")
        return None
    frame = _grab_frame(cap)
    cap.release()
    if frame is None:
        INFO("Không đọc frame – bỏ qua")
        return None
    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
    img_bytes = buf.tobytes()
    OK(f"Đã chụp {len(img_bytes)//1024} KB")

    STEP(5, "AI Service – nhận diện biển số")
    try:
        import base64
        b64 = base64.b64encode(img_bytes).decode()
        t0  = time.time()
        r   = requests.post(f"{AI_URL}/recognize/plate",
                            json={"image_b64": b64}, timeout=8)
        ms  = int((time.time() - t0) * 1000)
        d   = r.json()
        plate = d.get("plate", "")
        conf  = d.get("confidence", 0)
        if plate:
            OK(f"Biển số: {plate}  conf={conf:.3f}  {ms}ms")
        else:
            INFO(f"Không nhận ra biển số  conf={conf:.3f}  {ms}ms")
        return d
    except Exception as e:
        FAIL(f"AI lỗi: {e}")
        return None


# ════════════════════════════════════════════════════════════════════════════
# 6. Backend
# ════════════════════════════════════════════════════════════════════════════
def test_backend(face_result, plate_result):
    STEP(6, "Backend – POST /api/hardware/entry")
    plate      = (plate_result or {}).get("plate", "")
    plate_conf = (plate_result or {}).get("confidence", 0.0)
    face_uid   = (face_result  or {}).get("user_id")
    face_conf  = (face_result  or {}).get("confidence", 0.0)

    payload = {
        "device_id":        DEVICE_ID,
        "plate":            plate,
        "plate_confidence": plate_conf,
        "face_user_id":     face_uid,
        "face_confidence":  face_conf,
    }
    INFO(f"Payload: plate={plate!r}  face_uid={str(face_uid)[:16] if face_uid else None}")
    try:
        t0 = time.time()
        r  = requests.post(
            f"{BACKEND_URL}/api/hardware/entry",
            json=payload,
            headers={"x-hardware-key": HW_KEY},
            timeout=10,
        )
        ms = int((time.time() - t0) * 1000)
        d  = r.json()
        if d.get("allowed"):
            user = d.get("user_info", {})
            OK(f"ALLOWED  user={user.get('full_name','?')}  monthly_pass={d.get('monthly_pass',False)}  {ms}ms")
        else:
            INFO(f"DENIED  reason={d.get('message','?')}  {ms}ms")
        return d
    except Exception as e:
        FAIL(f"Backend lỗi: {e}")
        return None


# ════════════════════════════════════════════════════════════════════════════
# 7. Barrier
# ════════════════════════════════════════════════════════════════════════════
def test_barrier(ser, decision):
    STEP(7, "Arduino – điều khiển barrier")
    if ser is None:
        INFO("Không có kết nối Arduino – bỏ qua")
        return

    if decision and decision.get("allowed"):
        ser.write(b"OPEN\n")
        OK("Đã gửi OPEN tới Arduino")
        # Đọc phản hồi trong 3s
        deadline = time.time() + 3
        while time.time() < deadline:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if line:
                INFO(f"Arduino: {line}")
            if "BARRIER:OPEN" in line:
                OK("Barrier đã mở!")
                break
        # Tự đóng sau 4s
        def close():
            time.sleep(4)
            ser.write(b"CLOSE\n")
            INFO("Barrier đóng.")
        threading.Thread(target=close, daemon=True).start()
    else:
        INFO("Không mở barrier (DENIED hoặc không có quyết định)")


# ════════════════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-sensor", action="store_true",
                        help="Bỏ qua chờ SENSOR:DETECTED, test ngay")
    parser.add_argument("--plate", default=None,
                        help="Dùng biển số thủ công thay vì nhận diện camera")
    parser.add_argument("--cam-face", type=int, default=None,
                        help=f"Index camera khuôn mặt (mặc định {CAM_FACE})")
    parser.add_argument("--cam-plate", type=int, default=None,
                        help=f"Index camera biển số (mặc định {CAM_PLATE})")
    args = parser.parse_args()

    print(SEP)
    print("  TEST ĐẦY ĐỦ LUỒNG LỐI VÀO (Entry Gate)")
    print(f"  Backend : {BACKEND_URL}")
    print(f"  AI      : {AI_URL}")
    print(f"  Arduino : {ARDUINO_PORT}")
    print(SEP)

    # Kiểm tra AI service có online không
    try:
        r = requests.get(f"{AI_URL}/health", timeout=10)
        if r.ok:
            INFO(f"AI Service online  (v{r.json().get('version','?')})")
        else:
            FAIL("AI Service trả lỗi – hãy chạy ai_service trước")
    except Exception as he:
        print(f"\n  CANH BAO: AI Service offline ({AI_URL}) – {he}")
        print("  Chay: cd hardware/ai_service && uvicorn main:app --port 5001\n")

    ser          = test_arduino(args.no_sensor)
    face_result  = test_capture_face(cam_idx=args.cam_face)
    plate_result = test_capture_plate(args.plate, cam_idx=args.cam_plate)
    decision     = test_backend(face_result, plate_result)
    test_barrier(ser, decision)

    print(f"\n{SEP}")
    allowed = (decision or {}).get("allowed", False)
    print(f"  KET QUA CUOI: {'MO CONG' if allowed else 'TU CHOI / KHONG XAC THUC'}")
    print(SEP)

    if ser:
        time.sleep(5)   # đợi barrier đóng
        ser.close()


if __name__ == "__main__":
    main()
