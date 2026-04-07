# Hệ Thống Bãi Đỗ Xe Thông Minh – Tổng Quan Kết Nối

---

## Sơ Đồ Kiến Trúc Tổng Thể

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            MÁY TÍNH (192.168.1.26)                         │
│                                                                             │
│  ┌───────────────┐   REST/HTTP   ┌────────────────┐   SQL    ┌───────────┐  │
│  │  Admin Web    │◄─────────────►│    Backend     │◄────────►│PostgreSQL │  │
│  │  React+Vite   │               │  Express.js    │          │  DB       │  │
│  │  :3000        │  WebSocket    │  :4000         │          └───────────┘  │
│  │               │◄──────────── ►│  Socket.IO     │                         │
│  └───────────────┘               └────────┬───────┘                         │
│                                           │ REST/HTTP                       │
│  ┌───────────────┐   WebSocket            ▼                                 │
│  │  User WebApp  │◄──────────── ►┌────────────────┐   REST/HTTP             │
│  │  React+Vite   │               │  Hardware      │◄───────────────────┐    │
│  │  :5175        │  REST/HTTP    │  Bridge        │                    │    │
│  │               │◄─────────────►│  Node.js :4002 │                    │    │
│  └───────────────┘               └────────┬───────┘                    │    │
│                                           │ TCP                        │    │
│                                           │ :4003                      │    │
│                                  ┌────────▼───────┐                    │    │
│                                  │  AI Service    │────────────────────┘    │
│                                  │  Python FastAPI│                         │
│                                  │  :5001         │                         │
│                                  └────────────────┘                         │
│                                           ▲ USB (4 webcam)                  │
│                4 webcam ──────────────────┘                                 │
└─────────────────────┬───────────────────────────────────────────────────────┘
                      │ WiFi TCP :4003
                      │ (192.168.1.x → 192.168.1.26)
             ┌────────▼────────┐
             │   ESP8266       │
             │   NodeMCU       │
             │   I2C Master    │
             └──────┬──────────┘
           I2C bus  │  (SDA=D2/GPIO4, SCL=D1/GPIO5, GND chung)
        ┌───────────┴───────────┐
        ▼                       ▼
┌───────────────┐       ┌───────────────┐
│ Arduino UNO   │       │ Arduino UNO   │
│ Entry Gate    │       │ Exit Gate     │
│ I2C: 0x08     │       │ I2C: 0x09     │
│ Servo + HCSR05│       │ Servo + HCSR05│
└───────────────┘       └───────────────┘
```

---

## 1. Lớp Phần Cứng (Hardware Layer)

### 1.1 Arduino UNO – Entry Gate (`entry_gate.ino`)

| Thông số      | Giá trị                        |
|---------------|-------------------------------|
| I2C Address   | `0x08`                         |
| Vai trò       | I2C Slave                      |
| Servo pin     | D6                             |
| Ultrasonic    | Trig=D9, Echo=D10              |
| I2C SDA/SCL   | A4 / A5                        |
| Detect range  | ≤ 80 cm                        |
| Measure interval | 200 ms                      |
| Auto-close delay | 2000 ms sau khi xe qua     |

**Giao thức I2C (1 byte):**
```
READ (ESP8266 → Arduino):
  bit0 = 1 nếu sensor đang phát hiện xe
  bit1 = 1 nếu barrier đang mở
  bit2 = 1 luôn luôn (firmware ready)

WRITE (Arduino ← ESP8266):
  0x00 = PING
  0x01 = MỞ barrier
  0x02 = ĐÓNG barrier
```

---

### 1.2 Arduino UNO – Exit Gate (`exit_gate.ino`)

| Thông số        | Giá trị                        |
|-----------------|-------------------------------|
| I2C Address     | `0x09`                         |
| Vai trò         | I2C Slave                      |
| Servo pin       | D6                             |
| Ultrasonic      | Trig=D9, Echo=D10              |
| I2C SDA/SCL     | A4 / A5                        |
| Detect range    | ≤ 80 cm                        |
| Debounce count  | 3 lần liên tiếp                |
| Auto-close delay| 2000 ms                        |
| Max open time   | 6000 ms (tự đóng nếu kẹt)     |

Giao thức I2C giống Entry Gate.

---

### 1.3 ESP8266 NodeMCU (`esp8266_gate_bridge.ino`)

| Thông số      | Giá trị                         |
|---------------|---------------------------------|
| Vai trò       | I2C Master + WiFi TCP Client    |
| WiFi SSID     | `Khaidepzai`                    |
| Bridge IP     | `192.168.1.26`                  |
| Bridge Port   | `4003` (TCP)                    |
| I2C SDA       | D2 (GPIO4)                      |
| I2C SCL       | D1 (GPIO5)                      |
| Poll interval | 50 ms (20 Hz)                   |
| Ping interval | 30 000 ms                       |
| Reconnect delay | 5 000 ms                      |

**Sơ đồ dây I2C:**
```
ESP8266 D2 (GPIO4) ──── Arduino A4 (SDA)  ┐ cả 2 Arduino
ESP8266 D1 (GPIO5) ──── Arduino A5 (SCL)  ┘ dùng chung bus
GND                ──── GND               (bắt buộc chung mass)
```

**Giao thức TCP (text, kết thúc bằng `\n`):**

| Direction          | Message                     | Ý nghĩa                       |
|--------------------|-----------------------------|-------------------------------|
| ESP8266 → Bridge   | `ENTRY:READY`               | Kết nối thành công, sẵn sàng  |
| ESP8266 → Bridge   | `ENTRY:SENSOR:DETECTED`     | Xe vào được phát hiện         |
| ESP8266 → Bridge   | `ENTRY:SENSOR:CLEAR`        | Xe vào đã qua                 |
| ESP8266 → Bridge   | `ENTRY:PONG`                | Phản hồi PING                 |
| ESP8266 → Bridge   | `EXIT:READY`                | (tương tự cho cổng ra)        |
| Bridge → ESP8266   | `ENTRY:OPEN`                | Lệnh mở barrier vào           |
| Bridge → ESP8266   | `ENTRY:CLOSE`               | Lệnh đóng barrier vào         |
| Bridge → ESP8266   | `ENTRY:PING`                | Kiểm tra kết nối              |
| Bridge → ESP8266   | `EXIT:OPEN / EXIT:CLOSE`    | (tương tự cho cổng ra)        |

---

## 2. Lớp Phần Mềm Máy Tính (Software Layer)

### 2.1 Hardware Bridge (`hardware/bridge/`)

| Thông số     | Giá trị                            |
|--------------|------------------------------------|
| Runtime      | Node.js                            |
| TCP Server   | Port `4003` – nhận kết nối ESP8266 |
| WS Server    | Port `4002` – đẩy event Admin Web  |
| AI Service   | `http://localhost:5001`            |
| Backend      | `http://localhost:4000`            |
| Debounce     | 8000 ms                            |

**Files:**
```
bridge/
├── index.js              – entry point, khởi động tất cả
├── src/
│   ├── esp8266Handler.js – TCP server, giao tiếp ESP8266
│   ├── controller.js     – điều phối luồng vào/ra
│   ├── aiClient.js       – gọi AI Service
│   ├── backendClient.js  – gọi Backend API
│   ├── wsServer.js       – WebSocket tới Admin Web
│   └── config.js         – cấu hình từ .env
└── .env
```

**Luồng xử lý khi xe vào:**
```
ESP8266 → TCP "ENTRY:SENSOR:DETECTED"
  → Bridge Controller [debounce 8s]
  → AI Service POST /process/entry  (chụp cam 0+1, nhận diện)
  → Backend POST /api/entry         (tạo session, kiểm tra quyền)
  → Nếu allowed:  Bridge → TCP "ENTRY:OPEN"
  → Broadcast WS: SESSION_CREATED { allowed: true, ... }
  → Sau khi xe qua: Bridge → TCP "ENTRY:CLOSE"
```

**Luồng xử lý khi xe ra:**
```
ESP8266 → TCP "EXIT:SENSOR:DETECTED"
  → AI Service POST /process/exit  (chụp cam 2+3, nhận diện biển số)
  → Backend POST /api/exit         (đóng session, tính phí)
  → Bridge → TCP "EXIT:OPEN"
  → Broadcast WS: SESSION_CLOSED { fee: ..., ... }
```

---

### 2.2 AI Service (`hardware/ai_service/`)

| Thông số        | Giá trị                          |
|-----------------|----------------------------------|
| Runtime         | Python 3.11 + FastAPI + uvicorn  |
| Port            | `5001`                           |
| Venv            | `venv_paddle`                    |
| Capture mode    | `KEEP` (giữ camera mở liên tục)  |
| Camera FPS      | 15 fps                           |
| Startup delay   | 3 s (chờ Windows init driver)    |
| Backend order   | DSHOW trước MSMF                 |

**Camera mapping:**
```
Cam 0 (DisplayPort) → Entry biển số  (ENTRY_PLATE_CAM=0)
Cam 1 (USB trái)    → Entry khuôn mặt (ENTRY_FACE_CAM=1)
Cam 2 (USB)         → Exit biển số   (EXIT_PLATE_CAM=2)
Cam 3 (USB)         → Exit khuôn mặt (EXIT_FACE_CAM=3)
```

**API Endpoints:**
| Method | Path                  | Mô tả                              |
|--------|-----------------------|------------------------------------|
| GET    | `/health`             | Kiểm tra service còn sống          |
| GET    | `/cameras`            | Danh sách camera khả dụng          |
| GET    | `/cameras/assignment` | Mapping cam → cổng                 |
| GET    | `/stream/{n}`         | MJPEG stream camera n              |
| POST   | `/process/entry`      | Chụp + nhận diện biển số + mặt vào |
| POST   | `/process/exit`       | Chụp + nhận diện biển số ra        |
| POST   | `/recognize/plate`    | Nhận diện biển số từ ảnh base64    |
| POST   | `/recognize/face`     | Nhận diện khuôn mặt từ ảnh base64 |
| POST   | `/faces/reload`       | Reload danh sách khuôn mặt đã đăng ký |

---

### 2.3 Backend (`BuildWeb/backend/`)

| Thông số     | Giá trị              |
|--------------|----------------------|
| Runtime      | Node.js + Express.js |
| Port         | `4000`               |
| Database     | PostgreSQL           |
| Auth         | JWT                  |
| Rate limit   | 10 req/15 phút (login) |
| File upload  | `/uploads/` (ảnh mặt, biển số) |

**API Routes – Admin:**
```
POST /api/auth/login
GET  /api/dashboard
GET  /api/sessions
GET  /api/users
GET  /api/devices
GET  /api/event-logs
GET  /api/reports
GET  /api/alerts
GET  /api/config
POST /api/barriers
POST /api/hardware      ← nhận event từ Bridge
```

**API Routes – User WebApp:**
```
POST /api/user/auth/login
GET  /api/user/vehicles
GET  /api/user/wallet
GET  /api/user/sessions
GET  /api/user/authorizations
GET  /api/user/notifications
POST /api/user/face-images
GET  /api/user/monthly-passes
GET  /api/user/parking-lots
```

---

### 2.4 Admin Web (`BuildWeb/admin-web/`)

| Thông số    | Giá trị                       |
|-------------|-------------------------------|
| Runtime     | React 18 + Vite               |
| Port        | `3000`                        |
| Backend API | proxy `/api` → `localhost:4000` |
| Bridge WS   | `ws://localhost:4002`          |
| AI Stream   | `http://localhost:5001/stream/{n}` |

**Trang:**
- **Devices** – xem 4 camera live MJPEG, điều khiển barrier thủ công, trạng thái ESP8266
- **Dashboard** – tổng quan thống kê thời gian thực
- **Sessions** – lịch sử phiên đỗ xe
- **Users** – quản lý người dùng
- **Alerts / EventLogs / Reports / Config**

---

### 2.5 User WebApp (`WebApp/`)

| Thông số    | Giá trị                        |
|-------------|--------------------------------|
| Runtime     | React 18 + Vite                |
| Port        | `5175`                         |
| Backend API | proxy `/api` → `localhost:4000` |

**Trang:** Dashboard, Vehicles, Wallet, Sessions, Authorizations, Notifications, Profile, MonthlyPasses

---

## 3. Database PostgreSQL

| Thông số    | Giá trị (từ `.env` backend) |
|-------------|-----------------------------|
| Host        | `DB_HOST`                   |
| Port        | `DB_PORT` (mặc định 5432)   |
| Database    | `DB_NAME`                   |
| Pool size   | 20 connections              |

**Bảng chính:** `users`, `vehicles`, `sessions`, `devices`, `event_logs`, `alerts`, `parking_lots`, `monthly_passes`, `wallets`, `authorizations`

---

## 4. Cổng (Port) Tổng Hợp

| Port  | Service              | Protocol     |
|-------|----------------------|--------------|
| 3000  | Admin Web            | HTTP         |
| 4000  | Backend API          | HTTP / WS (Socket.IO) |
| 4002  | Hardware Bridge WS   | WebSocket    |
| 4003  | Hardware Bridge TCP  | TCP (ESP8266)|
| 5001  | AI Service           | HTTP (MJPEG + REST) |
| 5175  | User WebApp          | HTTP         |
| 5432  | PostgreSQL           | TCP          |

---

## 5. Luồng Dữ Liệu End-to-End

### Xe vào bãi:
```
[Xe tiến vào]
    │
    ▼
[Arduino 0x08] – HCSR05 phát hiện (< 80 cm)
    │ I2C bit0=1
    ▼
[ESP8266] – đọc trạng thái mỗi 50ms
    │ TCP "ENTRY:SENSOR:DETECTED\n"
    ▼
[Bridge] – controller.handleEntry() [debounce 8s]
    │ POST /process/entry
    ▼
[AI Service] – chụp cam0 (biển số) + cam1 (mặt)
    │ { plate, plate_confidence, face_user_id, face_confidence }
    ▼
[Bridge] – POST /api/entry (Backend)
    │ { allowed: true/false, session_id, user_info }
    ▼
[Bridge] – nếu allowed → TCP "ENTRY:OPEN\n"
    │                  → WS broadcast SESSION_CREATED
    ▼
[ESP8266] – nhận "ENTRY:OPEN" → I2C write 0x01 tới 0x08
    │
    ▼
[Arduino 0x08] – servo mở 90°
    │ [xe vào xong]
    ▼
[Arduino 0x08] – sensor clear, I2C bit0=0
[ESP8266] – TCP "ENTRY:SENSOR:CLEAR\n"
[Bridge] – TCP "ENTRY:CLOSE\n"
[Arduino 0x08] – servo đóng 0°
```

### Xe ra bãi:
```
[Xe tiến ra]
    │
    ▼
[Arduino 0x09] – HCSR05 phát hiện
    │ TCP "EXIT:SENSOR:DETECTED\n"
    ▼
[Bridge] – controller.handleExit() [debounce 8s]
    │ POST /process/exit
    ▼
[AI Service] – chụp cam2 (biển số)
    │ { plate, plate_confidence }
    ▼
[Bridge] – POST /api/exit (Backend) → tính phí, đóng session
    │ { fee, duration }
    ▼
[Bridge] – TCP "EXIT:OPEN\n" → WS broadcast SESSION_CLOSED { fee }
    ▼
[Arduino 0x09] – servo mở → xe ra → servo đóng
```

---

## 6. Cấu Hình Nhanh Khi Đổi Môi Trường

### Đổi WiFi (chỉ cần nạp lại ESP8266):
```cpp
// hardware/esp8266/esp8266_gate_bridge/esp8266_gate_bridge.ino
const char* WIFI_SSID     = "TênWiFiMới";
const char* WIFI_PASSWORD = "MatKhauMoi";
const char* BRIDGE_HOST   = "IP_may_tinh_moi";
```

### Đổi IP máy tính:
```
hardware/esp8266/esp8266_gate_bridge/esp8266_gate_bridge.ino → BRIDGE_HOST
```

### Đổi cổng camera:
```
hardware/ai_service/.env → ENTRY_PLATE_CAM, ENTRY_FACE_CAM, EXIT_PLATE_CAM, EXIT_FACE_CAM
```

### Đổi database:
```
BuildWeb/backend/.env → DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
```

---

## 7. Khởi Động Hệ Thống

```powershell
# Khởi động tất cả dịch vụ cùng lúc:
.\start-all.ps1

# Hoặc chạy thủ công theo thứ tự:
# 1. PostgreSQL (phải chạy trước)
# 2. Backend:   cd BuildWeb/backend  ; node src/index.js
# 3. AI Service: cd hardware/ai_service ; uvicorn main:app --port 5001
# 4. Bridge:    cd hardware/bridge   ; node index.js
# 5. Admin Web: cd BuildWeb/admin-web ; npm run dev
# 6. WebApp:    cd WebApp             ; npm run dev
```

**Kiểm tra nhanh sau khi khởi động:**
```powershell
# Tất cả port đang lắng nghe:
Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -in @(3000,4000,4002,4003,5001,5175) }

# AI Service health:
Invoke-RestMethod "http://localhost:5001/health"

# Danh sách camera:
Invoke-RestMethod "http://localhost:5001/cameras"
```
