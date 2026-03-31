-- =============================================================================
-- SETUP HOÀN CHỈNH – Hệ thống Bãi Đỗ Xe Thông Minh
-- Database: PostgreSQL 15+
-- File này gộp toàn bộ schema + dữ liệu mặc định ban đầu
--
-- HƯỚNG DẪN IMPORT VÀO pgAdmin 4:
--   1. Mở pgAdmin 4 → tạo database mới tên "parking_system"
--   2. Cài extension pgvector: trong psql chạy "CREATE EXTENSION vector;"
--      (cần cài pgvector cho PostgreSQL trước: https://github.com/pgvector/pgvector)
--   3. Click chuột phải vào database → Query Tool → mở file này → F5
--   4. Sau khi import xong:
--      - Cập nhật file backend/.env với DB_PASSWORD của bạn
--      - Tài khoản admin mặc định: admin / Admin@123  (đổi ngay sau khi đăng nhập)
-- =============================================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- dùng để hash mật khẩu trong seed data
-- NOTE: pgvector KHÔNG bắt buộc. Embedding lưu dưới dạng REAL[] thay vector(512).
-- Việc tính Cosine Similarity thực hiện trong Python (ArcFace module) trước khi ghi DB.


-- =============================================================================
-- PHẦN 1 – BẢNG PHỤC VỤ NGƯỜI DÙNG
-- =============================================================================

-- 1. TÀI KHOẢN NGƯỜI DÙNG
CREATE TABLE users (
    user_id         UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    full_name       VARCHAR(100)    NOT NULL,
    phone_number    VARCHAR(15)     NOT NULL UNIQUE,
    email           VARCHAR(100)    UNIQUE,
    password_hash   VARCHAR(255)    NOT NULL,
    avatar_path     VARCHAR(500),
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    is_verified     BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_users_phone ON users (phone_number);

-- 2. REFRESH TOKEN
CREATE TABLE refresh_tokens (
    token_id        UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID            NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    token_hash      VARCHAR(255)    NOT NULL UNIQUE,
    device_info     VARCHAR(200),
    ip_address      INET,
    expires_at      TIMESTAMPTZ     NOT NULL,
    revoked_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_refresh_tokens_user ON refresh_tokens (user_id);

-- 3. EMBEDDING KHUÔN MẶT (ArcFace 512 chiều)
CREATE TABLE face_embeddings (
    embedding_id    UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID            NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    embedding       REAL[]          NOT NULL,              -- ArcFace 512-dim, lưu dưới dạng mảng float
    face_image_path VARCHAR(500),
    model_version   VARCHAR(50)     NOT NULL DEFAULT 'arcface-r100-v1',
    is_primary      BOOLEAN         NOT NULL DEFAULT TRUE,
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_face_embeddings_user ON face_embeddings (user_id);

-- 4. PHƯƠNG TIỆN (XE MÁY)
CREATE TABLE vehicles (
    vehicle_id      UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID            NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    license_plate   VARCHAR(20)     NOT NULL UNIQUE,
    plate_image_path VARCHAR(500),
    nickname        VARCHAR(50),
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_vehicles_user          ON vehicles (user_id);
CREATE INDEX idx_vehicles_license_plate ON vehicles (license_plate);

-- 5. ỦY QUYỀN LẤY XE
CREATE TABLE authorizations (
    auth_id             UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    vehicle_id          UUID            NOT NULL REFERENCES vehicles(vehicle_id) ON DELETE CASCADE,
    owner_user_id       UUID            NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    delegate_name       VARCHAR(100),
    delegate_face_image VARCHAR(500)    NOT NULL,
    delegate_embedding  REAL[]          NOT NULL,          -- ArcFace 512-dim mảng float
    auth_type           VARCHAR(20)     NOT NULL CHECK (auth_type IN ('once', 'daily', 'permanent')),
    valid_from          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    valid_until         TIMESTAMPTZ,
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,
    is_consumed         BOOLEAN         NOT NULL DEFAULT FALSE,
    consumed_at         TIMESTAMPTZ,
    model_version       VARCHAR(50)     NOT NULL DEFAULT 'arcface-r100-v1',
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_auth_vehicle ON authorizations (vehicle_id);
CREATE INDEX idx_auth_owner   ON authorizations (owner_user_id);
CREATE INDEX idx_auth_active  ON authorizations (vehicle_id, is_active, auth_type);

-- 6. VÍ ĐIỆN TỬ
CREATE TABLE wallets (
    wallet_id               UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id                 UUID            NOT NULL UNIQUE REFERENCES users(user_id) ON DELETE CASCADE,
    balance                 NUMERIC(15,2)   NOT NULL DEFAULT 0.00 CHECK (balance >= 0),
    low_balance_threshold   NUMERIC(15,2)   NOT NULL DEFAULT 50000.00,
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- 7. GIAO DỊCH VÍ ĐIỆN TỬ
CREATE TABLE wallet_transactions (
    transaction_id          UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    wallet_id               UUID            NOT NULL REFERENCES wallets(wallet_id),
    user_id                 UUID            NOT NULL REFERENCES users(user_id),
    transaction_type        VARCHAR(20)     NOT NULL CHECK (transaction_type IN (
                                                'topup', 'deduct', 'withdraw', 'refund'
                                            )),
    amount                  NUMERIC(15,2)   NOT NULL CHECK (amount > 0),
    balance_before          NUMERIC(15,2)   NOT NULL,
    balance_after           NUMERIC(15,2)   NOT NULL,
    payment_gateway         VARCHAR(30)     CHECK (payment_gateway IN
                                                ('vnpay', 'momo', 'zalopay', 'bank_transfer', 'system')),
    gateway_transaction_id  VARCHAR(200),
    gateway_reference_code  VARCHAR(200),
    gateway_response_code   VARCHAR(20),
    parking_session_id      UUID,
    status                  VARCHAR(20)     NOT NULL DEFAULT 'pending' CHECK (status IN (
                                                'pending', 'success', 'failed', 'cancelled'
                                            )),
    description             TEXT,
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_wallet_tx_user    ON wallet_transactions (user_id, created_at DESC);
CREATE INDEX idx_wallet_tx_wallet  ON wallet_transactions (wallet_id, created_at DESC);
CREATE INDEX idx_wallet_tx_gateway ON wallet_transactions (gateway_transaction_id) WHERE gateway_transaction_id IS NOT NULL;
CREATE INDEX idx_wallet_tx_status  ON wallet_transactions (status) WHERE status = 'pending';

-- 8. PHIÊN GỬI XE – THÀNH VIÊN
CREATE TABLE parking_sessions (
    session_id                  UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    vehicle_id                  UUID            NOT NULL REFERENCES vehicles(vehicle_id),
    user_id                     UUID            NOT NULL REFERENCES users(user_id),
    auth_id                     UUID            REFERENCES authorizations(auth_id),
    session_type                VARCHAR(20)     NOT NULL DEFAULT 'member' CHECK (session_type IN ('member', 'authorized')),
    license_plate               VARCHAR(20)     NOT NULL,
    lot_id                      UUID            NOT NULL,
    entry_time                  TIMESTAMPTZ     NOT NULL,
    exit_time                   TIMESTAMPTZ,
    duration_minutes            INTEGER         CHECK (duration_minutes >= 0),
    entry_face_image_path       VARCHAR(500),
    entry_plate_image_path      VARCHAR(500),
    entry_composite_image_path  VARCHAR(500),
    exit_face_image_path        VARCHAR(500),
    exit_plate_image_path       VARCHAR(500),
    exit_composite_image_path   VARCHAR(500),
    fee                         NUMERIC(10,2)   CHECK (fee >= 0),
    wallet_transaction_id       UUID            REFERENCES wallet_transactions(transaction_id),
    status                      VARCHAR(20)     NOT NULL DEFAULT 'active' CHECK (status IN (
                                                    'active', 'completed', 'abnormal', 'force_ended'
                                                )),
    abnormal_reason             TEXT,
    force_ended_by              UUID,           -- admin_id người kết thúc cưỡng bức
    force_end_reason            TEXT,
    is_synced                   BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at                  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_parking_sessions_user    ON parking_sessions (user_id, entry_time DESC);
CREATE INDEX idx_parking_sessions_vehicle ON parking_sessions (vehicle_id, entry_time DESC);
CREATE INDEX idx_parking_sessions_plate   ON parking_sessions (license_plate);
CREATE INDEX idx_parking_sessions_active  ON parking_sessions (status, lot_id) WHERE status = 'active';
CREATE INDEX idx_parking_sessions_synced  ON parking_sessions (is_synced) WHERE is_synced = FALSE;

-- 9. PHIÊN GỬI XE – KHÁCH VÃNG LAI
CREATE TABLE guest_sessions (
    session_id                  UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_code                VARCHAR(20)     NOT NULL UNIQUE,
    license_plate               VARCHAR(20),
    lot_id                      UUID            NOT NULL,
    entry_time                  TIMESTAMPTZ     NOT NULL,
    exit_time                   TIMESTAMPTZ,
    duration_minutes            INTEGER         CHECK (duration_minutes >= 0),
    entry_face_image_path       VARCHAR(500),
    entry_plate_image_path      VARCHAR(500),
    entry_composite_image_path  VARCHAR(500),
    exit_composite_image_path   VARCHAR(500),
    fee                         NUMERIC(10,2)   CHECK (fee >= 0),
    payment_gateway             VARCHAR(30)     CHECK (payment_gateway IN ('vnpay', 'momo', 'zalopay', 'cash_qr')),
    gateway_transaction_id      VARCHAR(200),
    payment_status              VARCHAR(20)     NOT NULL DEFAULT 'pending' CHECK (payment_status IN (
                                                    'pending', 'paid', 'failed'
                                                )),
    paid_at                     TIMESTAMPTZ,
    status                      VARCHAR(20)     NOT NULL DEFAULT 'active' CHECK (status IN (
                                                    'active', 'completed', 'abnormal'
                                                )),
    abnormal_reason             TEXT,
    is_synced                   BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at                  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_guest_sessions_code   ON guest_sessions (session_code);
CREATE INDEX idx_guest_sessions_plate  ON guest_sessions (license_plate) WHERE license_plate IS NOT NULL;
CREATE INDEX idx_guest_sessions_active ON guest_sessions (status, lot_id) WHERE status = 'active';
CREATE INDEX idx_guest_sessions_synced ON guest_sessions (is_synced) WHERE is_synced = FALSE;

-- 10. THÔNG BÁO ĐẨY
CREATE TABLE notifications (
    notification_id UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID            NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    type            VARCHAR(50)     NOT NULL CHECK (type IN (
                        'vehicle_entry', 'vehicle_exit', 'fee_deducted', 'topup_success',
                        'low_balance', 'withdraw_success', 'session_abnormal', 'auth_granted', 'system'
                    )),
    title           VARCHAR(200)    NOT NULL,
    body            TEXT            NOT NULL,
    data            JSONB,
    is_read         BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_notifications_user   ON notifications (user_id, created_at DESC);
CREATE INDEX idx_notifications_unread ON notifications (user_id, is_read) WHERE is_read = FALSE;

-- 11. FCM TOKEN
CREATE TABLE fcm_tokens (
    token_id    UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID        NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    token       TEXT        NOT NULL,
    device_type VARCHAR(10) CHECK (device_type IN ('android', 'ios', 'web')),
    device_info VARCHAR(200),
    is_active   BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, token)
);
CREATE INDEX idx_fcm_tokens_user ON fcm_tokens (user_id) WHERE is_active = TRUE;


-- =============================================================================
-- PHẦN 2 – BẢNG PHỤC VỤ ADMIN
-- =============================================================================

-- 12. TÀI KHOẢN QUẢN TRỊ VIÊN
CREATE TABLE admins (
    admin_id        UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    username        VARCHAR(50)     NOT NULL UNIQUE,
    password_hash   VARCHAR(255)    NOT NULL,
    full_name       VARCHAR(100)    NOT NULL,
    email           VARCHAR(100)    UNIQUE,
    role            VARCHAR(20)     NOT NULL DEFAULT 'operator' CHECK (role IN (
                                        'superadmin', 'admin', 'operator'
                                    )),
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- 13. PHIÊN ĐĂNG NHẬP ADMIN
CREATE TABLE admin_sessions (
    session_id  UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    admin_id    UUID            NOT NULL REFERENCES admins(admin_id) ON DELETE CASCADE,
    token_hash  VARCHAR(255)    NOT NULL UNIQUE,
    ip_address  INET,
    user_agent  VARCHAR(500),
    expires_at  TIMESTAMPTZ     NOT NULL DEFAULT (NOW() + INTERVAL '8 hours'),
    revoked_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_admin_sessions_admin ON admin_sessions (admin_id);

-- 14. BÃI ĐỖ XE
CREATE TABLE parking_lots (
    lot_id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                VARCHAR(200) NOT NULL,
    address             TEXT,
    total_capacity      INTEGER     NOT NULL CHECK (total_capacity > 0),
    current_occupancy   INTEGER     NOT NULL DEFAULT 0 CHECK (current_occupancy >= 0),
    phone               VARCHAR(20),
    email               VARCHAR(100),
    is_active           BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_occupancy_not_exceed_capacity CHECK (current_occupancy <= total_capacity)
);

-- 15. CẤU HÌNH GIÁ GỬI XE
CREATE TABLE pricing_configs (
    config_id           UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    lot_id              UUID            NOT NULL REFERENCES parking_lots(lot_id) ON DELETE CASCADE,
    time_slot_name      VARCHAR(50)     NOT NULL,
    start_hour          SMALLINT        NOT NULL CHECK (start_hour BETWEEN 0 AND 23),
    end_hour            SMALLINT        NOT NULL CHECK (end_hour BETWEEN 0 AND 23),
    price_per_hour      NUMERIC(10,2)   NOT NULL CHECK (price_per_hour >= 0),
    minimum_fee         NUMERIC(10,2)   NOT NULL DEFAULT 0,
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_pricing_lot ON pricing_configs (lot_id, is_active);

-- 16. CẤU HÌNH HỆ THỐNG (key-value)
CREATE TABLE system_configs (
    config_key      VARCHAR(100)    PRIMARY KEY,
    config_value    TEXT            NOT NULL,
    data_type       VARCHAR(20)     NOT NULL DEFAULT 'string' CHECK (data_type IN (
                                        'string', 'integer', 'decimal', 'boolean', 'json'
                                    )),
    description     TEXT,
    updated_by      UUID            REFERENCES admins(admin_id),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- 17. THIẾT BỊ TẠI BÃI XE (Arduino USB Serial – không dùng ESP)
CREATE TABLE devices (
    device_id       UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    lot_id          UUID            NOT NULL REFERENCES parking_lots(lot_id),
    device_name     VARCHAR(100)    NOT NULL,
    device_type     VARCHAR(30)     NOT NULL CHECK (device_type IN (
                                        'camera_face', 'camera_plate', 'barrier',
                                        'sensor', 'led', 'speaker', 'arduino', 'computer'
                                    )),
    lane            VARCHAR(10)     CHECK (lane IN ('entry', 'exit', 'both')),
    ip_address      INET,
    serial_port     VARCHAR(30),    -- Cổng COM Arduino, VD: "COM3"
    baud_rate       INTEGER         DEFAULT 9600,
    status          VARCHAR(20)     NOT NULL DEFAULT 'offline' CHECK (status IN (
                                        'online', 'offline', 'error', 'maintenance'
                                    )),
    last_heartbeat  TIMESTAMPTZ,
    notes           TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_devices_lot  ON devices (lot_id);
CREATE INDEX idx_devices_type ON devices (device_type);

-- 18. LỊCH SỬ TRẠNG THÁI THIẾT BỊ
CREATE TABLE device_status_logs (
    log_id      UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    device_id   UUID        NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
    status      VARCHAR(20) NOT NULL,
    message     TEXT,
    logged_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_device_status_logs_device ON device_status_logs (device_id, logged_at DESC);

-- 19. LOG SỰ KIỆN (EVENT LOG – append-only)
CREATE TABLE event_logs (
    event_id        UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    lot_id          UUID            REFERENCES parking_lots(lot_id),   -- nullable: log hệ thống không có lot
    event_type      VARCHAR(60)     NOT NULL,
    session_id      UUID,
    session_kind    VARCHAR(10)     CHECK (session_kind IN ('member', 'guest')),
    user_id         UUID,
    admin_id        UUID            REFERENCES admins(admin_id),
    device_id       UUID            REFERENCES devices(device_id),
    license_plate   VARCHAR(20),
    description     TEXT,
    metadata        JSONB,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_event_logs_lot_time ON event_logs (lot_id, created_at DESC);
CREATE INDEX idx_event_logs_type     ON event_logs (event_type, created_at DESC);
CREATE INDEX idx_event_logs_user     ON event_logs (user_id, created_at DESC) WHERE user_id IS NOT NULL;
CREATE INDEX idx_event_logs_plate    ON event_logs (license_plate) WHERE license_plate IS NOT NULL;
CREATE INDEX idx_event_logs_session  ON event_logs (session_id) WHERE session_id IS NOT NULL;

-- 20. CẢNH BÁO HỆ THỐNG
CREATE TABLE system_alerts (
    alert_id            UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    lot_id              UUID            REFERENCES parking_lots(lot_id),
    alert_type          VARCHAR(50)     NOT NULL CHECK (alert_type IN (
                            'device_offline', 'arduino_disconnected', 'session_abnormal',
                            'lot_full', 'low_balance_user', 'sync_failed',
                            'auth_anomaly', 'barrier_stuck', 'camera_error'
                        )),
    severity            VARCHAR(10)     NOT NULL DEFAULT 'warning' CHECK (severity IN ('info', 'warning', 'critical')),
    title               VARCHAR(200)    NOT NULL,
    description         TEXT,
    related_device_id   UUID            REFERENCES devices(device_id),
    related_user_id     UUID,
    related_session_id  UUID,
    status              VARCHAR(20)     NOT NULL DEFAULT 'unresolved' CHECK (status IN ('unresolved', 'resolved', 'ignored')),
    is_resolved         BOOLEAN         GENERATED ALWAYS AS (status != 'unresolved') STORED,
    resolved_by         UUID            REFERENCES admins(admin_id),
    resolved_at         TIMESTAMPTZ,
    resolution_note     TEXT,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_system_alerts_unresolved ON system_alerts (status, severity, created_at DESC)
    WHERE status = 'unresolved';
CREATE INDEX idx_system_alerts_lot ON system_alerts (lot_id, created_at DESC);

-- 21. MỞ BARRIER THỦ CÔNG (AUDIT LOG)
CREATE TABLE manual_overrides (
    override_id             UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    lot_id                  UUID        REFERENCES parking_lots(lot_id),  -- nullable
    admin_id                UUID        NOT NULL REFERENCES admins(admin_id),
    device_id               UUID        REFERENCES devices(device_id),
    action                  VARCHAR(50) NOT NULL CHECK (action IN (
                                            'open_barrier', 'close_barrier',
                                            'end_session', 'unlock_account', 'force_exit'
                                        )),
    reason                  TEXT        NOT NULL,
    related_session_id      UUID,
    related_license_plate   VARCHAR(20),
    ip_address              INET,
    executed_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_manual_overrides_admin ON manual_overrides (admin_id, executed_at DESC);

-- 22. HÀNG CHỜ ĐỒNG BỘ OFFLINE
CREATE TABLE sync_queue (
    queue_id        UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    lot_id          UUID        REFERENCES parking_lots(lot_id),
    entity_type     VARCHAR(50) NOT NULL CHECK (entity_type IN (
                        'parking_session', 'guest_session', 'wallet_transaction',
                        'event_log', 'device_status', 'system_alert'
                    )),
    entity_id       UUID        NOT NULL,
    operation       VARCHAR(10) NOT NULL CHECK (operation IN ('insert', 'update', 'delete')),
    payload         JSONB       NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN (
                                    'pending', 'syncing', 'synced', 'failed'
                                )),
    retry_count     INTEGER     NOT NULL DEFAULT 0,
    last_error      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    synced_at       TIMESTAMPTZ
);
CREATE INDEX idx_sync_queue_pending ON sync_queue (status, created_at ASC)
    WHERE status IN ('pending', 'failed');

-- 23. BÁO CÁO THEO NGÀY
CREATE TABLE daily_reports (
    report_id               UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    lot_id                  UUID            NOT NULL REFERENCES parking_lots(lot_id),
    report_date             DATE            NOT NULL,
    total_sessions          INTEGER         NOT NULL DEFAULT 0,
    member_sessions         INTEGER         NOT NULL DEFAULT 0,
    guest_sessions_count    INTEGER         NOT NULL DEFAULT 0,
    total_revenue           NUMERIC(15,2)   NOT NULL DEFAULT 0,
    member_revenue          NUMERIC(15,2)   NOT NULL DEFAULT 0,
    guest_revenue           NUMERIC(15,2)   NOT NULL DEFAULT 0,
    auth_success_count      INTEGER         NOT NULL DEFAULT 0,
    auth_failed_count       INTEGER         NOT NULL DEFAULT 0,
    auth_fallback_guest_count INTEGER        NOT NULL DEFAULT 0,
    avg_duration_minutes    NUMERIC(6,2)    NOT NULL DEFAULT 0,
    hourly_occupancy        JSONB,
    peak_hour               SMALLINT        CHECK (peak_hour BETWEEN 0 AND 23),
    generated_at            TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    UNIQUE (lot_id, report_date)
);
CREATE INDEX idx_daily_reports_lot_date ON daily_reports (lot_id, report_date DESC);

-- 24. LỊCH SỬ XUẤT BÁO CÁO
CREATE TABLE report_exports (
    export_id       UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    admin_id        UUID        NOT NULL REFERENCES admins(admin_id),
    lot_id          UUID        REFERENCES parking_lots(lot_id),
    report_type     VARCHAR(30) NOT NULL,
    date_from       DATE,
    date_to         DATE,
    file_format     VARCHAR(10) NOT NULL CHECK (file_format IN ('csv', 'xlsx', 'pdf')),
    file_path       VARCHAR(500),
    file_size_bytes BIGINT,
    status          VARCHAR(20) NOT NULL DEFAULT 'processing' CHECK (status IN (
                                    'processing', 'completed', 'failed'
                                )),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);


-- =============================================================================
-- PHẦN 3 – TRIGGERS
-- =============================================================================

CREATE OR REPLACE FUNCTION trigger_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

-- updated_at cho tất cả bảng có cột đó
DO $$
DECLARE tbl TEXT;
BEGIN
    FOREACH tbl IN ARRAY ARRAY[
        'users','vehicles','wallets','wallet_transactions',
        'parking_sessions','guest_sessions','fcm_tokens',
        'admins','parking_lots','pricing_configs','devices'
    ] LOOP
        EXECUTE format(
            'CREATE TRIGGER set_updated_at_%I BEFORE UPDATE ON %I
             FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at()', tbl, tbl);
    END LOOP;
END $$;

-- Tự động tạo ví khi người dùng đăng ký
CREATE OR REPLACE FUNCTION trigger_create_wallet_for_new_user()
RETURNS TRIGGER AS $$
BEGIN INSERT INTO wallets (user_id) VALUES (NEW.user_id); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER auto_create_wallet
    AFTER INSERT ON users
    FOR EACH ROW EXECUTE FUNCTION trigger_create_wallet_for_new_user();

-- Ghi log khi trạng thái thiết bị thay đổi
CREATE OR REPLACE FUNCTION trigger_log_device_status_change()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO device_status_logs (device_id, status, message)
        VALUES (NEW.device_id, NEW.status,
                'Trạng thái thay đổi từ ' || COALESCE(OLD.status, 'unknown') || ' → ' || NEW.status);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER log_device_status
    AFTER UPDATE ON devices
    FOR EACH ROW EXECUTE FUNCTION trigger_log_device_status_change();


-- =============================================================================
-- PHẦN 4 – VIEWS
-- =============================================================================

CREATE VIEW v_lot_overview AS
SELECT
    pl.lot_id, pl.name AS lot_name,
    pl.total_capacity, pl.current_occupancy,
    pl.total_capacity - pl.current_occupancy            AS available_slots,
    ROUND(pl.current_occupancy * 100.0 / NULLIF(pl.total_capacity, 0), 1) AS occupancy_percent,
    (SELECT COUNT(*) FROM devices d
     WHERE d.lot_id = pl.lot_id AND d.status != 'online')    AS offline_device_count,
    (SELECT COUNT(*) FROM system_alerts sa
     WHERE sa.lot_id = pl.lot_id AND sa.status = 'unresolved') AS open_alerts,
    pl.is_active
FROM parking_lots pl;

CREATE VIEW v_active_sessions AS
SELECT session_id, lot_id, license_plate, session_type, entry_time,
    EXTRACT(EPOCH FROM (NOW() - entry_time)) / 60 AS duration_minutes_so_far,
    user_id, 'member' AS session_kind
FROM parking_sessions WHERE status = 'active'
UNION ALL
SELECT session_id, lot_id, license_plate, 'guest' AS session_type, entry_time,
    EXTRACT(EPOCH FROM (NOW() - entry_time)) / 60 AS duration_minutes_so_far,
    NULL AS user_id, 'guest' AS session_kind
FROM guest_sessions WHERE status = 'active';

CREATE VIEW v_device_status AS
SELECT d.device_id, pl.name AS lot_name, d.device_name, d.device_type,
    d.lane, d.serial_port, d.ip_address, d.status, d.last_heartbeat,
    EXTRACT(EPOCH FROM (NOW() - d.last_heartbeat)) / 60 AS minutes_since_heartbeat
FROM devices d
JOIN parking_lots pl ON pl.lot_id = d.lot_id
ORDER BY d.lot_id, d.device_type;


-- =============================================================================
-- PHẦN 5 – DỮ LIỆU MẶC ĐỊNH (SEED DATA)
-- =============================================================================

-- Cấu hình hệ thống mặc định
INSERT INTO system_configs (config_key, config_value, data_type, description) VALUES
    ('low_balance_default_threshold',   '50000',    'decimal',  'Ngưỡng số dư thấp mặc định (VND)'),
    ('max_parking_hours_alert',         '24',       'integer',  'Số giờ tối đa trước khi đánh dấu phiên bất thường'),
    ('face_match_threshold',            '0.6',      'decimal',  'Ngưỡng Cosine Similarity tối thiểu để chấp nhận khuôn mặt'),
    ('max_verify_attempts',             '3',        'integer',  'Số lần thử nhận diện tối đa trước khi chuyển khách vãng lai'),
    ('camera_capture_timeout_ms',       '5000',     'integer',  'Timeout chụp ảnh 2 camera (ms)'),
    ('barrier_auto_close_delay_ms',     '3000',     'integer',  'Thời gian delay đóng barrier sau khi xe qua (ms)'),
    ('offline_sync_retry_interval_s',   '30',       'integer',  'Chu kỳ thử đồng bộ lại khi có mạng (giây)'),
    ('guest_session_code_prefix',       'GX',       'string',   'Tiền tố mã phiên khách vãng lai');

-- Bãi đỗ xe mẫu
INSERT INTO parking_lots (name, address, total_capacity, phone, email)
VALUES ('Bãi Xe Thông Minh – Trường ĐH Hàng Hải Việt Nam', '484 Lạch Tray, Đổng Quốc Bình, Lê Chân, Hải Phòng', 100,
        '0225-3829-250', 'baixe@vimaru.edu.vn');

-- Bảng giá (liên kết với bãi vừa tạo)
INSERT INTO pricing_configs (lot_id, time_slot_name, start_hour, end_hour, price_per_hour, minimum_fee)
SELECT lot_id, 'Ban ngày',  6,  22, 5000,  2000 FROM parking_lots LIMIT 1;

INSERT INTO pricing_configs (lot_id, time_slot_name, start_hour, end_hour, price_per_hour, minimum_fee)
SELECT lot_id, 'Ban đêm',  22,  6, 3000,  2000 FROM parking_lots LIMIT 1;

-- Admin mặc định: username=admin, password=Admin@123
-- ⚠️  ĐỔI MẬT KHẨU NGAY SAU KHI ĐĂNG NHẬP LẦN ĐẦU
INSERT INTO admins (username, password_hash, full_name, email, role)
VALUES (
    'admin',
    crypt('Admin@123', gen_salt('bf', 12)),
    'Quản trị viên',
    'admin@parking.local',
    'superadmin'
);

-- Thiết bị mẫu (liên kết với bãi)
INSERT INTO devices (lot_id, device_name, device_type, lane, serial_port, baud_rate)
SELECT lot_id, 'Arduino - Cổng vào', 'arduino', 'entry', 'COM3', 9600 FROM parking_lots LIMIT 1;

INSERT INTO devices (lot_id, device_name, device_type, lane, serial_port, baud_rate)
SELECT lot_id, 'Arduino - Cổng ra',  'arduino', 'exit',  'COM4', 9600 FROM parking_lots LIMIT 1;

INSERT INTO devices (lot_id, device_name, device_type, lane, ip_address)
SELECT lot_id, 'Camera khuôn mặt - Cổng vào', 'camera_face',  'entry', '192.168.1.101'::INET FROM parking_lots LIMIT 1;

INSERT INTO devices (lot_id, device_name, device_type, lane, ip_address)
SELECT lot_id, 'Camera biển số - Cổng vào',   'camera_plate', 'entry', '192.168.1.102'::INET FROM parking_lots LIMIT 1;

INSERT INTO devices (lot_id, device_name, device_type, lane, ip_address)
SELECT lot_id, 'Camera khuôn mặt - Cổng ra',  'camera_face',  'exit',  '192.168.1.103'::INET FROM parking_lots LIMIT 1;

INSERT INTO devices (lot_id, device_name, device_type, lane, ip_address)
SELECT lot_id, 'Camera biển số - Cổng ra',    'camera_plate', 'exit',  '192.168.1.104'::INET FROM parking_lots LIMIT 1;

INSERT INTO devices (lot_id, device_name, device_type, lane)
SELECT lot_id, 'Barrier - Cổng vào', 'barrier', 'entry' FROM parking_lots LIMIT 1;

INSERT INTO devices (lot_id, device_name, device_type, lane)
SELECT lot_id, 'Barrier - Cổng ra',  'barrier', 'exit'  FROM parking_lots LIMIT 1;

-- =============================================================================
-- Hoàn thành! Kiểm tra kết quả:
--   SELECT table_name FROM information_schema.tables
--   WHERE table_schema = 'public' ORDER BY table_name;
--
-- Tài khoản admin: admin / Admin@123
-- ĐỔI MẬT KHẨU trong pgAdmin: UPDATE admins
--   SET password_hash = crypt('mật_khẩu_mới', gen_salt('bf', 12))
--   WHERE username = 'admin';
-- =============================================================================
