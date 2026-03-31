-- =============================================================================
-- DỮ LIỆU MẪU – NGƯỜI DÙNG WEB APP
-- Hệ thống Bãi Đỗ Xe Thông Minh
-- Database: PostgreSQL 15+
--
-- HƯỚNG DẪN:
--   1. Chạy setup_full.sql trước (nếu chưa chạy)
--   2. Sau đó chạy file này để có dữ liệu mẫu test WebApp
--
-- Tài khoản test:
--   SĐT: 0901234567  |  Mật khẩu: User@123
--   SĐT: 0912345678  |  Mật khẩu: User@123
-- =============================================================================

-- Tạo 2 người dùng mẫu
-- password = 'User@123' (bcrypt hash)
INSERT INTO users (user_id, full_name, phone_number, password_hash, is_active, is_verified)
VALUES
    ('a1b2c3d4-0000-0000-0000-000000000001',
     'Nguyễn Văn An',
     '0901234567',
     crypt('User@123', gen_salt('bf', 12)),
     TRUE, TRUE),

    ('a1b2c3d4-0000-0000-0000-000000000002',
     'Trần Thị Bình',
     '0912345678',
     crypt('User@123', gen_salt('bf', 12)),
     TRUE, FALSE)
ON CONFLICT (phone_number) DO NOTHING;

-- Ví điện tử (trigger auto_create_wallet sẽ tạo tự động khi INSERT users;
-- nếu chưa có thì tạo thủ công)
INSERT INTO wallets (user_id, balance, low_balance_threshold)
VALUES
    ('a1b2c3d4-0000-0000-0000-000000000001', 150000.00, 50000.00),
    ('a1b2c3d4-0000-0000-0000-000000000002',  30000.00, 50000.00)
ON CONFLICT (user_id) DO UPDATE
    SET balance = EXCLUDED.balance;

-- Xe của người dùng 1
INSERT INTO vehicles (vehicle_id, user_id, license_plate, nickname, is_active)
VALUES
    ('b1b2c3d4-0000-0000-0000-000000000001',
     'a1b2c3d4-0000-0000-0000-000000000001',
     '29B1-12345', 'Xe đi làm', TRUE),

    ('b1b2c3d4-0000-0000-0000-000000000002',
     'a1b2c3d4-0000-0000-0000-000000000001',
     '30A-98765',  'Xe của vợ', TRUE)
ON CONFLICT (license_plate) DO NOTHING;

-- Xe của người dùng 2
INSERT INTO vehicles (vehicle_id, user_id, license_plate, nickname, is_active)
VALUES
    ('b1b2c3d4-0000-0000-0000-000000000003',
     'a1b2c3d4-0000-0000-0000-000000000002',
     '51F-11111', 'Xe cá nhân', TRUE)
ON CONFLICT (license_plate) DO NOTHING;

-- Lịch sử giao dịch ví người dùng 1
DO $$
DECLARE
    wid UUID;
BEGIN
    SELECT wallet_id INTO wid FROM wallets
    WHERE user_id = 'a1b2c3d4-0000-0000-0000-000000000001';

    INSERT INTO wallet_transactions
        (wallet_id, user_id, transaction_type, amount, balance_before, balance_after,
         payment_gateway, status, description)
    VALUES
        (wid, 'a1b2c3d4-0000-0000-0000-000000000001',
         'topup', 200000, 0, 200000, 'momo', 'success', 'Nạp tiền lần đầu'),

        (wid, 'a1b2c3d4-0000-0000-0000-000000000001',
         'deduct', 10000, 200000, 190000, NULL, 'success', 'Phí gửi xe 2 tiếng'),

        (wid, 'a1b2c3d4-0000-0000-0000-000000000001',
         'deduct', 5000, 190000, 185000, NULL, 'success', 'Phí gửi xe 1 tiếng'),

        (wid, 'a1b2c3d4-0000-0000-0000-000000000001',
         'topup', 100000, 185000, 285000, 'vnpay', 'success', 'Nạp thêm tiền'),

        (wid, 'a1b2c3d4-0000-0000-0000-000000000001',
         'deduct', 135000, 285000, 150000, NULL, 'success', 'Phí gửi xe nhiều lần');
END $$;

-- Lịch sử phiên gửi xe người dùng 1 (đã hoàn thành)
DO $$
DECLARE
    lot UUID;
BEGIN
    SELECT lot_id INTO lot FROM parking_lots LIMIT 1;

    INSERT INTO parking_sessions
        (vehicle_id, user_id, session_type, license_plate, lot_id,
         entry_time, exit_time, duration_minutes, fee, status)
    VALUES
        ('b1b2c3d4-0000-0000-0000-000000000001',
         'a1b2c3d4-0000-0000-0000-000000000001',
         'member', '29B1-12345', lot,
         NOW() - INTERVAL '3 days 2 hours',
         NOW() - INTERVAL '3 days',
         120, 10000, 'completed'),

        ('b1b2c3d4-0000-0000-0000-000000000001',
         'a1b2c3d4-0000-0000-0000-000000000001',
         'member', '29B1-12345', lot,
         NOW() - INTERVAL '1 day 3 hours',
         NOW() - INTERVAL '1 day 2 hours',
         60, 5000, 'completed'),

        ('b1b2c3d4-0000-0000-0000-000000000002',
         'a1b2c3d4-0000-0000-0000-000000000001',
         'member', '30A-98765', lot,
         NOW() - INTERVAL '5 hours',
         NULL, NULL, NULL, 'active');
END $$;

-- Thông báo mẫu
INSERT INTO notifications (user_id, type, title, body, is_read)
VALUES
    ('a1b2c3d4-0000-0000-0000-000000000001',
     'topup_success',
     'Nạp tiền thành công',
     'Ví của bạn vừa được nạp 200,000 VND qua MoMo. Số dư hiện tại: 200,000 VND',
     TRUE),

    ('a1b2c3d4-0000-0000-0000-000000000001',
     'vehicle_entry',
     'Xe đã vào bãi',
     'Xe 29B1-12345 đã vào bãi lúc ' || TO_CHAR(NOW() - INTERVAL '3 days 2 hours', 'HH24:MI DD/MM'),
     TRUE),

    ('a1b2c3d4-0000-0000-0000-000000000001',
     'fee_deducted',
     'Trừ phí gửi xe',
     'Phí gửi xe 29B1-12345: 10,000 VND. Số dư còn lại: 190,000 VND',
     TRUE),

    ('a1b2c3d4-0000-0000-0000-000000000001',
     'low_balance',
     'Số dư sắp hết',
     'Số dư ví của bạn chỉ còn 30,000 VND. Hãy nạp thêm để tiếp tục sử dụng dịch vụ.',
     FALSE),

    ('a1b2c3d4-0000-0000-0000-000000000001',
     'vehicle_entry',
     'Xe đã vào bãi',
     'Xe 30A-98765 đã vào bãi lúc ' || TO_CHAR(NOW() - INTERVAL '5 hours', 'HH24:MI DD/MM'),
     FALSE),

    ('a1b2c3d4-0000-0000-0000-000000000002',
     'low_balance',
     'Số dư sắp hết',
     'Số dư ví của bạn chỉ còn 30,000 VND – thấp hơn ngưỡng cảnh báo 50,000 VND.',
     FALSE);

-- =============================================================================
-- Kiểm tra kết quả:
-- SELECT u.full_name, u.phone_number, w.balance
-- FROM users u JOIN wallets w ON w.user_id = u.user_id;
--
-- SELECT license_plate, nickname FROM vehicles WHERE is_active = TRUE;
--
-- SELECT status, COUNT(*) FROM parking_sessions GROUP BY status;
-- =============================================================================
