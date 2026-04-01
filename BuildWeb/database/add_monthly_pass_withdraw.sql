-- =============================================================================
-- MIGRATION: Thêm vé tháng và rút tiền
-- Phụ thuộc: setup_full.sql đã được chạy
--
-- HƯỚNG DẪN:
--   pgAdmin → Query Tool → Mở file này → F5
-- =============================================================================

-- 1. Thêm 'withdraw' vào notification type nếu chưa có
--    (setup_full.sql đã có sẵn 'withdraw_success' → không cần thay đổi notifications)

-- 2. BẢNG VÉ THÁNG
CREATE TABLE IF NOT EXISTS monthly_passes (
    pass_id         UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID            NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    vehicle_id      UUID            NOT NULL REFERENCES vehicles(vehicle_id) ON DELETE CASCADE,
    lot_id          UUID            NOT NULL REFERENCES parking_lots(lot_id) ON DELETE CASCADE,
    license_plate   VARCHAR(20)     NOT NULL,
    valid_from      DATE            NOT NULL,
    valid_until     DATE            NOT NULL,
    fee_paid        NUMERIC(10,2)   NOT NULL CHECK (fee_paid >= 0),
    wallet_tx_id    UUID            REFERENCES wallet_transactions(transaction_id) ON DELETE SET NULL,
    status          VARCHAR(20)     NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'expired', 'cancelled')),
    note            TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_pass_dates CHECK (valid_until >= valid_from)
);

CREATE INDEX IF NOT EXISTS idx_monthly_passes_user    ON monthly_passes (user_id);
CREATE INDEX IF NOT EXISTS idx_monthly_passes_vehicle ON monthly_passes (vehicle_id);
CREATE INDEX IF NOT EXISTS idx_monthly_passes_active  ON monthly_passes (user_id, status) WHERE status = 'active';

-- Auto-update updated_at
DROP TRIGGER IF EXISTS set_updated_at_monthly_passes ON monthly_passes;
CREATE TRIGGER set_updated_at_monthly_passes
    BEFORE UPDATE ON monthly_passes
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

-- 3. BẢNG YÊU CẦU RÚT TIỀN
CREATE TABLE IF NOT EXISTS withdraw_requests (
    request_id      UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID            NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    amount          NUMERIC(15,2)   NOT NULL CHECK (amount >= 10000),
    bank_name       VARCHAR(100)    NOT NULL,
    bank_account    VARCHAR(30)     NOT NULL,
    account_name    VARCHAR(100)    NOT NULL,
    wallet_tx_id    UUID            REFERENCES wallet_transactions(transaction_id) ON DELETE SET NULL,
    status          VARCHAR(20)     NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'processing', 'completed', 'rejected')),
    admin_note      TEXT,
    processed_by    UUID            REFERENCES admins(admin_id),
    processed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_withdraw_requests_user   ON withdraw_requests (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_withdraw_requests_status ON withdraw_requests (status) WHERE status = 'pending';

DROP TRIGGER IF EXISTS set_updated_at_withdraw_requests ON withdraw_requests;
CREATE TRIGGER set_updated_at_withdraw_requests
    BEFORE UPDATE ON withdraw_requests
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

-- 4. Cấu hình giá vé tháng (lưu vào system_configs)
--    key: monthly_pass_price  value: 200000 (đơn vị VND/tháng)
INSERT INTO system_configs (config_key, config_value, data_type, description)
VALUES ('monthly_pass_price', '200000', 'integer', 'Giá vé tháng gửi xe (VND/tháng/xe)')
ON CONFLICT (config_key) DO NOTHING;
