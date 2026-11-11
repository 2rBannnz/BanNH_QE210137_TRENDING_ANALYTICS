# Phân tích bài toán — Crawl · Làm sạch · EDA

Tài liệu chia toàn bộ công việc hiện có của đồ án thành **3 phần riêng biệt**. Mỗi phần là một chuỗi **bài toán**, và mỗi bài toán được ghi theo cùng một khuôn:

| Mục | Nội dung |
|---|---|
| **Vấn đề** | Khó khăn cụ thể cần giải quyết |
| **Vì sao cần** | Nếu bỏ qua thì hỏng ở đâu |
| **Cách giải** | Ý tưởng và các quyết định thiết kế |
| **Cài đặt** | File, hàm, tham số, lịch chạy |
| **Kết quả** | Số liệu thật đo được |
| **Hạn chế / còn mở** | Những gì chưa giải quyết hết |

| Phần | File | Phạm vi |
|---|---|---|
| 1 — Crawl | [01_crawl.md](01_crawl.md) | YouTube Data API → MinIO (raw JSON) |
| 2 — Làm sạch | [02_cleaning.md](02_cleaning.md) | MinIO → PostgreSQL → bảng phân tích sạch `v_video_features` |
| 3 — EDA | [03_eda.md](03_eda.md) | Bảng phân tích (bản đóng băng CSV) → RStudio, trả lời câu hỏi "thời điểm vàng" |

**Mốc số liệu:**
- Dữ liệu thu thập từ 24/09/2026. Crawler dừng sau lần chụp lúc 06:00 ngày 24/10.
- Số liệu database lấy ngày 21/10 (Report 2). Số liệu EDA lấy ngày 23/10 (Report 3).
- **30/10:** gộp thêm dữ liệu JP (crawler `duc`) và US (`phat`) của 2 thành viên vào cùng DB (P20–P22); tập phân tích VN chốt lại: cohort 156.311, `is_clean` 40.531 (398 trending chính). EDA cũ bỏ, làm lại theo kế hoạch cuối [02_cleaning.md](02_cleaning.md#kế-hoạch-từ-đây-tới-eda).
- **01/11:** nhãn danh mục có độ phủ riêng (ô 3 giờ, ngưỡng 0,3) và tập sạch riêng `is_clean_category`: 39.669 video, 1.283 trending danh mục (P15). Dữ liệu chốt ở lần chụp cuối 24/10, không crawl thêm.
- Ký hiệu "≈" là giá trị đọc từ biểu đồ.

---

## Câu hỏi nghiên cứu chung

> **Thời điểm vàng:** đăng video trong **giờ hành chính** (08:00–17:00, thứ 2–6, giờ Việt Nam) hay **giờ nghỉ** (mọi thời điểm còn lại) thì dễ lọt **Top Trending** YouTube Việt Nam hơn?

Bảng dữ liệu đích: **mỗi dòng là 1 video mới đăng**. Mỗi dòng có giờ đăng, nhãn "có lọt trending trong 72 giờ đầu hay không", và các biến kiểm soát (danh mục, quy mô kênh, thời lượng, loại video).

## Ranh giới giữa 3 phần

```
 PHẦN 1 — CRAWL                    PHẦN 2 — LÀM SẠCH                              PHẦN 3 — EDA
 YouTube API ──► MinIO  ─────────► PostgreSQL ──► v_video_labels ──► v_video_features ─────► 3_EDA.Rmd
 src/ingestion/   raw/youtube/...  cleaner.py     labels.sql         features.sql            (RStudio)
                                   schema.sql                        1_Exploration.ipynb
```

- **Phần 1** kết thúc khi response của API đã nằm nguyên văn trên MinIO. Phần này **không** gắn nhãn, **không** làm sạch.
- **Phần 2** kết thúc khi có bảng phân tích sạch `v_video_features`, kèm cờ `is_clean`.
- **Phần 3** chỉ **đọc** `v_video_features` (và vài bảng gốc để vẽ đường view). Phần này không sửa dữ liệu.

---

## Danh sách bài toán

### Phần 1 — Crawl ([chi tiết](01_crawl.md))

| ID | Bài toán | Cài đặt chính |
|---|---|---|
| C1 | Bắt được "khoảnh khắc" trending | `jobs/trending.py` |
| C2 | Trần số positive, tách 2 định nghĩa trending | `jobs/trending_category.py` |
| C3 | Biết cần theo dõi những kênh nào | `jobs/channels.py` |
| C4 | Nhóm so sánh: video **không** trending | `jobs/uploads.py` |
| C5 | Mở rộng và đa dạng hoá tập kênh | `jobs/discover.py` |
| C6 | Theo dõi tốc độ tăng view | `jobs/stats.py` |
| C7 | Lịch sử đăng của kênh | `jobs/backfill.py` |
| C8 | Ngân sách quota 10.000 unit/ngày | `quota.py`, `crawler.py` |
| C9 | Lỗi tạm thời của API và mạng | `youtube_client.py` |
| C10 | Lưu dữ liệu thô truy vết được (Data Lake) | `raw.py`, `minio_client.py` |
| C11 | Ghi nhớ tiến độ giữa các lần chạy | `state/*.json` trên MinIO |
| C12 | Chạy tự động, độ phủ thời gian | Task Scheduler `\ADY201m\` |
| C13 | Lấy đủ trường dữ liệu cho câu hỏi | `parts.py` |

### Phần 2 — Làm sạch ([chi tiết](02_cleaning.md))

| ID | Bài toán | Cài đặt chính |
|---|---|---|
| P1 | Thiết kế lược đồ database | `configs/schema.sql` |
| P2 | Đọc dữ liệu từ MinIO | `cleaner.py` (`MinioSource`, `main`) |
| P3 | Bóc tách envelope theo từng job | `cleaner.py` (`add_envelope`) |
| P4 | Chuẩn hoá kiểu dữ liệu | `cleaner.py` (`parse_time`, `parse_duration`, `to_int`) |
| P5 | Thống nhất mốc thời gian chụp | `cleaner.py` (`parse_key`) |
| P6 | Trùng lặp và phiên bản mới nhất | `cleaner.py` (`Batch`, `UPSERT_SQL`) |
| P7 | Nạp lại an toàn: không mất, không nhân đôi | `raw_files`, `write_batch`, `safe_read` |
| P8 | Toàn vẹn tham chiếu khi dữ liệu đến lệch thứ tự | khoá ngoại + dòng tạm |
| P9 | Nạp tăng dần, tự động, tự nạp bù | `--recent-days`, task "Nap DB" |
| P10 | Xác định đúng giờ ra mắt | `release_at` (`labels.sql`) |
| P11 | Xác định cohort (video có nhãn đáng tin) | `v_cohort` |
| P12 | Gắn 2 nhãn trending | `v_video_labels`, `v_trending_rank` |
| P13 | Loại dữ liệu không dùng được | `v_videos_analysis`, `v_stats_analysis` |
| P14 | Biến khung giờ và biến kiểm soát | `features.sql` |
| P15 | Nhãn 0 sai do crawler vắng mặt | `coverage_24h`, `coverage_72h` |
| P16 | Cờ làm sạch, tập `is_clean` và `is_clean_category` | `features.sql` |
| P17 | Kiểm tra chất lượng dữ liệu bằng SQL | `configs/checks.sql` |
| P18 | Notebook làm sạch (minh chứng, quyết định) | `notebooks/1_Exploration.ipynb` |
| P19 | Sự cố vận hành của database | `docker-compose.yml`, `checks.sql` |
| P20 | Gộp dữ liệu nhiều khu vực (VN / JP / US) | `region_code`, `crawler_regions`, view lọc VN |
| P21 | Đưa raw của thành viên lên MinIO | `src/utils/import_raw_zip.py` |
| P22 | Ảnh hưởng chéo qua bảng dùng chung | `videos`, `channels` |

### Phần 3 — EDA ([chi tiết](03_eda.md))

Làm lại 01/11 trên bản đóng băng (bản cũ 23/10 đã bỏ). Notebook: `notebooks/3_EDA.Rmd` → `3_EDA.html`.

| ID | Bài toán | Mục trong Rmd |
|---|---|---|
| E1 | Tập sạch có còn đại diện cho cohort không | A |
| E2 | Phân phối từng biến | B |
| E3 | Tỉ lệ trending theo giờ đăng | C1 |
| E4 | Giờ hành chính hay giờ nghỉ | C2, C3 |
| E5 | Tỉ lệ nền thay đổi theo ngày | C4 |
| E6 | Độ vững theo ngưỡng độ phủ | C5 |
| E7 | Kiểm soát nhiễu (Mantel–Haenszel, bootstrap theo kênh) | D1–D3, D5 |
| E8 | Ảnh hưởng của vài kênh lớn | D4 |
| E9 | Chân dung video trending | E |
| E10 | Nhãn danh mục | F |
| E11 | Kết luận và đề xuất cho Report 4 | I |

---

## Kết luận xuyên suốt

1. **Phần 1:** thu được 165.393 file raw (9,32 GB) của máy VN. Nhưng crawler chạy trên máy cá nhân nên **chỉ khoảng 50% số giờ có lần chụp trending**, ít nhất vào 10–13h. Đây là điểm yếu lớn nhất của dữ liệu. Ngày 30/10 gộp thêm 65.179 file của máy JP và US (P20–P21).
2. **Phần 2:** biến điểm yếu đó thành **cột đo được** (`coverage_24h`, `coverage_72h`; chart danh mục có `coverage_cat_*` riêng) và lọc theo ngưỡng 0,6 cho nhãn chính, 0,3 cho nhãn danh mục. Mốc 01/11: cohort VN 156.311 video còn **40.531 video sạch cho nhãn chính (398 trending)** và **39.669 video sạch cho nhãn danh mục (1.283 trending)**.
3. **Phần 3:** với **chart chính**, đăng ngoài giờ hành chính (rõ nhất 16–18h ngày thường) dễ lọt trending hơn: thô gấp 1,9 lần, sau khi kiểm soát ngày đăng, quy mô kênh, danh mục còn khoảng **1,5 lần**, thêm thời lượng còn khoảng 1,25 lần và không còn chắc chắn. Với **chart danh mục** không có khác biệt. **Loại video** (dài, không Shorts, không tin tức) quan trọng hơn giờ đăng nhiều. Shorts = video ≤ 3 phút (giới hạn của YouTube từ 15/10/2024), ước lượng theo thời lượng.

## Điểm lệch giữa tài liệu cũ và code hiện tại

| Nơi ghi | Đang ghi | Thực tế trong code |
|---|---|---|
| `README.md` mục 5 | Backfill lấy lùi 90 ngày, tối đa 200 video/kênh | `BACKFILL_DAYS = 30`, `MAX_PAGES_PER_CHANNEL = 1`, tức tối đa 50 video/kênh. Comment trong `backfill.py` cũng còn ghi "200 video" |
| `README.md` mục 5, 7, 11 | 6 job; tầng Processing "chưa làm" | 7 job (thêm `trending_category`); Processing đã xong |
| `README.md` mục 9, 10 | Trỏ tới `docs/VAN_HANH.md` | File thật là `docs/HOW_TO_SETUP.md` |
| `README.md` mục 1 | Giả thuyết H₀/H₁ kiểm định bằng p-value | Đã chuyển sang phân tích khám phá và mô hình phân loại; không kiểm định p-value |
