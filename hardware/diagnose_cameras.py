"""
Chẩn đoán camera – quét và hiển thị từng camera có thể dùng được
"""

import cv2
import numpy as np
import time
import subprocess
import re

def scan_windows_cameras():
    """Dùng PowerShell để lấy danh sách camera Windows nhận ra"""
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-PnpDevice -Class 'Camera' | Select-Object FriendlyName,Status | ConvertTo-Csv -NoTypeInformation"],
            capture_output=True, text=True, timeout=10
        )
        lines = result.stdout.strip().split("\n")[1:]  # bỏ header
        devices = []
        for line in lines:
            parts = [p.strip('"') for p in line.strip().split('","')]
            if len(parts) >= 2:
                devices.append({"name": parts[0], "status": parts[1]})
        return devices
    except Exception as e:
        return []

def find_working_cameras(max_index=10):
    """Thử mở từng index và trả về list index hoạt động được"""
    working = []
    for i in range(max_index):
        for backend, name in [(cv2.CAP_MSMF, "MSMF"), (cv2.CAP_DSHOW, "DSHOW")]:
            cap = cv2.VideoCapture(i, backend)
            if not cap.isOpened():
                cap.release()
                continue
            time.sleep(0.2)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            for _ in range(5):
                cap.grab()
            ret, frame = cap.read()
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()
            if ret and frame is not None:
                working.append({"index": i, "backend": backend, "backend_name": name,
                                 "width": w, "height": h})
                break  # đã tìm được backend OK cho index này
    return working

def show_cameras(working):
    if not working:
        print("\nKhong co camera nao hoat dong duoc!")
        return

    print(f"\nHien thi {len(working)} camera...")
    caps = {}
    for info in working:
        cap = cv2.VideoCapture(info["index"], info["backend"])
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        caps[info["index"]] = (cap, info)

    print("Nhan Q de thoat, S de chup snapshot")
    fps_data = {i: 0.0 for i in caps}
    t_prev   = {i: time.time() for i in caps}
    snap = 0

    while True:
        frames = []
        for idx, (cap, info) in caps.items():
            for _ in range(2):
                cap.grab()
            ret, frame = cap.read()
            if not ret or frame is None:
                f = np.zeros((480, 640, 3), np.uint8)
                cv2.putText(f, f"Index {idx}: LOI DOC FRAME", (10,50),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,200), 2)
            else:
                f = cv2.resize(frame, (640, 480))
                now = time.time()
                fps_data[idx] = 1.0 / max(now - t_prev[idx], 1e-6)
                t_prev[idx] = now

            # Overlay
            label = f"Index {idx} ({info['backend_name']})  {fps_data[idx]:.0f}fps"
            cv2.rectangle(f, (0, 450), (640, 480), (0,0,0), -1)
            cv2.putText(f, label, (5, 472),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255,255,255), 1)
            frames.append(f)

        # Xếp lưới
        if len(frames) == 1:
            grid = frames[0]
        elif len(frames) == 2:
            grid = np.hstack(frames)
        elif len(frames) <= 4:
            while len(frames) < 4:
                frames.append(np.zeros((480,640,3), np.uint8))
            grid = np.vstack([np.hstack(frames[:2]), np.hstack(frames[2:])])
        else:
            grid = np.hstack(frames[:4])

        # Header
        info_text = f"Cameras hoat dong: {len(working)}  |  S=Snapshot  Q=Quit"
        header = np.zeros((35, grid.shape[1], 3), np.uint8)
        cv2.putText(header, info_text, (8, 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180,255,180), 1)
        cv2.imshow("Camera Diagnostic", np.vstack([header, grid]))

        key = cv2.waitKey(1) & 0xFF
        if key in [ord('q'), 27]:
            break
        elif key == ord('s'):
            snap += 1
            ts = time.strftime("%Y%m%d_%H%M%S")
            import os
            out = os.path.join(os.path.dirname(__file__), f"diag_snap_{ts}.jpg")
            cv2.imwrite(out, grid)
            print(f"Snapshot luu: {out}")

    for cap, _ in caps.values():
        cap.release()
    cv2.destroyAllWindows()

def main():
    print("=" * 55)
    print("  CAMERA DIAGNOSTIC TOOL")
    print("=" * 55)

    print("\n[1] Quet camera tu Windows Device Manager...")
    win_devs = scan_windows_cameras()
    if win_devs:
        ok_count = sum(1 for d in win_devs if d["status"] == "OK")
        for d in win_devs:
            icon = "[OK]" if d["status"] == "OK" else "[!!]"
            print(f"    {icon} {d['name']:30s}  [{d['status']}]")
        if ok_count < len(win_devs):
            diff = len(win_devs) - ok_count
            print(f"\n  CANH BAO: {diff} camera trang thai 'Unknown/Error'.")
            print("     Nguyen nhan co the:")
            print("     - 4 webcam cung model xung dot driver (cung VID/PID)")
            print("     - Khong du bang thong USB (cam tren cung USB controller)")
            print("     Giai phap:")
            print("     - Cam vao cac cong USB khac nhau (USB 2.0 + USB 3.0 tron lan)")
            print("     - Dung USB hub co nguon rieng")
            print("     - Giam resolution xuong 720p hoac 480p")
    else:
        print("  Khong query duoc Device Manager")

    print("\n[2] Quet camera hoat dong duoc qua OpenCV (index 0-9)...")
    working = find_working_cameras(10)
    if working:
        print(f"  Tim thay {len(working)} camera hoat dong:")
        for w in working:
            print(f"    Index {w['index']:2d}  {w['backend_name']:6s}  {w['width']}x{w['height']}")
        print(f"\n  => Cap nhat config.py:")
        for w in working:
            roles = ["ENTRY_PLATE_CAM", "ENTRY_FACE_CAM", "EXIT_PLATE_CAM", "EXIT_FACE_CAM"]
            role  = roles[working.index(w)] if working.index(w) < 4 else f"CAM_{w['index']}"
            print(f"     {role:20s} = {w['index']}")
    else:
        print("  Khong tim thay camera nao!")

    if working:
        print("\n[3] Hien thi live feed...")
        show_cameras(working)

if __name__ == "__main__":
    main()
