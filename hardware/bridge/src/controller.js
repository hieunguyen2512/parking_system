/**
 * Controller – điều phối toàn bộ luồng xử lý
 *
 * ENTRY FLOW:
 *   Arduino sensor DETECTED → gọi AI service → gọi backend → mở/từ chối barrier
 *
 * EXIT FLOW:
 *   Arduino sensor DETECTED → gọi AI service → gọi backend → mở barrier + đóng session
 */

const serial    = require('./esp8266Handler');
const ai        = require('./aiClient');
const backend   = require('./backendClient');
const ws        = require('./wsServer');
const cfg       = require('./config');

// Debounce: tránh xử lý nhiều lần khi sensor dao động
const _lastTrigger = { entry: 0, exit: 0 };
const _processing  = { entry: false, exit: false };

// Theo dõi trạng thái barrier để tránh broadcast BARRIER_CLOSED khi barrier chưa mở
const _barrierOpen = { entry: false, exit: false };

function _debounced(gate) {
  const now = Date.now();
  if (_processing[gate]) return false;       // đang xử lý, bỏ qua
  if (now - _lastTrigger[gate] < cfg.DEBOUNCE_MS) return false;
  _lastTrigger[gate] = now;
  return true;
}

// ── Luồng VÀO ────────────────────────────────────────────────────────────────
async function handleEntry() {
  if (!_debounced('entry')) return;
  _processing.entry = true;

  console.log('\n[ENTRY] === Xe vào phát hiện ===');
  ws.broadcast('ENTRY_DETECTED', { gate: 'entry', ts: Date.now() });

  let aiResult = null;
  try {
    // 1. AI nhận diện
    console.log('[ENTRY] Gọi AI service...');
    aiResult = await ai.processEntry();
    console.log('[ENTRY] AI kết quả:', {
      plate: aiResult.plate,
      plate_conf: aiResult.plate_confidence,
      face_user: aiResult.face_user_id,
      face_conf:  aiResult.face_confidence,
      time_ms:    aiResult.processing_time_ms,
    });
    ws.broadcast('AI_RESULT', { gate: 'entry', ...aiResult });

    // 2. Báo backend tạo session
    const backendRes = await backend.reportEntry({
      plate:             aiResult.plate,
      plate_confidence:  aiResult.plate_confidence,
      plate_image_path:  aiResult.plate_image_path,
      face_user_id:      aiResult.face_user_id,
      face_confidence:   aiResult.face_confidence,
      face_image_path:   aiResult.face_image_path,
      device_id:         cfg.ENTRY_DEVICE_ID,
    });

    console.log('[ENTRY] Backend:', backendRes.message, '| allowed:', backendRes.allowed);
    ws.broadcast('SESSION_CREATED', { gate: 'entry', ...backendRes });

    // 3. Mở barrier – bắt buộc nhận diện được CẢ biển số VÀ khuôn mặt
    const hasPlate = aiResult.plate && aiResult.plate.length >= 2;
    const hasFace  = aiResult.face_user_id != null;
    if (!hasPlate || !hasFace) {
      const missing = !hasPlate && !hasFace ? 'biển số và khuôn mặt'
                    : !hasPlate            ? 'biển số'
                    :                        'khuôn mặt';
      console.warn(`[ENTRY] Thiếu ${missing} – giữ barrier đóng`);
      ws.broadcast('ERROR', { gate: 'entry', message: `Không nhận diện được ${missing} – cần can thiệp thủ công` });
      return;
    }
    if (backendRes.allowed) {
      serial.openBarrier('entry');
      _barrierOpen.entry = true;
      ws.broadcast('BARRIER_OPENED', { gate: 'entry' });
    } else {
      console.warn('[ENTRY] Từ chối vào:', backendRes.message);
      ws.broadcast('ERROR', { gate: 'entry', message: backendRes.message });
    }

  } catch (err) {
    console.error('[ENTRY] Lỗi:', err.message);
    ws.broadcast('ERROR', { gate: 'entry', message: err.message });
    // KHÔNG mở barrier khi lỗi – bắt buộc cần cả mặt lẫn biển số hợp lệ
    console.warn('[ENTRY] AI/Backend lỗi – giữ barrier đóng, cần can thiệp thủ công');
  } finally {
    _processing.entry = false;
  }
}

// ── Luồng RA ─────────────────────────────────────────────────────────────────
async function handleExit() {
  if (!_debounced('exit')) return;
  _processing.exit = true;

  console.log('\n[EXIT] === Xe ra phát hiện ===');
  ws.broadcast('EXIT_DETECTED', { gate: 'exit', ts: Date.now() });

  let aiResult = null;
  try {
    // 1. AI nhận diện
    console.log('[EXIT] Gọi AI service...');
    aiResult = await ai.processExit();
    console.log('[EXIT] AI kết quả:', {
      plate: aiResult.plate,
      plate_conf: aiResult.plate_confidence,
      time_ms:    aiResult.processing_time_ms,
    });
    ws.broadcast('AI_RESULT', { gate: 'exit', ...aiResult });

    // 2. Báo backend đóng session + tính phí
    // Gửi cả face_user_id để backend có thể tìm session qua mặt khi biển số không đọc được
    const backendRes = await backend.reportExit({
      plate:            aiResult.plate,
      plate_confidence: aiResult.plate_confidence,
      plate_image_path: aiResult.plate_image_path,
      face_user_id:     aiResult.face_user_id,
      face_confidence:  aiResult.face_confidence,
      face_image_path:  aiResult.face_image_path,
      device_id:        cfg.EXIT_DEVICE_ID,
    });

    console.log('[EXIT] Backend:', backendRes.message,
      '| fee:', backendRes.fee,
      '| monthly_pass:', backendRes.monthly_pass);
    ws.broadcast('SESSION_CLOSED', { gate: 'exit', ...backendRes });

    // 3. Mở barrier – bắt buộc nhận diện được CẢ biển số VÀ khuôn mặt
    const hasPlate = aiResult.plate && aiResult.plate.length >= 2;
    const hasFace  = aiResult.face_user_id != null;
    if (!hasPlate || !hasFace) {
      const missing = !hasPlate && !hasFace ? 'biển số và khuôn mặt'
                    : !hasPlate            ? 'biển số'
                    :                        'khuôn mặt';
      console.warn(`[EXIT] Thiếu ${missing} – giữ barrier đóng`);
      ws.broadcast('ERROR', {
        gate: 'exit',
        message: `Không nhận diện được ${missing} – cần can thiệp thủ công`,
      });
      return;
    }
    serial.openBarrier('exit');
    _barrierOpen.exit = true;
    ws.broadcast('BARRIER_OPENED', { gate: 'exit' });

  } catch (err) {
    console.error('[EXIT] Lỗi nhận diện:', err.message);
    ws.broadcast('ERROR', { gate: 'exit', message: `Nhận diện thất bại: ${err.message}` });
    // KHÔNG tự mở barrier khi nhận diện lỗi – yêu cầu nhận diện thành công trước khi mở
    // Admin có thể mở thủ công: gửi WebSocket message { type: 'OPEN_BARRIER', gate: 'exit' }
    console.warn('[EXIT] Barrier giữ đóng – chờ admin can thiệp thủ công hoặc xe rời đi');
  } finally {
    _processing.exit = false;
  }
}

// ── Bind events ───────────────────────────────────────────────────────────────
function init() {
  serial.on('entry:detected', handleEntry);
  serial.on('exit:detected',  handleExit);

  serial.on('entry:clear', () => {
    console.log('[ENTRY] Sensor clear');
    if (_barrierOpen.entry) {
      _barrierOpen.entry = false;
      ws.broadcast('BARRIER_CLOSED', { gate: 'entry' });
    }
  });

  serial.on('exit:clear', () => {
    console.log('[EXIT] Sensor clear');
    if (_barrierOpen.exit) {
      _barrierOpen.exit = false;
      ws.broadcast('BARRIER_CLOSED', { gate: 'exit' });
    }
  });

  serial.on('connected',    gate => {
    console.log(`[Serial] ${gate} gate kết nối`);
    ws.broadcast('DEVICE_CONNECTED', { gate });
  });
  serial.on('disconnected', gate => {
    console.warn(`[Serial] ${gate} gate mất kết nối`);
    ws.broadcast('DEVICE_DISCONNECTED', { gate });
  });

  // Đăng ký controller với WS server để nhận SIMULATE_SENSOR
  ws.setController({ simulate });
}

// ── Mô phỏng cảm biến (dùng khi test không có Arduino phần cứng) ─────────────
function simulate(gate) {
  if (gate === 'exit') {
    handleExit();
  } else {
    handleEntry();
  }
}

module.exports = { init };
