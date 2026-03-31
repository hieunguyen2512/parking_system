-- =============================================================================
-- MIGRATION: Thêm bảng user_face_images
-- Mục đích: Lưu trữ ảnh khuôn mặt của người dùng để AI (ArcFace) xử lý đối chiếu
--
-- LUỒNG XỬ LÝ:
--   1. Người dùng upload ảnh qua WebApp → Backend lưu file vào uploads/faces/{user_id}/
--   2. Record được tạo trong user_face_images với status = 'pending'
--   3. Module AI query: SELECT * FROM user_face_images WHERE status = 'pending'
--   4. AI xử lý ảnh, tạo embedding 512 chiều (ArcFace)
--   5. AI INSERT vào face_embeddings, UPDATE user_face_images SET status='processed', embedding_id=...
--
-- HƯỚNG DẪN CHẠY:
--   pgAdmin → Query Tool → Mở file này → F5
--   (Phải chạy TRÊN database parking_system đã có setup_full.sql)
-- =============================================================================

-- Bảng lưu ảnh khuôn mặt người dùng (chờ AI xử lý embedding)
CREATE TABLE IF NOT EXISTS user_face_images (
    image_id        UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID            NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    image_path      VARCHAR(500)    NOT NULL,                          -- đường dẫn tương đối từ thư mục uploads/
    status          VARCHAR(20)     NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'processing', 'processed', 'failed')),
    embedding_id    UUID            REFERENCES face_embeddings(embedding_id) ON DELETE SET NULL,
    note            TEXT,                                              -- ghi chú lỗi nếu AI xử lý thất bại
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_face_images_user    ON user_face_images (user_id);
CREATE INDEX IF NOT EXISTS idx_user_face_images_status  ON user_face_images (status);
CREATE INDEX IF NOT EXISTS idx_user_face_images_pending ON user_face_images (status) WHERE status = 'pending';

-- Trigger tự cập nhật updated_at
CREATE OR REPLACE FUNCTION update_face_images_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_face_images_updated_at ON user_face_images;
CREATE TRIGGER trg_face_images_updated_at
    BEFORE UPDATE ON user_face_images
    FOR EACH ROW EXECUTE FUNCTION update_face_images_updated_at();

-- =============================================================================
-- VIEW hỗ trợ AI: lấy ảnh chờ xử lý kèm thông tin người dùng
-- Module AI có thể query: SELECT * FROM v_pending_face_images;
-- =============================================================================
CREATE OR REPLACE VIEW v_pending_face_images AS
SELECT
    fi.image_id,
    fi.user_id,
    fi.image_path,
    fi.status,
    fi.created_at,
    u.full_name,
    u.phone_number
FROM user_face_images fi
JOIN users u ON u.user_id = fi.user_id
WHERE fi.status IN ('pending', 'processing')
ORDER BY fi.created_at ASC;

-- =============================================================================
-- VIEW tổng hợp: thông tin khuôn mặt của từng user để admin xem
-- =============================================================================
CREATE OR REPLACE VIEW v_user_face_summary AS
SELECT
    u.user_id,
    u.full_name,
    u.phone_number,
    COUNT(fi.image_id)                                          AS total_images,
    COUNT(fi.image_id) FILTER (WHERE fi.status = 'pending')    AS pending_count,
    COUNT(fi.image_id) FILTER (WHERE fi.status = 'processed')  AS processed_count,
    COUNT(fe.embedding_id)                                      AS embedding_count,
    MAX(fi.created_at)                                          AS last_upload_at
FROM users u
LEFT JOIN user_face_images fi ON fi.user_id = u.user_id
LEFT JOIN face_embeddings  fe ON fe.user_id = u.user_id AND fe.is_active
GROUP BY u.user_id, u.full_name, u.phone_number;
