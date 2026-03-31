const router = require('express').Router();
const { pool } = require('../../db');
const userAuth = require('../../middleware/userAuth');

// GET /api/user/vehicles
router.get('/', userAuth, async (req, res, next) => {
  try {
    const result = await pool.query(
      `SELECT vehicle_id AS id, license_plate, nickname, plate_image_path, is_active, created_at
       FROM vehicles WHERE user_id = $1 ORDER BY created_at DESC`,
      [req.user.id]
    );
    res.json(result.rows);
  } catch (err) { next(err); }
});

// POST /api/user/vehicles
router.post('/', userAuth, async (req, res, next) => {
  try {
    const { license_plate, nickname } = req.body;
    if (!license_plate) return res.status(400).json({ error: 'Thiếu biển số xe' });

    // Chuẩn hóa biển số
    const normalized = license_plate.trim().toUpperCase().replace(/\s+/g, '');

    // Kiểm tra trùng
    const existing = await pool.query(
      'SELECT vehicle_id FROM vehicles WHERE license_plate = $1',
      [normalized]
    );
    if (existing.rows.length > 0) {
      return res.status(409).json({ error: 'Biển số xe đã được đăng ký trong hệ thống' });
    }

    const result = await pool.query(
      `INSERT INTO vehicles (user_id, license_plate, nickname)
       VALUES ($1, $2, $3)
       RETURNING vehicle_id AS id, license_plate, nickname, is_active, created_at`,
      [req.user.id, normalized, nickname || null]
    );
    res.status(201).json(result.rows[0]);
  } catch (err) { next(err); }
});

// PUT /api/user/vehicles/:id
router.put('/:id', userAuth, async (req, res, next) => {
  try {
    const { nickname } = req.body;
    const result = await pool.query(
      `UPDATE vehicles SET nickname = $1, updated_at = NOW()
       WHERE vehicle_id = $2 AND user_id = $3
       RETURNING vehicle_id AS id, license_plate, nickname, is_active`,
      [nickname || null, req.params.id, req.user.id]
    );
    if (!result.rows[0]) return res.status(404).json({ error: 'Không tìm thấy xe' });
    res.json(result.rows[0]);
  } catch (err) { next(err); }
});

// DELETE /api/user/vehicles/:id
router.delete('/:id', userAuth, async (req, res, next) => {
  try {
    // Kiểm tra xe có đang trong bãi không
    const active = await pool.query(
      `SELECT session_id FROM parking_sessions
       WHERE vehicle_id = $1 AND status = 'active' LIMIT 1`,
      [req.params.id]
    );
    if (active.rows.length > 0) {
      return res.status(400).json({ error: 'Xe đang trong bãi, không thể xóa' });
    }

    const result = await pool.query(
      `UPDATE vehicles SET is_active = false, updated_at = NOW()
       WHERE vehicle_id = $1 AND user_id = $2
       RETURNING vehicle_id AS id`,
      [req.params.id, req.user.id]
    );
    if (!result.rows[0]) return res.status(404).json({ error: 'Không tìm thấy xe' });
    res.json({ message: 'Đã xóa xe' });
  } catch (err) { next(err); }
});

module.exports = router;
