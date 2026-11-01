# Data Dictionary — YouTube Trending VN (ADY201m, đề tài 4)

Mốc số liệu: **01/11/2026**. Dữ liệu thu thập từ 24/09 đến lần chụp cuối 24/10/2026 (giờ VN), không crawl thêm.

```
YouTube Data API ─► MinIO (raw JSON) ─► PostgreSQL: 9 bảng gốc ─► view trung gian ─► v_video_features ─► EDA / mô hình
                    src/ingestion/       configs/schema.sql          configs/labels.sql    configs/features.sql
```

- **Bảng gốc** chứa dữ liệu đã chuẩn hoá kiểu, không bị xoá hay lọc. Mọi lựa chọn (bỏ backfill, cohort, nhãn, cờ làm sạch) nằm ở **view**.
- **Bảng phân tích** là `v_video_features`, đóng băng ra `data/processed/video_features_full_2026-11-01.csv` (156.311 dòng, 47 cột; không commit, repo chỉ có mẫu 500 dòng `video_features_sample.csv`).
- **Thời gian**: cột `TIMESTAMPTZ` lưu theo UTC. Cột có hậu tố `_vn` là giờ Việt Nam (`Asia/Ho_Chi_Minh`, UTC+7).
- **`region_code`** = khu vực của **máy crawl** đã thu thập dòng đó (VN / JP / US), gán theo `crawler_id` trong `configs/db_config.json`. **Không phải** quốc gia của kênh (xem `channels.country`). Mọi view phân tích chỉ dùng `VN`.

---

## 1. Bảng gốc (9 bảng)

### 1.1. `raw_files` — nhật ký file raw đã nạp (241.202 dòng)
| Cột | Kiểu | Ý nghĩa |
|---|---|---|
| `object_key` (PK) | TEXT | Tên object trên MinIO: `raw/youtube/<job>/dt=<ngày>/<crawler_id>_<HHMMSS>_pNN.json` |
| `job`, `endpoint` | TEXT | Job crawl (`trending`, `uploads/videos`, ...) và endpoint API đã gọi |
| `crawler_id` | TEXT | Máy crawl (VN: `t1-2rban`, `t1-2rbannnz`; JP: `duc`; US: `phat`) |
| `captured_at` / `crawl_time_utc` | TIMESTAMPTZ | Mốc chụp lấy từ tên file (lúc bắt đầu lượt chạy) / lúc thật sự gọi API |
| `page_index`, `n_items` | INT | Trang thứ mấy của lượt chạy, số item trong file |

Bằng chứng dữ liệu đi từ MinIO vào DB; loader bỏ qua file đã có ở đây nên chạy lại không nạp trùng.

### 1.2. `categories` — danh mục video (32 dòng)
| Cột | Kiểu | Ý nghĩa |
|---|---|---|
| `category_id` (PK) | INT | Mã danh mục YouTube |
| `title` | TEXT | Tên danh mục tiếng Việt (`videoCategories.list`, `hl=vi`) |
| `assignable` | BOOLEAN | Danh mục có gán được cho video không |

Danh mục 29 không có trong API khu vực VN nhưng có video dùng, nên được thêm sẵn. Mã lạ khác được thêm thành dòng tạm (`title` NULL).

### 1.3. `channels` — kênh, bản mới nhất (19.219 dòng)
| Cột | Kiểu | Ý nghĩa |
|---|---|---|
| `channel_id` (PK) | TEXT | Mã kênh |
| `title`, `custom_url`, `country`, `default_language` | TEXT | Thông tin kênh; `country` NULL nếu kênh không khai báo |
| `subscriber_count`, `video_count`, `view_count` | BIGINT | Số liệu kênh **tại lần chụp mới nhất**; subscriber NULL nếu kênh ẩn |
| `hidden_subscriber` | BOOLEAN | Kênh ẩn số subscriber |
| `uploads_playlist` | TEXT | Playlist "uploads" của kênh, job `uploads` đọc để tìm video mới |
| `first_seen_at`, `last_seen_at`, `first_source_job` | | Lần đầu / lần cuối thấy kênh và job đã thấy đầu tiên |
| `is_stub` | BOOLEAN | Kênh **tạm** (68 kênh): video đến trước kênh, chỉ có `channel_id`, chờ `channels.list` điền đủ |

### 1.4. `videos` — metadata video, bản mới nhất (439.870 dòng)
| Cột | Kiểu | Ý nghĩa |
|---|---|---|
| `video_id` (PK) | TEXT | Mã video |
| `channel_id` (FK → `channels`), `category_id` (FK → `categories`) | TEXT / INT | Kênh và danh mục |
| `published_at` | TIMESTAMPTZ | `snippet.publishedAt`; với livestream YouTube đổi thành lúc phát **xong** |
| `actual_start_time`, `scheduled_start_time` | TIMESTAMPTZ | Lúc bắt đầu phát thật / dự kiến (chỉ livestream, premiere) |
| `title`, `description`, `tags` (TEXT[]), `default_language`, `default_audio_language` | | Nội dung do chủ kênh khai báo |
| `duration_s` | INT | Thời lượng (giây), đổi từ ISO 8601 `PT4M13S`; NULL hoặc 0 khi livestream chưa kết thúc |
| `definition`, `caption`, `live_broadcast_content` | TEXT / BOOLEAN / TEXT | `hd`/`sd`; có phụ đề; `none`/`live`/`upcoming` |
| `first_seen_at`, `last_seen_at`, `first_source_job` | | Lần đầu / lần cuối thấy video, job đã thấy đầu tiên |

### 1.5. `video_sources` — video được job nào thấy (1.621.859 dòng)
| Cột | Kiểu | Ý nghĩa |
|---|---|---|
| `video_id` | TEXT | Mã video (không có FK: nhiều video chỉ có trong playlist, không có dòng `videos`) |
| `source_job` | TEXT | `trending`, `trending_category`, `uploads/videos`, `uploads/playlist_items`, `stats`, `backfill/videos`, `backfill/playlist_items` |
| `region_code` | TEXT | Khu vực máy crawl |
| `first_captured_at` | TIMESTAMPTZ | Lần đầu job đó thấy video |
| PK | | `(video_id, source_job, region_code)` |

Dùng để tách video mới (cohort, từ `uploads/videos` của VN) khỏi video lịch sử (backfill).

### 1.6. `video_stats` — số liệu tương tác tại mỗi lần chụp (2.723.654 dòng)
| Cột | Kiểu | Ý nghĩa |
|---|---|---|
| `video_id` (FK → `videos`) | TEXT | Mã video |
| `captured_at` | TIMESTAMPTZ | Mốc chụp |
| `source_job`, `region_code` | TEXT | Job và khu vực máy đã chụp |
| `view_count` | BIGINT | Số view tại mốc chụp |
| `like_count`, `comment_count` | BIGINT | NULL khi chủ kênh ẩn (không điền 0) |
| PK | | `(video_id, captured_at, source_job, region_code)` |

### 1.7. `trending_snapshots` — mỗi lần video có mặt trên bảng xếp hạng (180.459 dòng)
| Cột | Kiểu | Ý nghĩa |
|---|---|---|
| `video_id` (FK → `videos`) | TEXT | Mã video |
| `captured_at` | TIMESTAMPTZ | Mốc chụp của lượt chạy |
| `source` | TEXT | `main` = chart chính (job `trending`, mỗi giờ); `category` = chart theo danh mục (job `trending_category`, mỗi 3 giờ) |
| `category_id` | INT | 0 với chart chính; mã danh mục với chart danh mục |
| `page_index`, `position` | INT | Trang (50 video/trang) và vị trí trong trang; thứ hạng = `v_trending_rank.rank` |
| `region_code` | TEXT | Chart của khu vực nào |
| PK | | `(video_id, captured_at, source, category_id, region_code)` |

Nguồn của 2 nhãn trending.

### 1.8. `playlist_items` — danh sách video của kênh (7.967.633 dòng)
| Cột | Kiểu | Ý nghĩa |
|---|---|---|
| `video_id`, `playlist_id` | TEXT | Video nằm trong playlist uploads của kênh |
| `video_published_at` | TIMESTAMPTZ | Giờ đăng theo playlist |
| `captured_at`, `source_job` | | Mốc chụp, job (`uploads/playlist_items` hoặc `backfill/playlist_items`) |
| PK | | `(video_id, playlist_id, captured_at)` |

Bước trung gian để tìm video mới; không có FK vì phần lớn video cũ không được gọi `videos.list`.

### 1.9. `discover_candidates` — kênh ứng viên do `discover` tìm được (28.911 dòng)
| Cột | Kiểu | Ý nghĩa |
|---|---|---|
| `channel_id` | TEXT | Kênh ứng viên |
| `method` | TEXT | `search` (tìm theo từ khoá) hoặc `sections` (mục "kênh nổi bật" của kênh khác) |
| `query_or_parent` | TEXT | Từ khoá đã tìm, hoặc kênh cha |
| `captured_at` | TIMESTAMPTZ | Mốc chụp |
| PK | | `(channel_id, method, query_or_parent, captured_at)` |

Truy vết vì sao một kênh được đưa vào danh sách theo dõi.

---

## 2. View trung gian (`configs/labels.sql`)

| View | Một dòng là | Vai trò |
|---|---|---|
| `v_videos_analysis` | 1 video | Video được máy VN thấy ở job không phải backfill, kênh không phải kênh tạm |
| `v_stats_analysis` | 1 lần chụp số liệu | `video_stats` của VN, bỏ backfill, chỉ video trong `v_videos_analysis` |
| `v_trending_rank` | 1 lần có mặt trên chart VN | Thêm `rank` liên tục (1 = cao nhất) trong từng lần chụp × chart × danh mục |
| `v_cohort` | 1 video | Video do `uploads/videos` của VN tìm thấy, ra mắt trong khoảng chart chính được theo dõi trọn 72 giờ (24/09 16:52 → 20/10 23:00 UTC) |
| `v_video_labels` | 1 video của cohort | Gắn 2 nhãn trending (cửa sổ 72 giờ) và biến cơ bản |

---

## 3. Bảng phân tích `v_video_features` (156.311 dòng, 47 cột)

Một dòng = **một video trong cohort VN**. Cột "Giá trị (01/11)" lấy trên toàn bộ 156.311 dòng.

### 3.1. Định danh và thời gian

| Cột | Kiểu | Ý nghĩa / cách tính | NULL khi | Giá trị (01/11) |
|---|---|---|---|---|
| `video_id` | text | Mã video (khoá, không trùng) | Không | 156.311 video |
| `channel_id` | text | Mã kênh | Không | 3.824 kênh |
| `published_at` | timestamptz | `snippet.publishedAt` từ API | Không | |
| `release_at` | timestamptz | **Giờ ra mắt thật** = `COALESCE(actual_start_time, published_at)`; livestream dùng lúc bắt đầu phát | Không | Khác `published_at` ở 5.531 video |
| `release_at_vn` | timestamp | `release_at` theo giờ VN | Không | 24/09 23:53 → 21/10 06:00 |
| `publish_hour_vn` | integer | Giờ đăng theo giờ VN (0–23) | Không | Trung vị 15 |
| `publish_dow_vn` | integer | Thứ đăng theo giờ VN, ISO: 1 = thứ 2 … 7 = chủ nhật | Không | |

### 3.2. Nhãn trending (cửa sổ 72 giờ kể từ `release_at`)

| Cột | Kiểu | Ý nghĩa / cách tính | NULL khi | Giá trị (01/11) |
|---|---|---|---|---|
| `is_trending_main` | boolean | Có ít nhất một lần chụp **chart chính VN** trong `[release_at, release_at + 72h]` | Không bao giờ (cohort đã đảm bảo theo dõi trọn 72 giờ) | true: 1.029 (0,66%) |
| `hours_to_trending_main` | numeric | Số giờ từ `release_at` tới lần đầu lên chart chính | Video không trending chính | 2,3 → 71,8 giờ; trung vị 25,0 |
| `best_rank_main` | bigint | Thứ hạng cao nhất trên chart chính trong 72 giờ (1 = đầu bảng) | Video không trending chính | 1 → 200; trung vị 98 |
| `is_trending_category` | boolean | Có ít nhất một lần chụp **chart danh mục VN** trong 72 giờ | Video ra mắt ngoài khoảng chart danh mục được theo dõi đủ 72 giờ (job bắt đầu 09/10): **không biết**, không phải `false` | NULL 40,14%; true: 2.492 |
| `hours_to_trending_category` | numeric | Như trên, với chart danh mục | Video không trending danh mục | 2,5 → 71,9 giờ; trung vị 27,2 |
| `best_rank_category` | bigint | Thứ hạng cao nhất trên chart danh mục | Video không trending danh mục | 1 → 200; trung vị 75 |

### 3.3. Khung giờ đăng (biến chính của câu hỏi "thời điểm vàng")

| Cột | Kiểu | Ý nghĩa / cách tính | NULL khi | Giá trị |
|---|---|---|---|---|
| `is_office_hours` | boolean | Thứ 2–6 **và** giờ 8–16 (tức 08:00–16:59, giờ VN) | Không | true: 51.702 (33%) |
| `time_slot` | text | `hanh_chinh` nếu `is_office_hours`, ngược lại `nghi` | Không | 2 giá trị |
| `slot_detail` | text | Tách giờ nghỉ: `gio_hanh_chinh`, `cuoi_tuan` (thứ 7, CN), `toi_ngay_thuong (17-24h)`, `dem_sang_ngay_thuong (0-8h)` | Không | 4 giá trị |
| `day_part` | text | Buổi trong ngày: `dem (0-6h)`, `sang (6-12h)`, `chieu (12-18h)`, `toi (18-24h)` | Không | 4 giá trị |
| `is_weekend` | boolean | Thứ 7 hoặc chủ nhật (giờ VN) | Không | true: 45.883 |

### 3.4. Biến kiểm soát

| Cột | Kiểu | Ý nghĩa / cách tính | NULL khi | Giá trị |
|---|---|---|---|---|
| `category_id` | integer | Mã danh mục video | Không | 15 danh mục |
| `category_title` | text | Tên danh mục (từ `categories`) | Không | Nhiều nhất: Mọi người và Blog |
| `duration_s` | integer | Thời lượng (giây) | Livestream chưa có thời lượng (0,02%) | Trung vị 73 giây |
| `duration_group` | text | `<=60s (Shorts)`, `61-180s`, `3-10 phut`, `10-20 phut`, `20-60 phut`, `>60 phut`, `khong_ro` (NULL) | Không | 7 giá trị |
| `is_short` | boolean | `duration_s ≤ 60` | `duration_s` NULL | |
| `live_broadcast_content` | text | Trạng thái phát lúc chụp cuối: `none`, `live`, `upcoming` | Không | |
| `is_live_or_premiere` | boolean | Có `actual_start_time` (livestream hoặc premiere đã phát) | Không | true: 13.369 |
| `definition` | text | `hd` / `sd` | Không | |
| `caption` | boolean | Có phụ đề do chủ kênh tải lên | Không | true: 846 |
| `default_audio_language` | text | Ngôn ngữ âm thanh do chủ kênh khai báo (`vi`, `en`, ...) | Chủ kênh không khai báo (32,56%) | 49 giá trị |
| `title_length` | integer | Số ký tự tiêu đề | Không | 1 → 100; trung vị 68 |
| `n_tags` | integer | Số tag (0 nếu không có) | Không | Trung vị 5 |
| `channel_subscribers` | bigint | Số subscriber của kênh **tại lần chụp kênh mới nhất**, không phải lúc đăng video | Kênh ẩn subscriber (hiện 0 video) | Trung vị 183.000 |
| `subs_group` | text | `<10k`, `10k-100k`, `100k-1M`, `1M-10M`, `>10M`; `an` nếu ẩn | Không | 5 giá trị có mặt |
| `log10_subs` | double | `log10(1 + channel_subscribers)` | Kênh ẩn subscriber | 0 → 8,7 |
| `channel_video_count`, `channel_view_count` | bigint | Số video, tổng view của kênh (lần chụp mới nhất) | Không | |
| `channel_country` | text | Quốc gia kênh tự khai báo | Kênh không khai báo (13,22%) | 55 giá trị; nhiều nhất VN |

### 3.5. Độ phủ crawler và cờ làm sạch

Cờ **không xoá dòng**, chỉ đánh dấu. Mỗi nhãn có một tập sạch riêng.

| Cột | Kiểu | Ý nghĩa / cách tính | NULL khi | Giá trị |
|---|---|---|---|---|
| `coverage_24h` | double | Tỉ lệ số giờ có lần chụp chart chính VN trong 24 giờ đầu (số giờ / 24) | Không | 0 → 1; trung vị 0,583 |
| `coverage_72h` | double | Như trên, trong 72 giờ đầu (/ 72). Giá trị nhỏ nhất 0,014 (= 1/72) thay vì 0 do cách đếm, không ảnh hưởng ngưỡng | Không | Trung vị 0,542; tối đa 0,917 |
| `coverage_cat_24h` | double | Tỉ lệ **ô 3 giờ** có lần chụp chart danh mục **đúng danh mục của video** trong 24 giờ đầu (/ 8) | Không | 0 → 0,875 |
| `coverage_cat_72h` | double | Như trên, trong 72 giờ đầu (/ 24) | Không | 0 → 0,708; trung vị 0,167 |
| `flag_no_duration` | boolean | `duration_s` NULL hoặc 0 (livestream chưa kết thúc) | Không | true: 205 |
| `flag_hidden_subs` | boolean | `channel_subscribers` NULL (kênh ẩn hoặc kênh tạm) | Không | true: 0 |
| `flag_extreme_duration` | boolean | `duration_s` > 3 giờ (chủ yếu bản ghi livestream dài) | `duration_s` NULL | true: 1.912 |
| `flag_low_coverage` | boolean | `coverage_24h` < 0,6 **hoặc** `coverage_72h` < 0,6 | Không | true: 115.009 |
| `flag_low_coverage_cat` | boolean | `coverage_cat_24h` < 0,3 **hoặc** `coverage_cat_72h` < 0,3 | Không | true: 112.553 |
| **`is_clean`** | boolean | **Tập sạch cho nhãn chính**: không dính `flag_no_duration`, `flag_hidden_subs`, `flag_extreme_duration`, `flag_low_coverage` | Không | **true: 40.531** (398 trending chính) |
| **`is_clean_category`** | boolean | **Tập sạch cho nhãn danh mục**: `is_trending_category` không NULL, không dính 3 cờ đầu và `flag_low_coverage_cat` | Không | **true: 39.669** (1.283 trending danh mục) |

**Vì sao cần độ phủ:** crawler chạy trên máy cá nhân, chỉ có mặt khoảng 59% số giờ. Video lên trending đúng lúc crawler tắt bị ghi nhãn 0 sai. Ngưỡng chọn bằng bảng độ nhạy (`notebooks/1_Exploration.ipynb` mục 6, 6b; `docs/analysis/02_cleaning.md` P15).

---

## 4. Cách dùng

| Câu hỏi | Lọc | Nhãn |
|---|---|---|
| Đăng giờ nào dễ lọt **chart chính** | `WHERE is_clean` | `is_trending_main` |
| Đăng giờ nào dễ lọt **chart danh mục** | `WHERE is_clean_category` | `is_trending_category` |
| Mô tả video trending (nhanh/chậm, hạng) | Mọi video có nhãn 1, không cần tập sạch | `hours_to_trending_*`, `best_rank_*` |
