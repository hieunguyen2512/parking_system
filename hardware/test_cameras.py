"""
Test 4 USB webcam đồng thời
Nhấn:
  Q  – thoát
  S  – chụp snapshot từ tất cả camera
  1-4 – toggle bật/tắt từng camera
"""

import cv2
import numpy as np
import os
import time

# ── Cấu hình ─────────────────────────────────────────────────────────────────
CAMERA_INDICES = [0, 1, 2, 3]  # index của 4 webcam USB
LABELS = ["Cam 0: Entry Plate", "Cam 1: Entry Face",
          "Cam 2: Exit Plate",  "Cam 3: Exit Face"]
WIDTH  = 640
HEIGHT = 480
SNAPSHOT_DIR = os.path.join(os.path.dirname(__file__), "snapshots")
os.makedirs(SNAPSHOT_DIR, exist_ok=True)

# ── Mở camera ────────────────────────────────────────────────────────────────
def open_cameras():
    caps = {}
    for i in CAMERA_INDICES:
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH,  WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            print(f"  Camera {i}: OK  {actual_w}x{actual_h}")
            caps[i] = cap
        else:
            print(f"  Camera {i}: KHÔNG MỞ ĐƯỢC")
    return caps

# ── Tạo frame lỗi (khi không đọc được) ──────────────────────────────────────
def error_frame(label, msg):
    f = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    cv2.putText(f, label, (10, 30),  cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100,100,100), 1)
    cv2.putText(f, msg,   (10, 70),  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 80, 200), 1)
    return f

# ── Vẽ label + FPS lên frame ─────────────────────────────────────────────────
def annotate(frame, label, fps):
    h, w = frame.shape[:2]
    # Overlay nền mờ
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, h-36), (w, h), (0,0,0), -1)
    cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)
    cv2.putText(frame, label,       (8, h-12), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255,255,255), 1, cv2.LINE_AA)
    cv2.putText(frame, f"{fps:.0f} FPS", (w-70, h-12), cv2.FONT_HERSHEY_SIMPLEX, 0.5,  (0,255,100),  1, cv2.LINE_AA)
    return frame

# ── Xếp 4 frame thành lưới 2x2 ──────────────────────────────────────────────
def make_grid(frames):
    top    = np.hstack([frames[0], frames[1]])
    bottom = np.hstack([frames[2], frames[3]])
    return np.vstack([top, bottom])

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    print("=" * 50)
    print("  WEBCAM TEST – 4 cameras đồng thời")
    print("=" * 50)
    caps   = open_cameras()
    active = {i: True for i in CAMERA_INDICES}
    t_prev = {i: time.time() for i in CAMERA_INDICES}
    fps    = {i: 0.0        for i in CAMERA_INDICES}
    snap   = 0

    print("\nPhím tắt:")
    print("  Q       – thoát")
    print("  S       – chụp snapshot tất cả camera")
    print("  1/2/3/4 – bật tắt camera 0/1/2/3\n")

    while True:
        frames = []
        for i in CAMERA_INDICES:
            label = LABELS[i]

            if not active[i]:
                f = error_frame(label, "[Paused]")
                frames.append(f)
                continue

            cap = caps.get(i)
            if cap is None or not cap.isOpened():
                f = error_frame(label, "Khong ket noi duoc")
                frames.append(f)
                continue

            # Flush buffer
            cap.grab()
            ret, frame = cap.read()
            if not ret or frame is None:
                f = error_frame(label, "Loi doc frame")
                frames.append(f)
                continue

            # Resize về cùng kích thước
            frame = cv2.resize(frame, (WIDTH, HEIGHT))

            # Tính FPS
            now = time.time()
            fps[i] = 1.0 / max(now - t_prev[i], 1e-6)
            t_prev[i] = now

            annotate(frame, label, fps[i])
            frames.append(frame)

        # Đảm bảo đủ 4 frame
        while len(frames) < 4:
            frames.append(error_frame("No Camera", ""))

        grid = make_grid(frames)

        # Tiêu đề
        header = np.zeros((40, grid.shape[1], 3), dtype=np.uint8)
        fps_all = [f"{fps[i]:.0f}" for i in CAMERA_INDICES]
        cv2.putText(header,
                    f"4-Camera Live Test  |  FPS: {' / '.join(fps_all)}  |  S=Snapshot  Q=Quit",
                    (10, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1, cv2.LINE_AA)
        display = np.vstack([header, grid])

        cv2.imshow("Parking System – 4 Camera Test", display)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:
            break
        elif key == ord('s'):
            snap += 1
            ts = time.strftime("%Y%m%d_%H%M%S")
            cv2.imwrite(os.path.join(SNAPSHOT_DIR, f"grid_{ts}.jpg"), grid)
            for i, f in zip(CAMERA_INDICES, frames):
                cv2.imwrite(os.path.join(SNAPSHOT_DIR, f"cam{i}_{ts}.jpg"), f)
            print(f"Snapshot #{snap} đã lưu vào {SNAPSHOT_DIR}")
        elif key == ord('1'): active[0] = not active[0]
        elif key == ord('2'): active[1] = not active[1]
        elif key == ord('3'): active[2] = not active[2]
        elif key == ord('4'): active[3] = not active[3]

    # Cleanup
    for cap in caps.values():
        cap.release()
    cv2.destroyAllWindows()
    print("Đã đóng tất cả camera.")

if __name__ == "__main__":
    main()
