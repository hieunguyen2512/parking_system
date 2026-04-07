-- Migration: thêm cột hỗ trợ hardware integration
-- Chạy: psql -U postgres -d parking_system -f hardware_migration.sql

-- Thêm entry_device_id / exit_device_id vào parking_sessions (UUID, khớp với devices.device_id)
ALTER TABLE parking_sessions
  ADD COLUMN IF NOT EXISTS entry_device_id UUID REFERENCES devices(device_id),
  ADD COLUMN IF NOT EXISTS exit_device_id  UUID REFERENCES devices(device_id);

-- Thêm entry_device_id / exit_device_id vào guest_sessions
ALTER TABLE guest_sessions
  ADD COLUMN IF NOT EXISTS entry_device_id UUID REFERENCES devices(device_id),
  ADD COLUMN IF NOT EXISTS exit_device_id  UUID REFERENCES devices(device_id);

-- Tạo index để tìm phiên đang mở nhanh hơn
CREATE INDEX IF NOT EXISTS idx_parking_sessions_plate_active
  ON parking_sessions(license_plate) WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_guest_sessions_plate_active
  ON guest_sessions(license_plate) WHERE status = 'active';
