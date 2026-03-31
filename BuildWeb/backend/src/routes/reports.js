const router = require('express').Router();
const auth = require('../middleware/auth');
const { pool } = require('../db');

// GET /api/reports/daily?from=&to=
router.get('/daily', auth, async (req, res, next) => {
  try {
    const from = req.query.from || new Date(Date.now() - 30 * 86400000).toISOString().split('T')[0];
    const to = req.query.to || new Date().toISOString().split('T')[0];

    const result = await pool.query(`
      SELECT *
      FROM daily_reports
      WHERE report_date BETWEEN $1 AND $2
      ORDER BY report_date DESC
    `, [from, to]);
    res.json(result.rows);
  } catch (err) {
    next(err);
  }
});

// GET /api/reports/summary?from=&to=
router.get('/summary', auth, async (req, res, next) => {
  try {
    const from = req.query.from || new Date(Date.now() - 30 * 86400000).toISOString().split('T')[0];
    const to = req.query.to || new Date().toISOString().split('T')[0];

    const result = await pool.query(`
      SELECT
        SUM(total_sessions) AS total_sessions,
        SUM(total_revenue) AS total_revenue,
        SUM(member_sessions) AS member_sessions,
        SUM(guest_sessions_count) AS guest_sessions,
        AVG(avg_duration_minutes) AS avg_duration_minutes,
        MAX(peak_hour) AS common_peak_hour
      FROM daily_reports
      WHERE report_date BETWEEN $1 AND $2
    `, [from, to]);
    res.json(result.rows[0]);
  } catch (err) {
    next(err);
  }
});

// GET /api/reports/generate-day?date= (tính toán và lưu báo cáo ngày)
router.post('/generate-day', auth, async (req, res, next) => {
  try {
    const { date } = req.body;
    const d = date || new Date().toISOString().split('T')[0];

    const stats = await pool.query(`
      SELECT
        COUNT(*) AS total_sessions,
        COUNT(*) FILTER (WHERE session_type = 'member') AS member_sessions,
        COUNT(*) FILTER (WHERE session_type = 'guest') AS guest_sessions,
        COALESCE(SUM(fee_charged), 0) AS total_revenue,
        COALESCE(AVG(EXTRACT(EPOCH FROM (exit_time - entry_time))/60), 0) AS avg_duration_minutes,
        MODE() WITHIN GROUP (ORDER BY EXTRACT(HOUR FROM entry_time)) AS peak_hour
      FROM parking_sessions
      WHERE DATE(entry_time) = $1 AND status IN ('completed', 'force_ended')
    `, [d]);

    const row = stats.rows[0];
    const lotRes = await pool.query('SELECT lot_id FROM parking_lots LIMIT 1');
    const lot_id = lotRes.rows[0]?.lot_id;
    await pool.query(`
      INSERT INTO daily_reports
        (report_date, lot_id, total_sessions, member_sessions, guest_sessions_count,
         total_revenue, avg_duration_minutes, peak_hour)
      VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
      ON CONFLICT (lot_id, report_date) DO UPDATE SET
        total_sessions = EXCLUDED.total_sessions,
        member_sessions = EXCLUDED.member_sessions,
        guest_sessions_count = EXCLUDED.guest_sessions_count,
        total_revenue = EXCLUDED.total_revenue,
        avg_duration_minutes = EXCLUDED.avg_duration_minutes,
        peak_hour = EXCLUDED.peak_hour
    `, [d, lot_id, row.total_sessions, row.member_sessions, row.guest_sessions,
        row.total_revenue, row.avg_duration_minutes, row.peak_hour]);

    res.json({ message: `Đã tạo báo cáo ngày ${d}`, ...row });
  } catch (err) {
    next(err);
  }
});

module.exports = router;
