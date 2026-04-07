/**
 * comAutoDetect.js – Tự động tìm COM port của Arduino theo serial number (Windows).
 *
 * Tại sao cần: Khi rút/cắm lại USB, Windows có thể đổi số COM (COM9 → COM10, v.v.)
 * nhưng serial number của thiết bị không đổi → dùng để nhận dạng chắc chắn.
 *
 * Cách lấy serial number:
 *   PowerShell: Get-WmiObject -Class Win32_PnPEntity |
 *               Where-Object { $_.Name -match "COM\d+" } |
 *               Select-Object Name, DeviceID
 *   Serial number là phần cuối của DeviceID, ví dụ:
 *     USB\VID_0843&PID_5740\FX2348N   → serial = FX2348N
 *
 * Lưu vào .env:
 *   ENTRY_SERIAL_NUMBER=FX2348N       (hoặc bỏ trống để dùng ENTRY_SERIAL_PORT cố định)
 *   EXIT_SERIAL_NUMBER=5&52206AA&0&1
 */

const { execSync } = require('child_process');

/**
 * Lấy danh sách tất cả COM port đang có trên hệ thống cùng serial number.
 * @returns {Array<{ com: string, serialNum: string, name: string }>}
 */
function listSerialDevices() {
  try {
    const ps = `
      Get-WmiObject -Class Win32_PnPEntity |
      Where-Object { $_.Name -match 'COM\\d+' } |
      Select-Object Name, DeviceID |
      ConvertTo-Json -Compress
    `;
    const out = execSync(`powershell -NoProfile -Command "${ps}"`, {
      timeout: 5000, encoding: 'utf8',
    }).trim();

    if (!out || out === 'null') return [];
    const raw = JSON.parse(out);
    const arr = Array.isArray(raw) ? raw : [raw];
    return arr.map(d => {
      const comMatch = (d.Name || '').match(/COM(\d+)/);
      const com      = comMatch ? `COM${comMatch[1]}` : null;
      // DeviceID dạng: USB\VID_xxxx&PID_xxxx\SERIALNUMBER
      const parts    = (d.DeviceID || '').split('\\');
      const serialNum = parts.length >= 3 ? parts[parts.length - 1] : '';
      return { com, serialNum: serialNum.toUpperCase(), name: d.Name || '' };
    }).filter(d => d.com);
  } catch (e) {
    console.warn('[ComAutoDetect] WMI query failed:', e.message);
    return [];
  }
}

/**
 * Tìm COM port theo serial number.
 * @param {string} serialNumber  – serial number cần tìm (không phân biệt hoa/thường)
 * @returns {string|null}  – "COMx" hoặc null nếu không tìm thấy
 */
function findComBySerial(serialNumber) {
  if (!serialNumber) return null;
  const devices = listSerialDevices();
  const found = devices.find(d => d.serialNum === serialNumber.toUpperCase());
  return found ? found.com : null;
}

/**
 * Resolve COM port: ưu tiên tìm theo serial number, fallback về port cố định trong .env.
 * @param {string} gate          – 'entry' | 'exit'
 * @param {string} serialNumber  – serial number trong .env (có thể trống)
 * @param {string} fallbackPort  – COM port cố định trong .env
 * @returns {string}  – COM port để dùng
 */
function resolvePort(gate, serialNumber, fallbackPort) {
  if (serialNumber) {
    const found = findComBySerial(serialNumber);
    if (found) {
      if (found !== fallbackPort) {
        console.log(`[ComAutoDetect:${gate}] Serial ${serialNumber} → ${found} (đã đổi từ ${fallbackPort})`);
      } else {
        console.log(`[ComAutoDetect:${gate}] Serial ${serialNumber} → ${found}`);
      }
      return found;
    }
    console.warn(`[ComAutoDetect:${gate}] Không tìm thấy serial ${serialNumber} – dùng fallback ${fallbackPort}`);
  }
  return fallbackPort;
}

module.exports = { listSerialDevices, findComBySerial, resolvePort };
