-- =====================================================================
-- Bảng phân tích đã làm sạch cho EDA (Report 3) và mô hình (Report 4)
-- Dựng trên v_video_labels; chạy lại an toàn (xoá view rồi tạo lại).
--
-- Câu hỏi trọng tâm "thời điểm vàng": đăng trong giờ hành chính (08–17h, thứ 2–6, giờ VN)
-- hay giờ nghỉ thì dễ lọt Top Trending hơn?
--   - Cột thời gian: time_slot, slot_detail, day_part, is_weekend
--   - Cột kiểm soát nhiễu: subs_group, log10_subs, duration_group, is_short
--   - Cờ làm sạch: KHÔNG xoá dòng, chỉ đánh dấu; is_clean = không dính cờ nào
--
-- Độ phủ crawler: crawler trending chạy mỗi giờ nhưng máy có lúc tắt (tính đến 23/10 chỉ ~50% số giờ
-- có lần chụp, thấp nhất 10–13h). Video ra mắt lúc crawler tắt có thể đã trending mà không ai thấy
-- -> nhãn 0 sai. coverage_24h / coverage_72h = tỉ lệ số giờ có lần chụp trending chính trong
-- 24h / 72h đầu sau release_at. is_clean yêu cầu cả hai >= COVERAGE_MIN (0.6).
-- =====================================================================

DROP VIEW IF EXISTS v_video_features;

CREATE VIEW v_video_features AS
WITH run_hours AS (
    -- Các giờ máy crawl VN có ít nhất một lần chụp trending chính (giờ máy JP/US chạy không tính)
    SELECT DISTINCT date_trunc('hour', captured_at) AS h
    FROM trending_snapshots WHERE source = 'main' AND region_code = 'VN'
),
coverage AS (
    SELECT l.video_id,
           COUNT(*) FILTER (WHERE r.h < l.release_at + INTERVAL '24 hours') / 24.0 AS coverage_24h,
           COUNT(*) / 72.0                                                       AS coverage_72h
    FROM v_video_labels l
    LEFT JOIN run_hours r
           ON r.h >= l.release_at AND r.h < l.release_at + INTERVAL '72 hours'
    GROUP BY l.video_id, l.release_at
)
SELECT
    l.*,

    -- ---------- Thời gian đăng ----------
    CASE WHEN l.is_office_hours THEN 'hanh_chinh' ELSE 'nghi' END              AS time_slot,
    (l.publish_dow_vn IN (6, 7))                                                AS is_weekend,
    CASE WHEN l.publish_hour_vn < 6  THEN 'dem (0-6h)'
         WHEN l.publish_hour_vn < 12 THEN 'sang (6-12h)'
         WHEN l.publish_hour_vn < 18 THEN 'chieu (12-18h)'
         ELSE 'toi (18-24h)' END                                                AS day_part,
    -- Tách giờ nghỉ thành các đoạn để biết đoạn nào thực sự tốt
    CASE WHEN l.is_office_hours            THEN 'gio_hanh_chinh'
         WHEN l.publish_dow_vn IN (6, 7)   THEN 'cuoi_tuan'
         WHEN l.publish_hour_vn >= 17      THEN 'toi_ngay_thuong (17-24h)'
         ELSE 'dem_sang_ngay_thuong (0-8h)' END                                 AS slot_detail,

    -- ---------- Biến kiểm soát nhiễu ----------
    CASE WHEN l.channel_subscribers IS NULL       THEN 'an'
         WHEN l.channel_subscribers < 10000       THEN '<10k'
         WHEN l.channel_subscribers < 100000      THEN '10k-100k'
         WHEN l.channel_subscribers < 1000000     THEN '100k-1M'
         WHEN l.channel_subscribers < 10000000    THEN '1M-10M'
         ELSE '>10M' END                                                        AS subs_group,
    LOG(1 + l.channel_subscribers::NUMERIC)::DOUBLE PRECISION                   AS log10_subs,
    CASE WHEN l.duration_s IS NULL   THEN 'khong_ro'
         WHEN l.duration_s <= 60     THEN '<=60s (Shorts)'
         WHEN l.duration_s <= 180    THEN '61-180s'
         WHEN l.duration_s <= 600    THEN '3-10 phut'
         WHEN l.duration_s <= 1200   THEN '10-20 phut'
         WHEN l.duration_s <= 3600   THEN '20-60 phut'
         ELSE '>60 phut' END                                                    AS duration_group,
    (l.duration_s <= 60)                                                        AS is_short,

    -- ---------- Cờ làm sạch ----------
    -- Livestream chưa kết thúc: API trả thời lượng rỗng hoặc P0D (= 0 giây)
    (l.duration_s IS NULL OR l.duration_s = 0)                                  AS flag_no_duration,
    (l.channel_subscribers IS NULL)                                             AS flag_hidden_subs,
    (l.duration_s > 3 * 3600)                                                   AS flag_extreme_duration,
    -- Độ phủ crawler trong 24h / 72h đầu (0–1)
    ROUND(c.coverage_24h::NUMERIC, 3)::DOUBLE PRECISION                         AS coverage_24h,
    ROUND(c.coverage_72h::NUMERIC, 3)::DOUBLE PRECISION                         AS coverage_72h,
    (c.coverage_24h < 0.6 OR c.coverage_72h < 0.6)                              AS flag_low_coverage,
    NOT (
        l.duration_s IS NULL OR l.duration_s = 0
        OR l.channel_subscribers IS NULL
        OR l.duration_s > 3 * 3600
        OR c.coverage_24h < 0.6
        OR c.coverage_72h < 0.6
    )                                                                           AS is_clean
FROM v_video_labels l
JOIN coverage c ON c.video_id = l.video_id;
