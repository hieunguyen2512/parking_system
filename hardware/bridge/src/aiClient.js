/**
 * aiClient – gọi Python AI Service
 */

const axios = require('axios');
const cfg   = require('./config');

const http = axios.create({
  baseURL: cfg.AI_SERVICE_URL,
  timeout: cfg.AI_TIMEOUT_MS,
});

/**
 * Xử lý luồng vào: chụp ảnh + nhận diện biển số + nhận diện khuôn mặt
 * @returns {{ plate, plate_confidence, plate_image_path,
 *             face_user_id, face_confidence, face_image_path,
 *             processing_time_ms }}
 */
async function processEntry() {
  const { data } = await http.post('/process/entry');
  return data;
}

/**
 * Xử lý luồng ra: chụp ảnh + nhận diện biển số
 */
async function processExit() {
  const { data } = await http.post('/process/exit');
  return data;
}

/**
 * Reload danh sách khuôn mặt đã đăng ký (sau khi user upload ảnh mới)
 */
async function reloadFaces() {
  const { data } = await http.post('/faces/reload');
  return data;
}

/**
 * Kiểm tra AI service còn sống không
 */
async function healthCheck() {
  try {
    const { data } = await http.get('/health');
    return data;
  } catch {
    return null;
  }
}

module.exports = { processEntry, processExit, reloadFaces, healthCheck };
