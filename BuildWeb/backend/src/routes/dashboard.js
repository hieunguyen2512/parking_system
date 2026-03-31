const router = require('express').Router();
const auth = require('../middleware/auth');
const { pool } = require('../db');

// GET /api/dashboard/stats
router.get('/stats', auth, async (req, res, next) => {
  try {
    const [lotRes, activeRes, todayRes, deviceRes, alertRes] = await Promise.all([
      pool.query('SELECT total_capacity, current_occupancy AS occupied_spots FROM parking_lots LIMIT 1'),
      pool.query(`SELECT COUNT(*) AS count FROM parking_sessions WHERE status = 'active'`),
      pool.query(`
        SELECT
          COALESCE(SUM(fee), 0) AS revenue,
          COUNT(*) AS total_sessions
        FROM parking_sessions
        WHERE DATE(entry_time) = CURRENT_DATE AND status = 'completed'
      `),
      pool.query(`
        SELECT
          COUNT(*) FILTER (WHERE status = 'online') AS online,
          COUNT(*) FILTER (WHERE status != 'online') AS offline
        FROM devices
      `),
      pool.query(`SELECT COUNT(*) AS count FROM system_alerts WHERE status = 'unresolved'`),
    ]);

    const lot = lotRes.rows[0] || { total_capacity: 0, occupied_spots: 0 };
    res.json({
      capacity: parseInt(lot.total_capacity),
      occupied: parseInt(lot.occupied_spots),
      available: parseInt(lot.total_capacity) - parseInt(lot.occupied_spots),
      activeSessions: parseInt(activeRes.rows[0].count),
      todayRevenue: parseFloat(todayRes.rows[0].revenue),
      todaySessions: parseInt(todayRes.rows[0].total_sessions),
      devicesOnline: parseInt(deviceRes.rows[0].online),
      devicesOffline: parseInt(deviceRes.rows[0].offline),
      unresolvedAlerts: parseInt(alertRes.rows[0].count),
    });
  } catch (err) {
    next(err);
  }
});

// GET /api/dashboard/hourly-traffic?date=YYYY-MM-DD
router.get('/hourly-traffic', auth, async (req, res, next) => {
  try {
    const date = req.query.date || new Date().toISOString().split('T')[0];
    const result = await pool.query(`
      SELECT
        EXTRACT(HOUR FROM entry_time)::int AS hour,
        COUNT(*) AS entries
      FROM parking_sessions
      WHERE DATE(entry_time) = $1
      GROUP BY hour
      ORDER BY hour
    `, [date]);

    const hours = Array.from({ length: 24 }, (_, i) => ({ hour: i, entries: 0 }));
    result.rows.forEach(r => { hours[r.hour].entries = parseInt(r.entries); });
    res.json(hours);
  } catch (err) {
    next(err);
  }
});

// GET /api/dashboard/active-sessions (top 10)
router.get('/active-sessions', auth, async (req, res, next) => {
  try {
    const result = await pool.query(`
      SELECT
        ps.session_id AS id, ps.entry_time,
        ps.license_plate AS vehicle_plate,
        ps.entry_composite_image_path AS entry_image_url,
        ps.session_type,
        u.full_name AS user_name,
        u.phone_number AS user_phone,
        'member' AS session_kind
      FROM parking_sessions ps
      LEFT JOIN users u ON ps.user_id = u.user_id
      WHERE ps.status = 'active'

      UNION ALL

      SELECT
        gs.session_id AS id, gs.entry_time,
        gs.license_plate AS vehicle_plate,
        gs.entry_composite_image_path AS entry_image_url,
        'guest' AS session_type,
        NULL AS user_name,
        NULL AS user_phone,
        'guest' AS session_kind
      FROM guest_sessions gs
      WHERE gs.status = 'active'

      ORDER BY entry_time DESC
      LIMIT 20
    `);
    res.json(result.rows);
  } catch (err) {
    next(err);
  }
});

module.exports = router;
