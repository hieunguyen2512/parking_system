/**
 * backendClient – gọi Backend API để tạo/đóng session
 */

const axios = require('axios');
const cfg   = require('./config');

const http = axios.create({
  baseURL: cfg.BACKEND_URL,
  timeout: 8000,
  headers: {
    'x-hardware-key': cfg.HARDWARE_API_KEY,
    'Content-Type':   'application/json',
  },
});

/**
 * Xử lý xe vào
 * @param {{ plate, plate_confidence, plate_image_path,
 *           face_user_id, face_confidence, face_image_path,
 *           device_id }} payload
 * @returns {{ allowed, session_id, session_kind,
 *             user_info, monthly_pass, message }}
 */
async function reportEntry(payload) {
  const { data } = await http.post('/api/hardware/entry', payload);
  return data;
}

/**
 * Xử lý xe ra
 * @param {{ plate, plate_confidence, plate_image_path,
 *           face_image_path, device_id }} payload
 * @returns {{ allowed, session_id, fee, message, user_info }}
 */
async function reportExit(payload) {
  const { data } = await http.post('/api/hardware/exit', payload);
  return data;
}

module.exports = { reportEntry, reportExit };
