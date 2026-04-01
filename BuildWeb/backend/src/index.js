require('dotenv').config();
const path    = require('path');
const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const rateLimit = require('express-rate-limit');
const { testConnection } = require('./db');
const errorHandler = require('./middleware/errorHandler');

const app = express();

// Bảo mật
app.use(helmet());
const allowedOrigins = [
  process.env.CORS_ORIGIN || 'http://localhost:3000',
  process.env.CORS_USER_ORIGIN || 'http://localhost:5175',
];
app.use(cors({
  origin: (origin, callback) => {
    // Cho phép tất cả localhost (mọi port) khi dev
    if (!origin || allowedOrigins.includes(origin) ||
        /^http:\/\/localhost:\d+$/.test(origin)) {
      return callback(null, true);
    }
    callback(new Error('Not allowed by CORS'));
  },
  credentials: true,
}));

// Rate limiting cho login
const loginLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 phút
  max: 10,
  message: { error: 'Quá nhiều lần đăng nhập, thử lại sau 15 phút' },
});

// Parse JSON (10mb để hỗ trợ upload ảnh base64)
app.use(express.json({ limit: '10mb' }));

// Phục vụ file tĩnh (ảnh khuôn mặt, biển số...)
app.use('/uploads', express.static(path.join(__dirname, '..', 'uploads')));

// Routes – Admin
app.use('/api/auth/login', loginLimiter);
app.use('/api/auth', require('./routes/auth'));
app.use('/api/dashboard', require('./routes/dashboard'));
app.use('/api/sessions', require('./routes/sessions'));
app.use('/api/users', require('./routes/users'));
app.use('/api/devices', require('./routes/devices'));
app.use('/api/event-logs', require('./routes/eventLogs'));
app.use('/api/reports', require('./routes/reports'));
app.use('/api/alerts', require('./routes/alerts'));
app.use('/api/config', require('./routes/config'));
app.use('/api/barriers', require('./routes/barriers'));

// Routes – User Web App
app.use('/api/user/auth/login', loginLimiter);
app.use('/api/user/auth', require('./routes/user/auth'));
app.use('/api/user/vehicles', require('./routes/user/vehicles'));
app.use('/api/user/wallet', require('./routes/user/wallet'));
app.use('/api/user/sessions', require('./routes/user/sessions'));
app.use('/api/user/authorizations', require('./routes/user/authorizations'));
app.use('/api/user/notifications', require('./routes/user/notifications'));
app.use('/api/user/face-images',   require('./routes/user/faceImages'));
app.use('/api/user/monthly-passes',require('./routes/user/monthlyPasses'));

// Danh sách bãi đỗ xe (public cho user)
const { pool } = require('./db');
const userAuth  = require('./middleware/userAuth');
app.get('/api/user/parking-lots', userAuth, async (req, res, next) => {
  try {
    const { rows } = await pool.query(
      'SELECT lot_id, name, address, total_capacity FROM parking_lots WHERE is_active = true ORDER BY name'
    );
    res.json(rows);
  } catch (e) { next(e); }
});

// Health check
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', time: new Date().toISOString() });
});

// 404
app.use((req, res) => {
  res.status(404).json({ error: `Route không tồn tại: ${req.method} ${req.path}` });
});

// Error handler
app.use(errorHandler);

const PORT = parseInt(process.env.PORT) || 4000;
app.listen(PORT, async () => {
  console.log(`\n🚀 Backend API đang chạy tại http://localhost:${PORT}`);
  console.log(`   Admin web (CORS): ${process.env.CORS_ORIGIN || 'http://localhost:3000'}`);
  console.log(`   User web  (CORS): ${process.env.CORS_USER_ORIGIN || 'http://localhost:5175'}`);
  await testConnection();
});
