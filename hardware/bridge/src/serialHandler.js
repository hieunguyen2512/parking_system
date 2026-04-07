/**
 * SerialHandler – quản lý kết nối serial với 2 Arduino
 *
 * Sự kiện emit:
 *   'entry:detected'   – HYSRF05 cổng vào phát hiện xe
 *   'entry:clear'      – HYSRF05 cổng vào không còn xe
 *   'exit:detected'    – HYSRF05 cổng ra phát hiện xe
 *   'exit:clear'       – HYSRF05 cổng ra không còn xe
 *   'connected'        – Arduino kết nối thành công
 *   'disconnected'     – Arduino mất kết nối
 */

const { SerialPort }         = require('serialport');
const EventEmitter           = require('events');
const cfg                    = require('./config');
const { resolvePort }        = require('./comAutoDetect');

class SerialHandler extends EventEmitter {
  constructor() {
    super();
    this._entryPort = null;
    this._exitPort  = null;
    this._entryReady = false;
    this._exitReady  = false;
  }

  // ── Kết nối ──────────────────────────────────────────────────────────────
  connect() {
    const entryPort = resolvePort('entry', cfg.ENTRY_SERIAL_NUMBER, cfg.ENTRY_SERIAL_PORT);
    const exitPort  = resolvePort('exit',  cfg.EXIT_SERIAL_NUMBER,  cfg.EXIT_SERIAL_PORT);
    this._openPort('entry', entryPort);
    this._openPort('exit',  exitPort);
  }

  _openPort(gate, path) {
    const port = new SerialPort({
      path,
      baudRate: cfg.SERIAL_BAUD,
      autoOpen: false,
      rtscts:   false,
      xon:      false,
      xoff:     false,
      hupcl:    false,   // giữ DTR=high khi đóng → Arduino không reset
    });

    // Manual line buffer thay vì ReadlineParser (tránh lỗi pipe() trên Windows USB CDC)
    let _lineBuf = '';
    const self = this;
    port.on('data', (chunk) => {
      _lineBuf += chunk.toString('utf8');
      let idx;
      while ((idx = _lineBuf.indexOf('\n')) !== -1) {
        const line = _lineBuf.slice(0, idx).replace(/\r$/, '').trim();
        _lineBuf = _lineBuf.slice(idx + 1);
        if (line) self._handleLine(gate, line);
      }
    });

    port.open(err => {
      if (err) {
        console.error(`[Serial:${gate}] Không mở được ${path}:`, err.message);
        const serialNum = gate === 'entry' ? cfg.ENTRY_SERIAL_NUMBER : cfg.EXIT_SERIAL_NUMBER;
        const fallback  = gate === 'entry' ? cfg.ENTRY_SERIAL_PORT   : cfg.EXIT_SERIAL_PORT;
        setTimeout(() => {
          // Thử tìm lại COM port qua serial number (có thể đã đổi sau khi replug)
          const retryPath = resolvePort(gate, serialNum, fallback);
          this._openPort(gate, retryPath);
        }, 5000);
        return;
      }
      console.log(`[Serial:${gate}] Kết nối ${path} thành công`);

      // Force reset Arduino bằng cách toggle DTR: LOW→HIGH (giống Arduino IDE khi upload)
      // DTR LOW = kéo RESET pin xuống → Arduino reset
      // DTR HIGH = thả RESET pin → Arduino boot
      port.set({ dtr: false, rts: false }, () => {
        setTimeout(() => {
          port.set({ dtr: true, rts: true }, (e) => {
            if (e) console.warn(`[Serial:${gate}] set DTR high:`, e.message);
          });
        }, 150);  // giữ LOW 150ms (đủ để trigger reset)
      });

      // Gửi PING sau 2.5s (150ms reset delay + 2s Arduino boot time)
      const _doPing = () => {
        if (!port.isOpen) return;
        port.write('PING\n');
        console.log(`[Serial:${gate}] >>> PING`);
      };
      setTimeout(_doPing, 2500);

      // Retry PING mỗi 10s nếu chưa nhận được READY/PONG
      const _pingInterval = setInterval(() => {
        if (!port.isOpen) { clearInterval(_pingInterval); return; }
        const ready = gate === 'entry' ? this._entryReady : this._exitReady;
        if (!ready) {
          console.log(`[Serial:${gate}] Chưa thấy READY – thử PING lại...`);
          _doPing();
        } else {
          clearInterval(_pingInterval);
        }
      }, 10000);

      port.once('close', () => clearInterval(_pingInterval));
    });

    port.on('close', () => {
      console.warn(`[Serial:${gate}] Mất kết nối – thử lại sau 5s`);
      if (gate === 'entry') this._entryReady = false;
      else                  this._exitReady  = false;
      this.emit('disconnected', gate);
      setTimeout(() => this._openPort(gate, path), 5000);
    });

    port.on('error', err => {
      console.error(`[Serial:${gate}] Lỗi:`, err.message);
    });

    if (gate === 'entry') this._entryPort = port;
    else                  this._exitPort  = port;
  }

  // ── Xử lý line nhận từ Arduino ───────────────────────────────────────────
  _handleLine(gate, line) {
    if (!line) return;  // bỏ qua dòng trống
    console.log(`[Serial:${gate}] <<< ${line}`);

    if (line === `READY:${gate.toUpperCase()}_GATE`) {
      if (gate === 'entry') this._entryReady = true;
      else                  this._exitReady  = true;
      this.emit('connected', gate);
      return;
    }

    if (line === 'SENSOR:DETECTED') {
      this.emit(`${gate}:detected`);
      return;
    }

    if (line === 'SENSOR:CLEAR') {
      this.emit(`${gate}:clear`);
      return;
    }

    if (line === 'PONG') {
      console.log(`[Serial:${gate}] Arduino ALIVE – PING OK`);
      // Đánh dấu ready nếu chưa nhận được READY:GATE (Arduino đã chạy sẵn trước khi bridge kết nối)
      if (gate === 'entry' && !this._entryReady) {
        this._entryReady = true;
        this.emit('connected', gate);
      } else if (gate === 'exit' && !this._exitReady) {
        this._exitReady = true;
        this.emit('connected', gate);
      }
      return;
    }
    // STATUS:BARRIER:* và các message khác – chỉ log
  }

  // ── Gửi lệnh xuống Arduino ───────────────────────────────────────────────
  _send(gate, cmd) {
    const port = gate === 'entry' ? this._entryPort : this._exitPort;
    if (!port || !port.isOpen) {
      console.error(`[Serial:${gate}] Port chưa mở – không gửi được lệnh "${cmd}"`);
      return;
    }
    console.log(`[Serial:${gate}] >>> ${cmd}`);
    port.write(cmd + '\n');
  }

  openBarrier(gate)  { this._send(gate, 'OPEN');  }
  closeBarrier(gate) { this._send(gate, 'CLOSE'); }
  ping(gate)         { this._send(gate, 'PING');  }

  get entryReady() { return this._entryReady; }
  get exitReady()  { return this._exitReady;  }
}

module.exports = new SerialHandler();
