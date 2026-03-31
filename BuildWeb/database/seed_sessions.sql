-- =============================================================================
-- DỮ LIỆU MẪU – PHIÊN GỬI XE (THÀNH VIÊN + KHÁCH VÃNG LAI)
-- Hệ thống Bãi Đỗ Xe Thông Minh
-- Database: PostgreSQL 15+
--
-- HƯỚNG DẪN:
--   1. Chạy setup_full.sql trước
--   2. Chạy seed_user_webapp.sql để có tài khoản user mẫu
--   3. Sau đó chạy file này để có dữ liệu phiên gửi xe mẫu
--
-- Dữ liệu bao gồm:
--   - parking_sessions : phiên của thành viên đã đăng ký app (active + completed)
--   - guest_sessions   : phiên của khách vãng lai (active + completed)
--   - Cập nhật current_occupancy của bãi xe
-- =============================================================================

-- ─────────────────────────────────────────────────────────────
-- 1. PHIÊN THÀNH VIÊN – ĐANG GỬI (active)
-- ─────────────────────────────────────────────────────────────
INSERT INTO parking_sessions (
    session_id, vehicle_id, user_id, session_type,
    license_plate, lot_id, entry_time, status
)
VALUES
    -- User 1 (Nguyễn Văn An) – xe 29B1-12345
    (
        'aa000001-0000-0000-0000-000000000001',
        'b1b2c3d4-0000-0000-0000-000000000001',
        'a1b2c3d4-0000-0000-0000-000000000001',
        'member',
        '29B1-12345',
        (SELECT lot_id FROM parking_lots LIMIT 1),
        NOW() - INTERVAL '1 hour 20 minutes',
        'active'
    ),
    -- User 1 (Nguyễn Văn An) – xe 30A-98765 (xe vợ đang gửi)
    (
        'aa000001-0000-0000-0000-000000000002',
        'b1b2c3d4-0000-0000-0000-000000000002',
        'a1b2c3d4-0000-0000-0000-000000000001',
        'member',
        '30A-98765',
        (SELECT lot_id FROM parking_lots LIMIT 1),
        NOW() - INTERVAL '35 minutes',
        'active'
    ),
    -- User 2 (Trần Thị Bình) – xe 51G-555.77
    (
        'aa000002-0000-0000-0000-000000000001',
        'b1b2c3d4-0000-0000-0000-000000000003',
        'a1b2c3d4-0000-0000-0000-000000000002',
        'member',
        '51G-555.77',
        (SELECT lot_id FROM parking_lots LIMIT 1),
        NOW() - INTERVAL '2 hours 5 minutes',
        'active'
    )
ON CONFLICT (session_id) DO NOTHING;

-- ─────────────────────────────────────────────────────────────
-- 2. PHIÊN THÀNH VIÊN – ĐÃ HOÀN THÀNH (completed)
-- ─────────────────────────────────────────────────────────────
INSERT INTO parking_sessions (
    session_id, vehicle_id, user_id, session_type,
    license_plate, lot_id, entry_time, exit_time,
    duration_minutes, fee, status
)
VALUES
    (
        'aa000001-0000-0000-0000-000000000010',
        'b1b2c3d4-0000-0000-0000-000000000001',
        'a1b2c3d4-0000-0000-0000-000000000001',
        'member', '29B1-12345',
        (SELECT lot_id FROM parking_lots LIMIT 1),
        NOW() - INTERVAL '1 day 3 hours',
        NOW() - INTERVAL '1 day 1 hour',
        120, 10000, 'completed'
    ),
    (
        'aa000001-0000-0000-0000-000000000011',
        'b1b2c3d4-0000-0000-0000-000000000001',
        'a1b2c3d4-0000-0000-0000-000000000001',
        'member', '29B1-12345',
        (SELECT lot_id FROM parking_lots LIMIT 1),
        NOW() - INTERVAL '2 days 2 hours',
        NOW() - INTERVAL '2 days',
        120, 10000, 'completed'
    ),
    (
        'aa000002-0000-0000-0000-000000000010',
        'b1b2c3d4-0000-0000-0000-000000000003',
        'a1b2c3d4-0000-0000-0000-000000000002',
        'member', '51G-555.77',
        (SELECT lot_id FROM parking_lots LIMIT 1),
        NOW() - INTERVAL '3 days 4 hours',
        NOW() - INTERVAL '3 days 2 hours',
        120, 10000, 'completed'
    ),
    (
        'aa000001-0000-0000-0000-000000000012',
        'b1b2c3d4-0000-0000-0000-000000000002',
        'a1b2c3d4-0000-0000-0000-000000000001',
        'member', '30A-98765',
        (SELECT lot_id FROM parking_lots LIMIT 1),
        NOW() - INTERVAL '5 days 1 hour',
        NOW() - INTERVAL '5 days',
        60, 5000, 'completed'
    )
ON CONFLICT (session_id) DO NOTHING;

-- ─────────────────────────────────────────────────────────────
-- 3. PHIÊN KHÁCH VÃNG LAI – ĐANG GỬI (active)
-- ─────────────────────────────────────────────────────────────
INSERT INTO guest_sessions (
    session_id, session_code, license_plate,
    lot_id, entry_time, status
)
VALUES
    (
        'bb000001-0000-0000-0000-000000000001',
        'GX-240001',
        '51F-123.45',
        (SELECT lot_id FROM parking_lots LIMIT 1),
        NOW() - INTERVAL '45 minutes',
        'active'
    ),
    (
        'bb000001-0000-0000-0000-000000000002',
        'GX-240002',
        '51K-678.90',
        (SELECT lot_id FROM parking_lots LIMIT 1),
        NOW() - INTERVAL '3 hours 10 minutes',
        'active'
    ),
    (
        'bb000001-0000-0000-0000-000000000003',
        'GX-240003',
        NULL,
        (SELECT lot_id FROM parking_lots LIMIT 1),
        NOW() - INTERVAL '15 minutes',
        'active'
    ),
    (
        'bb000001-0000-0000-0000-000000000004',
        'GX-240004',
        '29A-456.78',
        (SELECT lot_id FROM parking_lots LIMIT 1),
        NOW() - INTERVAL '1 hour 50 minutes',
        'active'
    ),
    (
        'bb000001-0000-0000-0000-000000000005',
        'GX-240005',
        '51H-999.00',
        (SELECT lot_id FROM parking_lots LIMIT 1),
        NOW() - INTERVAL '25 minutes',
        'active'
    )
ON CONFLICT (session_id) DO NOTHING;

-- ─────────────────────────────────────────────────────────────
-- 4. PHIÊN KHÁCH VÃNG LAI – ĐÃ HOÀN THÀNH (completed)
-- ─────────────────────────────────────────────────────────────
INSERT INTO guest_sessions (
    session_id, session_code, license_plate,
    lot_id, entry_time, exit_time,
    duration_minutes, fee, payment_status, status
)
VALUES
    (
        'bb000001-0000-0000-0000-000000000010',
        'GX-230101', '51F-111.22',
        (SELECT lot_id FROM parking_lots LIMIT 1),
        NOW() - INTERVAL '1 day 2 hours',
        NOW() - INTERVAL '1 day',
        120, 10000, 'paid', 'completed'
    ),
    (
        'bb000001-0000-0000-0000-000000000011',
        'GX-230102', '30F-333.44',
        (SELECT lot_id FROM parking_lots LIMIT 1),
        NOW() - INTERVAL '2 days 3 hours',
        NOW() - INTERVAL '2 days 1 hour',
        120, 10000, 'paid', 'completed'
    ),
    (
        'bb000001-0000-0000-0000-000000000012',
        'GX-230103', NULL,
        (SELECT lot_id FROM parking_lots LIMIT 1),
        NOW() - INTERVAL '2 days 30 minutes',
        NOW() - INTERVAL '2 days',
        30, 2000, 'paid', 'completed'
    ),
    (
        'bb000001-0000-0000-0000-000000000013',
        'GX-230104', '51G-777.88',
        (SELECT lot_id FROM parking_lots LIMIT 1),
        NOW() - INTERVAL '4 days 2 hours',
        NOW() - INTERVAL '4 days',
        120, 10000, 'pending', 'completed'
    )
ON CONFLICT (session_id) DO NOTHING;

-- ─────────────────────────────────────────────────────────────
-- 5. CẬP NHẬT SỐ XE TRONG BÃI (3 member + 5 guest = 8)
-- ─────────────────────────────────────────────────────────────
UPDATE parking_lots
SET current_occupancy = (
    SELECT COUNT(*) FROM (
        SELECT session_id FROM parking_sessions WHERE status = 'active' AND lot_id = parking_lots.lot_id
        UNION ALL
        SELECT session_id FROM guest_sessions   WHERE status = 'active' AND lot_id = parking_lots.lot_id
    ) t
);
