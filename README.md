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

---

## 8. Kết Nối Chi Tiết – Giao Thức & Câu Lệnh

### 8.1 I2C – ESP8266 ↔ Arduino (phần cứng)

| Hướng | Dữ liệu | Ý nghĩa |
|-------|---------|---------|
| ESP → Arduino (WRITE) | `0x00` | PING – kiểm tra Arduino còn sống |
| ESP → Arduino (WRITE) | `0x01` | CMD_OPEN – mở barrier |
| ESP → Arduino (WRITE) | `0x02` | CMD_CLOSE – đóng barrier |
| ESP ← Arduino (READ 1 byte) | bit0=sensor, bit1=open, bit2=ready | Trạng thái: cảm biến / barrier / sẵn sàng |

**Cấu hình I2C:**
```
Bus speed : 100 kHz
SDA pin   : D2 (GPIO4) trên ESP8266
SCL pin   : D1 (GPIO5) trên ESP8266
SDA/SCL   : A4/A5 trên Arduino Uno
Entry addr: 0x08
Exit addr : 0x09
```

**Đọc trạng thái từ Arduino (logic trong ESP8266 firmware):**
```cpp
Wire.requestFrom(0x08, 1);          // đọc 1 byte từ Arduino Entry
uint8_t st = Wire.read();
bool sensor_detected = st & 0x01;   // bit 0 = xe đang chắn cảm biến
bool barrier_open    = st & 0x02;   // bit 1 = barrier đang mở
bool arduino_ready   = st & 0x04;   // bit 2 = Arduino sẵn sàng

Wire.beginTransmission(0x08);
Wire.write(0x01);                   // gửi lệnh OPEN
Wire.endTransmission();
```

---

### 8.2 TCP – ESP8266 ↔ Hardware Bridge (port 4003)

**Kết nối:**
```
ESP8266 → TCP client → 192.168.1.26:4003
Bridge  → TCP server → 0.0.0.0:4003
```

**Tin nhắn ESP8266 → Bridge (kết thúc bằng `\n`):**
```
ENTRY:READY             – ESP8266 kết nối thành công, sẵn sàng
ENTRY:SENSOR:DETECTED   – cảm biến cổng vào phát hiện xe
ENTRY:SENSOR:CLEAR      – cảm biến cổng vào không còn xe
ENTRY:OPENED            – barrier cổng vào đã mở
ENTRY:CLOSED            – barrier cổng vào đã đóng
ENTRY:PONG              – phản hồi PING

EXIT:READY
EXIT:SENSOR:DETECTED
EXIT:SENSOR:CLEAR
EXIT:OPENED
EXIT:CLOSED
EXIT:PONG
```

**Tin nhắn Bridge → ESP8266 (kết thúc bằng `\n`):**
```
ENTRY:OPEN              – ra lệnh mở barrier cổng vào
ENTRY:CLOSE             – ra lệnh đóng barrier cổng vào
ENTRY:PING              – kiểm tra kết nối

EXIT:OPEN
EXIT:CLOSE
EXIT:PING
```

**Test TCP từ PowerShell:**
```powershell
# Kiểm tra port 4003 đang nghe:
Test-NetConnection -ComputerName localhost -Port 4003

# Gửi lệnh mở barrier thủ công (telnet-style):
$client = New-Object System.Net.Sockets.TcpClient("localhost", 4003)
$stream = $client.GetStream()
$writer = New-Object System.IO.StreamWriter($stream)
$writer.AutoFlush = $true
$writer.WriteLine("ENTRY:OPEN")
$client.Close()
```

---

### 8.3 WebSocket – Admin Web ↔ Hardware Bridge (port 4002)

**Kết nối:**
```
ws://localhost:4002
```

**Tin nhắn từ Admin Web → Bridge (JSON):**
```json
// Mở barrier thủ công
{ "type": "OPEN_BARRIER",  "gate": "entry" }
{ "type": "OPEN_BARRIER",  "gate": "exit" }

// Đóng barrier thủ công
{ "type": "CLOSE_BARRIER", "gate": "entry" }
{ "type": "CLOSE_BARRIER", "gate": "exit" }

// Giả lập cảm biến (test không cần Arduino)
{ "type": "SIMULATE_SENSOR", "gate": "entry" }
{ "type": "SIMULATE_SENSOR", "gate": "exit" }
```

**Tin nhắn từ Bridge → Admin Web (JSON):**
```json
{ "type": "ENTRY_DETECTED" }
{ "type": "EXIT_DETECTED" }
{ "type": "AI_RESULT",       "gate": "entry", "plate": "51G-12345", "face_user_id": "uuid...", "allowed": true }
{ "type": "SESSION_CREATED", "gate": "entry", "session_id": "uuid...", "plate": "51G-12345" }
{ "type": "BARRIER_OPENED",  "gate": "entry" }
{ "type": "BARRIER_CLOSED",  "gate": "entry" }
{ "type": "ERROR",           "gate": "entry", "message": "Không nhận diện được biển số" }
```

**Test WebSocket từ PowerShell (cần wscat):**
```powershell
# Cài wscat nếu chưa có:
npm install -g wscat

# Kết nối và gửi lệnh:
wscat -c ws://localhost:4002
# Sau đó gõ: {"type":"OPEN_BARRIER","gate":"entry"}
```

---

### 8.4 REST API – Hardware Bridge → AI Service (port 5001)

**Base URL:** `http://localhost:5001`

#### `GET /health` – Kiểm tra trạng thái
```powershell
Invoke-RestMethod "http://localhost:5001/health"
```
```json
{
  "status": "ok",
  "plate_model_ready": true,
  "face_model_ready": true,
  "known_faces_count": 5,
  "timestamp": "2025-01-01T10:00:00"
}
```

#### `GET /cameras` – Liệt kê camera
```powershell
Invoke-RestMethod "http://localhost:5001/cameras"
```
```json
{
  "cameras": [
    { "index": 0, "width": 1920, "height": 1080, "backend": "DSHOW" },
    { "index": 1, "width": 1920, "height": 1080, "backend": "DSHOW" },
    { "index": 2, "width": 640,  "height": 480,  "backend": "DSHOW" },
    { "index": 3, "width": 1920, "height": 1080, "backend": "DSHOW" }
  ]
}
```

#### `GET /cameras/assignment` – Xem phân công camera
```powershell
Invoke-RestMethod "http://localhost:5001/cameras/assignment"
```
```json
{ "entry_plate": 0, "entry_face": 1, "exit_plate": 2, "exit_face": 3 }
```

#### `POST /cameras/assignment` – Đổi phân công camera (lưu vào .env)
```powershell
Invoke-RestMethod "http://localhost:5001/cameras/assignment" -Method POST `
  -ContentType "application/json" `
  -Body '{"entry_plate":0,"entry_face":1,"exit_plate":2,"exit_face":3}'
```

#### `GET /stream/{cam_index}` – Stream MJPEG từ camera
```
http://localhost:5001/stream/0    ← cổng vào – camera biển số
http://localhost:5001/stream/1    ← cổng vào – camera khuôn mặt
http://localhost:5001/stream/2    ← cổng ra  – camera biển số
http://localhost:5001/stream/3    ← cổng ra  – camera khuôn mặt
```
```powershell
# Kiểm tra stream trả về dữ liệu:
$req = [System.Net.HttpWebRequest]::Create("http://localhost:5001/stream/0")
$req.Timeout = 3000
$resp = $req.GetResponse()
Write-Host "cam0 HTTP status:" $resp.StatusCode
$resp.Close()
```

#### `POST /capture/{cam_index}` – Chụp ảnh tức thời (base64)
```powershell
Invoke-RestMethod "http://localhost:5001/capture/0" -Method POST
```
```json
{ "cam_index": 0, "image_b64": "/9j/4AAQ..." }
```

#### `POST /process/entry` – Toàn bộ luồng nhận diện xe vào
```powershell
Invoke-RestMethod "http://localhost:5001/process/entry" -Method POST
```
```json
{
  "plate":            "51G-12345",
  "plate_confidence": 0.92,
  "plate_image_path": "captures/plate_20250101_100000_abc123.jpg",
  "face_user_id":     "uuid-của-user",
  "face_confidence":  0.87,
  "face_image_path":  "captures/face_20250101_100000_def456.jpg"
}
```

#### `POST /process/exit` – Toàn bộ luồng nhận diện xe ra
```powershell
Invoke-RestMethod "http://localhost:5001/process/exit" -Method POST
```
```json
{
  "plate":            "51G-12345",
  "plate_confidence": 0.90,
  "plate_image_path": "captures/plate_exit_20250101_100500_ghi789.jpg",
  "face_user_id":     null,
  "face_confidence":  0
}
```

#### `POST /faces/reload` – Tải lại dữ liệu khuôn mặt từ thư mục
```powershell
Invoke-RestMethod "http://localhost:5001/faces/reload" -Method POST
```
```json
{ "ok": true, "known_faces_count": 6 }
```

---

### 8.5 REST API – Hardware Bridge → Backend (port 4000)

**Header bắt buộc:** `x-hardware-key: parking_hw_secret_change_this`

#### `POST /api/hardware/entry` – Xử lý xe vào
```powershell
$headers = @{ "x-hardware-key" = "parking_hw_secret_change_this"; "Content-Type" = "application/json" }
$body = @{
  plate             = "51G-12345"
  plate_confidence  = 0.92
  plate_image_path  = "captures/plate_20250101_100000_abc123.jpg"
  face_user_id      = "uuid-của-user"
  face_confidence   = 0.87
  face_image_path   = "captures/face_20250101_100000_def456.jpg"
  device_id         = "8605967a-0c82-4d85-bd65-b89d22268d13"
} | ConvertTo-Json
Invoke-RestMethod "http://localhost:4000/api/hardware/entry" -Method POST -Headers $headers -Body $body
```
**Response – Cho phép vào:**
```json
{
  "allowed":    true,
  "session_id": "uuid-session",
  "message":    "Xe vào thành công",
  "user":       { "user_id": "...", "full_name": "Nguyễn Văn A", "phone_number": "0901234567" },
  "plate":      "51G12345",
  "session_type": "member"
}
```
**Response – Từ chối:**
```json
{ "allowed": false, "message": "Khuôn mặt không khớp với chủ xe", "session_id": null }
```

**Các lý do từ chối có thể xảy ra:**
- `Không nhận diện được biển số` – plate_confidence < ngưỡng (PLATE_CONF_MIN=0.5)
- `Không nhận diện được khuôn mặt` – face_confidence < ngưỡng (FACE_CONF_MIN=0.55)
- `Biển số chưa đăng ký trong hệ thống`
- `Khuôn mặt không khớp với chủ xe`
- `Biển số xe đang trong bãi` – xe chưa ra mà vào lại

#### `POST /api/hardware/exit` – Xử lý xe ra
```powershell
$headers = @{ "x-hardware-key" = "parking_hw_secret_change_this"; "Content-Type" = "application/json" }
$body = @{
  plate             = "51G-12345"
  plate_confidence  = 0.90
  plate_image_path  = "captures/plate_exit_20250101_100500.jpg"
  face_image_path   = "captures/face_exit_20250101_100500.jpg"
  device_id         = "43ea7073-5a58-468a-a01c-05134ac01562"
} | ConvertTo-Json
Invoke-RestMethod "http://localhost:4000/api/hardware/exit" -Method POST -Headers $headers -Body $body
```
```json
{
  "allowed":    true,
  "session_id": "uuid-session",
  "message":    "Xe ra thành công",
  "fee":        5000,
  "duration_minutes": 30,
  "plate":      "51G12345"
}
```

---

### 8.6 REST API – Admin Web → Backend (port 4000)

**Header bắt buộc:** `Authorization: Bearer <admin_jwt_token>`

#### Xác thực Admin
```powershell
# Đăng nhập
$body = '{"email":"admin@parking.com","password":"admin123"}' 
$r = Invoke-RestMethod "http://localhost:4000/api/auth/login" -Method POST -ContentType "application/json" -Body $body
$token = $r.token

# Lưu token cho các lệnh sau
$auth = @{ "Authorization" = "Bearer $token"; "Content-Type" = "application/json" }
```

#### Dashboard
```powershell
Invoke-RestMethod "http://localhost:4000/api/dashboard" -Headers $auth
```

#### Quản lý phiên đỗ xe
```powershell
# Danh sách phiên (đang active)
Invoke-RestMethod "http://localhost:4000/api/sessions?status=active" -Headers $auth

# Lịch sử phiên
Invoke-RestMethod "http://localhost:4000/api/sessions?status=completed&page=1&limit=20" -Headers $auth
```

#### Quản lý thiết bị
```powershell
# Danh sách thiết bị
Invoke-RestMethod "http://localhost:4000/api/devices" -Headers $auth

# Mở barrier thủ công qua Admin API
$body = '{"reason":"Mở thủ công để kiểm tra"}' 
Invoke-RestMethod "http://localhost:4000/api/barriers/8605967a-0c82-4d85-bd65-b89d22268d13/open" `
  -Method POST -Headers $auth -Body $body
```

#### Quản lý người dùng
```powershell
# Danh sách user
Invoke-RestMethod "http://localhost:4000/api/users" -Headers $auth

# Tạo user mới
$body = @{
  full_name    = "Nguyễn Văn A"
  email        = "nva@example.com"
  phone_number = "0901234567"
  password     = "matkhau123"
  role         = "user"
} | ConvertTo-Json
Invoke-RestMethod "http://localhost:4000/api/users" -Method POST -Headers $auth -Body $body
```

#### Event Logs & Báo cáo
```powershell
# Nhật ký sự kiện (10 mới nhất)
Invoke-RestMethod "http://localhost:4000/api/event-logs?limit=10" -Headers $auth

# Báo cáo doanh thu theo ngày
Invoke-RestMethod "http://localhost:4000/api/reports?type=daily&date=2025-01-01" -Headers $auth

# Danh sách cảnh báo chưa đọc
Invoke-RestMethod "http://localhost:4000/api/alerts?read=false" -Headers $auth
```

#### Cấu hình hệ thống
```powershell
# Xem cấu hình hiện tại
Invoke-RestMethod "http://localhost:4000/api/config" -Headers $auth

# Cập nhật cấu hình
$body = '{"parking_fee_per_hour":10000,"plate_conf_min":0.5,"face_conf_min":0.55}'
Invoke-RestMethod "http://localhost:4000/api/config" -Method PUT -Headers $auth -Body $body
```

---

### 8.7 REST API – User WebApp → Backend (port 4000)

**Header bắt buộc:** `Authorization: Bearer <user_jwt_token>`

#### Xác thực User
```powershell
# Đăng ký tài khoản
$body = @{
  full_name    = "Nguyễn Văn A"
  email        = "user@example.com"
  phone_number = "0901234567"
  password     = "matkhau123"
} | ConvertTo-Json
Invoke-RestMethod "http://localhost:4000/api/user/auth/register" -Method POST -ContentType "application/json" -Body $body

# Đăng nhập
$body = '{"email":"user@example.com","password":"matkhau123"}'
$r = Invoke-RestMethod "http://localhost:4000/api/user/auth/login" -Method POST -ContentType "application/json" -Body $body
$utoken = $r.token
$uauth  = @{ "Authorization" = "Bearer $utoken"; "Content-Type" = "application/json" }
```

#### Quản lý xe
```powershell
# Danh sách xe của tôi
Invoke-RestMethod "http://localhost:4000/api/user/vehicles" -Headers $uauth

# Thêm xe
$body = '{"license_plate":"51G-12345","vehicle_type":"car","brand":"Toyota","model":"Vios","color":"Trắng"}'
Invoke-RestMethod "http://localhost:4000/api/user/vehicles" -Method POST -Headers $uauth -Body $body
```

#### Ví điện tử
```powershell
# Xem số dư ví
Invoke-RestMethod "http://localhost:4000/api/user/wallet" -Headers $uauth

# Nạp tiền
$body = '{"amount":100000}'
Invoke-RestMethod "http://localhost:4000/api/user/wallet/deposit" -Method POST -Headers $uauth -Body $body

# Lịch sử giao dịch
Invoke-RestMethod "http://localhost:4000/api/user/wallet/transactions" -Headers $uauth
```

#### Lịch sử đỗ xe & vé tháng
```powershell
# Lịch sử phiên đỗ xe
Invoke-RestMethod "http://localhost:4000/api/user/sessions" -Headers $uauth

# Vé tháng hiện tại
Invoke-RestMethod "http://localhost:4000/api/user/monthly-passes" -Headers $uauth

# Đăng ký vé tháng
$body = '{"vehicle_id":"uuid-xe","lot_id":"uuid-lot","months":1}'
Invoke-RestMethod "http://localhost:4000/api/user/monthly-passes" -Method POST -Headers $uauth -Body $body
```

#### Khuôn mặt & thông báo
```powershell
# Xem ảnh khuôn mặt đã đăng ký
Invoke-RestMethod "http://localhost:4000/api/user/face-images" -Headers $uauth

# Lịch sử đăng ký/thu hồi xe trong bãi
Invoke-RestMethod "http://localhost:4000/api/user/authorizations" -Headers $uauth

# Thông báo
Invoke-RestMethod "http://localhost:4000/api/user/notifications" -Headers $uauth
```

---

### 8.8 Socket.IO – Admin Web ↔ Backend (port 4000)

**Kết nối:**
```javascript
import { io } from 'socket.io-client';
const socket = io('http://localhost:4000', {
  auth: { token: '<admin_jwt_token>' }
});
```

**Sự kiện nhận từ Backend:**
```
session:created    – phiên đỗ xe mới được tạo (xe vào)
session:closed     – phiên đỗ xe kết thúc (xe ra)
alert:new          – cảnh báo mới
device:status      – trạng thái thiết bị thay đổi
```

---

### 8.9 Câu Lệnh Kiểm Tra Toàn Hệ Thống

```powershell
# ── 1. Kiểm tra tất cả port đang lắng nghe ───────────────────────────────────
Get-NetTCPConnection -State Listen |
  Where-Object { $_.LocalPort -in @(3000,4000,4002,4003,5001,5175) } |
  Select-Object LocalPort, @{N='Process';E={(Get-Process -Id $_.OwningProcess).Name}} |
  Sort-Object LocalPort

# ── 2. AI Service ─────────────────────────────────────────────────────────────
Invoke-RestMethod "http://localhost:5001/health"                  # health
Invoke-RestMethod "http://localhost:5001/cameras"                 # camera list

# Kiểm tra tất cả 4 stream camera đang hoạt động:
0..3 | ForEach-Object {
  $i   = $_
  $req = [System.Net.HttpWebRequest]::Create("http://localhost:5001/stream/$i")
  $req.Timeout = 3000
  try { $resp = $req.GetResponse(); Write-Host "cam$i : OK ($($resp.StatusCode))"; $resp.Close() }
  catch { Write-Host "cam$i : FAIL ($_)" }
}

# ── 3. Backend ────────────────────────────────────────────────────────────────
Invoke-RestMethod "http://localhost:4000/api/health"              # health (nếu có route)

# ── 4. Bridge TCP (port 4003) ─────────────────────────────────────────────────
Test-NetConnection -ComputerName localhost -Port 4003 | Select-Object TcpTestSucceeded

# ── 5. Bridge WebSocket (port 4002) ──────────────────────────────────────────
Test-NetConnection -ComputerName localhost -Port 4002 | Select-Object TcpTestSucceeded

# ── 6. Xem log dịch vụ (nếu dùng start-all.ps1) ──────────────────────────────
Get-Content "C:\DoAn\logs\backend.log"    -Tail 20
Get-Content "C:\DoAn\logs\ai_service.log" -Tail 20
Get-Content "C:\DoAn\logs\bridge.log"     -Tail 20

# ── 7. Giả lập xe vào (luồng đầy đủ không cần phần cứng) ────────────────────
$hwHeaders = @{
  "x-hardware-key" = "parking_hw_secret_change_this"
  "Content-Type"   = "application/json"
}
$hwBody = @{
  plate            = "51G-99999"
  plate_confidence = 0.95
  face_user_id     = "uuid-user-đã-tồn-tại"
  face_confidence  = 0.90
  device_id        = "8605967a-0c82-4d85-bd65-b89d22268d13"
} | ConvertTo-Json
Invoke-RestMethod "http://localhost:4000/api/hardware/entry" -Method POST -Headers $hwHeaders -Body $hwBody
```
