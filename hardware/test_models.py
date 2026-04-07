"""
Test nhanh 2 model AI:
  - plate_detector.pt  (YOLOv8 + EasyOCR)
  - face_detector.pt   (YOLOv8 + InsightFace)

Chay: python test_models.py
"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "ai_service"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "ai_service", "modules"))

import config

SEP = "-" * 56

def test_plate_model():
    print(SEP)
    print("[PLATE] Dang load plate_recognizer...")
    t0 = time.time()
    from plate_recognizer import PlateRecognizer
    pr = PlateRecognizer.get()
    print(f"[PLATE] Load xong: {time.time()-t0:.1f}s  |  ready={pr._ready}")
    if not pr._ready:
        print("[PLATE] FAIL: model chua san sang")
        return False

    # Tao anh test: hinh chu nhat trang voi bien so gia
    import cv2, numpy as np
    img = np.ones((200, 400, 3), dtype=np.uint8) * 200
    cv2.putText(img, "51A-12345", (60, 120), cv2.FONT_HERSHEY_SIMPLEX,
                2, (0,0,0), 4, cv2.LINE_AA)
    _, buf = cv2.imencode(".jpg", img)
    image_bytes = buf.tobytes()

    t0 = time.time()
    result = pr.recognize(image_bytes)
    elapsed = time.time() - t0
    print(f"[PLATE] Ket qua: plate='{result['plate']}'  conf={result['confidence']:.3f}  roi={'co' if result['roi_image'] else 'khong'}  ({elapsed*1000:.0f}ms)")
    return True

def test_face_model():
    print(SEP)
    print("[FACE ] Dang load face_recognizer...")
    t0 = time.time()
    from face_recognizer import FaceRecognizer
    fr = FaceRecognizer.get()
    print(f"[FACE ] Load xong: {time.time()-t0:.1f}s  |  ready={fr._ready}")
    if not fr._ready:
        print("[FACE ] FAIL: model chua san sang")
        return False

    # Tao anh test: anh toi mau (gia khuon mat)
    import cv2, numpy as np
    img = np.ones((300, 300, 3), dtype=np.uint8) * 120
    cv2.circle(img, (150, 150), 80, (200, 180, 160), -1)  # mat gia
    _, buf = cv2.imencode(".jpg", img)
    image_bytes = buf.tobytes()

    t0 = time.time()
    result = fr.recognize(image_bytes)
    elapsed = time.time() - t0
    print(f"[FACE ] Ket qua: user_id={result['user_id']}  conf={result['confidence']:.3f}  matched={result['matched']}  ({elapsed*1000:.0f}ms)")
    print(f"[FACE ] Known users: {len(fr._known_embeddings)}")
    return True

def test_camera_capture():
    print(SEP)
    print("[CAM  ] Test chup anh tu camera 0...")
    from camera_manager import CameraManager
    cm = CameraManager.get()
    t0 = time.time()
    img_bytes = cm.capture(0, retries=2)
    elapsed = time.time() - t0
    if img_bytes:
        print(f"[CAM  ] OK: {len(img_bytes)//1024}KB  ({elapsed*1000:.0f}ms)")
    else:
        print(f"[CAM  ] FAIL: khong chup duoc  ({elapsed*1000:.0f}ms)")

if __name__ == "__main__":
    print(SEP)
    print("  TEST AI MODELS - PARKING SYSTEM")
    print(f"  MODELS DIR: {config.MODELS_DIR}")
    print(SEP)

    ok_plate = test_plate_model()
    ok_face  = test_face_model()
    test_camera_capture()

    print(SEP)
    print(f"Ket qua: Plate={'OK' if ok_plate else 'FAIL'}  Face={'OK' if ok_face else 'FAIL'}")
    print(SEP)
