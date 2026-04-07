import os
from pathlib import Path

# Load .env nếu có
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    with open(_env_path, encoding='utf-8') as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _v = _line.split('=', 1)
                os.environ.setdefault(_k.strip(), _v.strip())

# ─── Server ──────────────────────────────────────────────────────────────────
AI_HOST = os.getenv("AI_HOST", "0.0.0.0")
AI_PORT = int(os.getenv("AI_PORT", "5001"))

# ─── Camera indices (USB webcam) ─────────────────────────────────────────────
# Kiểm tra bằng: python -c "import cv2; [print(i) for i in range(6) if cv2.VideoCapture(i).isOpened()]"
ENTRY_PLATE_CAM  = int(os.getenv("ENTRY_PLATE_CAM", "0"))  # Cam cổng vào - quay biển số
ENTRY_FACE_CAM   = int(os.getenv("ENTRY_FACE_CAM",  "1"))  # Cam cổng vào - quay khuôn mặt
EXIT_PLATE_CAM   = int(os.getenv("EXIT_PLATE_CAM",  "2"))  # Cam cổng ra  - quay biển số
EXIT_FACE_CAM    = int(os.getenv("EXIT_FACE_CAM",   "3"))  # Cam cổng ra  - quay khuôn mặt

CAMERA_WIDTH  = int(os.getenv("CAMERA_WIDTH",  "1280"))
CAMERA_HEIGHT = int(os.getenv("CAMERA_HEIGHT", "720"))
# FPS hardware capture – giảm xuống 15 để tiết kiệm USB bandwidth (4 cam đồng thời)
CAMERA_FPS     = int(os.getenv("CAMERA_FPS",    "15"))
# Giây chờ trước warm_cameras – để Windows khởi tạo xong driver camera
CAMERA_STARTUP_DELAY = float(os.getenv("CAMERA_STARTUP_DELAY", "3.0"))

# LAZY  = mở-chụp-đóng mỗi lần trigger (khuyến nghị khi dùng chung USB hub)
# KEEP  = giữ camera mở liên tục (nhanh hơn, dùng khi mỗi camera có port riêng)
CAPTURE_MODE   = os.getenv("CAPTURE_MODE", "LAZY")
WARMUP_FRAMES  = int(os.getenv("WARMUP_FRAMES", "5"))   # flush auto-exposure khi mở camera

# ─── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR          = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR       = os.getenv("UPLOADS_DIR",
                               os.path.join(BASE_DIR, "..", "..", "BuildWeb", "backend", "uploads"))
CAPTURES_DIR      = os.path.join(UPLOADS_DIR, "captures")   # ảnh chụp thời gian thực
FACES_DIR         = os.path.join(UPLOADS_DIR, "faces")      # ảnh khuôn mặt đã đăng ký
MODELS_DIR        = os.path.join(BASE_DIR, "models")

os.makedirs(CAPTURES_DIR, exist_ok=True)
os.makedirs(MODELS_DIR,   exist_ok=True)

# ─── Plate recognition ───────────────────────────────────────────────────────
PLATE_MODEL_PATH    = os.getenv("PLATE_MODEL_PATH",
                        os.path.join(MODELS_DIR, "plate_detector.pt"))
PLATE_OCR_MODEL_PATH= os.path.join(MODELS_DIR, "plate_ocr.pt")       # TODO: đặt model vào đây
PLATE_CONF_THRESHOLD= float(os.getenv("PLATE_CONF_THRESHOLD", "0.5"))

# ─── Face recognition ────────────────────────────────────────────────────────
FACE_MODEL_PATH      = os.path.join(MODELS_DIR, "face_recognition.pt")  # TODO: đặt model vào đây
FACE_CONF_THRESHOLD  = float(os.getenv("FACE_CONF_THRESHOLD", "0.6"))
FACE_EMBED_DIM       = int(os.getenv("FACE_EMBED_DIM", "512"))
FACE_CAPTURE_DELAY   = float(os.getenv("FACE_CAPTURE_DELAY", "1.0"))   # giây chờ trước khi chụp mặt
FACE_MAX_RETRIES     = int(os.getenv("FACE_MAX_RETRIES", "2"))          # số lần thử lại nếu confidence thấp
PLATE_MAX_RETRIES    = int(os.getenv("PLATE_MAX_RETRIES", "2"))         # số lần thử lại plate nếu confidence thấp

# ─── Backend API ─────────────────────────────────────────────────────────────
BACKEND_URL     = os.getenv("BACKEND_URL",     "http://localhost:4000")
HARDWARE_API_KEY= os.getenv("HARDWARE_API_KEY", "parking_hw_secret_change_this")
