const router = require('express').Router();
const auth = require('../middleware/auth');
const { pool } = require('../db');

// GET /api/event-logs?type=&search=&page=1&limit=50&from=&to=
router.get('/', auth, async (req, res, next) => {
  try {
    const { type, search = '', page = 1, limit = 50, from, to } = req.query;
    const params = [];
    const conditions = [];

    if (type) {
      params.push(type);
      conditions.push(`el.event_type = $${params.length}`);
    }
    if (from) {
      params.push(from);
      conditions.push(`el.created_at >= $${params.length}`);
    }
    if (to) {
      params.push(to);
      conditions.push(`el.created_at <= $${params.length}`);
    }
    if (search) {
      params.push(`%${search}%`);
      conditions.push(`(el.description ILIKE $${params.length} OR el.license_plate ILIKE $${params.length})`);
    }

    const where = conditions.length ? 'WHERE ' + conditions.join(' AND ') : '';
    const offset = (parseInt(page) - 1) * parseInt(limit);

    const countRes = await pool.query(`SELECT COUNT(*) FROM event_logs el ${where}`, params);
    params.push(parseInt(limit), offset);

    const dataRes = await pool.query(`
      SELECT
        el.*,
        a.username AS admin_username
      FROM event_logs el
      LEFT JOIN admins a ON a.id = el.admin_id
      ${where}
      ORDER BY el.created_at DESC
      LIMIT $${params.length - 1} OFFSET $${params.length}
    `, params);

    res.json({
      total: parseInt(countRes.rows[0].count),
      page: parseInt(page),
      limit: parseInt(limit),
      data: dataRes.rows,
    });
  } catch (err) {
    next(err);
  }
});

module.exports = router;
