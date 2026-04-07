require('dotenv').config();

const serial     = require('./src/esp8266Handler');
const controller = require('./src/controller');
const ws         = require('./src/wsServer');
const ai         = require('./src/aiClient');
const cfg        = require('./src/config');
const axios      = require('axios');

async function resolveDeviceIds() {
  /**
   * Nếu ENTRY_DEVICE_ID / EXIT_DEVICE_ID chưa cấu hình,
   * tự tra cứu theo serial_port trong bảng devices.
   */
  if (cfg.ENTRY_DEVICE_ID && cfg.EXIT_DEVICE_ID) return;

  try {
    const { data: devices } = await axios.get(`${cfg.BACKEND_URL}/api/devices`, {
      headers: { 'x-hardware-key': cfg.HARDWARE_API_KEY },
      timeout: 5000,
    });

    for (const d of devices) {
      if (!cfg.ENTRY_DEVICE_ID && d.serial_port === cfg.ENTRY_SERIAL_PORT) {
        cfg.ENTRY_DEVICE_ID = d.device_id;
        console.log(`[Bridge] Entry device_id = ${d.device_id} (${d.device_name})`);
      }
      if (!cfg.EXIT_DEVICE_ID && d.serial_port === cfg.EXIT_SERIAL_PORT) {
        cfg.EXIT_DEVICE_ID = d.device_id;
        console.log(`[Bridge] Exit device_id = ${d.device_id} (${d.device_name})`);
      }
    }
  } catch (e) {
    console.warn('[Bridge] Không tra được device UUID từ backend:', e.message);
  }
}

async function main() {
  console.log('=================================================');
  console.log(' PARKING HARDWARE BRIDGE');
  console.log('=================================================');
  console.log(` ESP8266 TCP port: ${cfg.ESP8266_TCP_PORT}`);
  console.log(` AI Service: ${cfg.AI_SERVICE_URL}`);
  console.log(` Backend:    ${cfg.BACKEND_URL}`);
  console.log(` WS Port:    ${cfg.WS_PORT}`);
  console.log('=================================================\n');

  // 1. Khởi WebSocket server
  ws.start();

  // 2. Kiểm tra AI service (không block – retry 10s/lần cho đến khi sẵn sàng)
  let _aiReady = false;
  const health = await ai.healthCheck();
  if (health) {
    _aiReady = true;
    console.log('[Bridge] AI Service:', health.status,
                '| plate_model:', health.plate_model_ready,
                '| face_model:', health.face_model_ready);
  } else {
    console.warn('[Bridge] AI Service chưa sẵn sàng – sẽ retry mỗi 10s...');
    const _aiHealthInterval = setInterval(async () => {
      if (_aiReady) { clearInterval(_aiHealthInterval); return; }
      const h = await ai.healthCheck();
      if (h) {
        _aiReady = true;
        console.log('[Bridge] AI Service đã sẵn sàng:', h.status);
        clearInterval(_aiHealthInterval);
      }
    }, 10_000);
  }

  // 3. Tra device UUIDs
  await resolveDeviceIds();

  // 4. Khởi controller (bind events)
  controller.init();

  // 5. Kết nối Arduino qua serial
  serial.connect();

  // 6. Heartbeat – ping Arduino mỗi 30s
  setInterval(() => {
    if (serial.entryReady) serial.ping('entry');
    if (serial.exitReady)  serial.ping('exit');
  }, 30_000);

  console.log('[Bridge] Đang chờ xe...\n');
}

main().catch(err => {
  console.error('[Bridge] Lỗi khởi động:', err);
  process.exit(1);
});
