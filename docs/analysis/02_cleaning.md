# Phần 2 — Làm sạch: MinIO → PostgreSQL → bảng phân tích sạch

[← Phần 1 — Crawl](01_crawl.md) · [Tổng quan](README.md) · [Phần 3 — EDA →](03_eda.md)

**Mục tiêu của phần:** biến toàn bộ file JSON thô (241.202 file của 3 máy crawl VN / JP / US, mốc 30/10) thành **một bảng phân tích sạch** (`v_video_features`): mỗi dòng là 1 video **VN**, có giờ ra mắt đúng, có 2 nhãn trending, có biến kiểm soát và cờ chất lượng. Dữ liệu JP/US nằm cùng DB nhưng không vào bảng phân tích (P20).

## Luồng xử lý

```
zip raw của thành viên (JP, US)
   │  src/utils/import_raw_zip.py  (chép nguyên byte lên MinIO, kiểm tra crawler)        P21
   ▼
MinIO raw/youtube/...  (VN: t1-2rban, t1-2rbannnz · JP: duc · US: phat)
   │  src/processing/cleaner.py  (đọc → bóc tách → gán region_code → làm sạch → upsert theo lô)
   ▼
9 bảng                       configs/schema.sql     (bảng, khoá ngoại, dòng tạm, region_code)
   ▼
v_videos_analysis, v_cohort,  configs/labels.sql    (chỉ VN; bỏ backfill, cohort, 2 nhãn)
v_video_labels
   ▼
v_video_features              configs/features.sql  (khung giờ, biến kiểm soát, độ phủ VN, cờ làm sạch)
   ▼
kiểm tra: configs/checks.sql · minh chứng: notebooks/1_Exploration.ipynb
```

Mỗi lần chạy, loader tự áp dụng lại cả 3 file SQL (danh sách `sql_files` trong `configs/db_config.json`). Cả 3 file đều chạy lại được nhiều lần mà không gây lỗi.

## Đi một vòng: một file raw trở thành một dòng `is_clean` như thế nào

Phần này theo **một file trending** từ MinIO tới bảng phân tích, để thấy mỗi tầng làm gì. Các mục P1–P22 bên dưới giải thích chi tiết từng chỗ. Muốn tự xem dữ liệu: pgAdmin http://localhost:5050 (host `postgres`), hoặc DBeaver/CloudBeaver; ERD vẽ bằng "ERD For Schema" trên schema `public`.

**1. Tên file đã mang sẵn 4 thông tin (P5, P20).**
`raw/youtube/trending/dt=2026-10-23/t1-2rbannnz_230005_p01.json` → `parse_key()` tách ra:

| Phần trong tên | Giá trị | Dùng làm |
|---|---|---|
| `trending` | job | Quyết định đọc response theo kiểu nào, ghi vào bảng nào (P3) |
| `dt=2026-10-23` + `230005` | `captured_at` = 2026-10-23 23:00:05 UTC | Mốc chụp **chung** cho cả 4 trang của lần chạy (P5) |
| `t1-2rbannnz` | `crawler_id` | Truy vết máy nào crawl |
| `t1-2rbannnz` → `crawler_regions` | `region_code` = `VN` | Khu vực thu thập (P20) |

**2. Bóc envelope thành dòng cho từng bảng (P3, P4).**
Mỗi video trong `response.items` sinh ra:
- 1 dòng `videos` (metadata: tiêu đề, kênh, thời lượng `PT4M13S` → 253 giây, ...),
- 1 dòng `video_sources` ("video này được job `trending` của máy VN thấy lần đầu lúc ..."),
- 1 dòng `video_stats` (view/like/comment tại mốc chụp),
- 1 dòng `trending_snapshots` (video đứng ở trang `page_index`, vị trí `position` của chart VN).

**3. Khử trùng trong lô rồi ghi (P6, P7, P8).**
500 file gom thành một lô (`Batch`). Cùng một video xuất hiện nhiều lần trong lô thì chỉ giữ bản chụp muộn nhất. Lô ghi trong **một transaction** theo thứ tự: kênh/danh mục tạm → `videos` → bảng con → `raw_files`. Nếu lỗi giữa chừng thì không có gì được ghi, và lần chạy sau nạp lại đúng lô đó.

**4. Tầng view chọn dữ liệu dùng được (P11, P13, P20).** Dữ liệu trong bảng **không bao giờ bị xoá**. Mọi lựa chọn nằm ở view, và chạy lại được:

| View | Câu hỏi nó trả lời | Lọc gì |
|---|---|---|
| `v_videos_analysis` | Video nào dùng được để phân tích? | Bỏ video chỉ có ở backfill, video của kênh tạm, video không do máy VN thấy |
| `v_cohort` | Video nào có nhãn đáng tin? | Chỉ video do `uploads` của VN phát hiện, ra mắt trong khoảng chart VN được theo dõi đủ 72 giờ |
| `v_trending_rank` | Video đứng hạng mấy trong mỗi lần chụp? | Chỉ chart VN |
| `v_video_labels` | Video có lên trending trong 72 giờ đầu không? | Gắn 2 nhãn `is_trending_main`, `is_trending_category` |
| `v_video_features` | Video đăng khung giờ nào, nhãn 0 có đáng tin không? | Thêm khung giờ, biến kiểm soát, **độ phủ** (chart chính và chart danh mục), cờ, `is_clean`, `is_clean_category` |

**5. Vì sao cần `is_clean` (P15, P16).**
Nhãn 1 luôn đúng: đã thấy trên chart thì chắc chắn có trending. Nhãn 0 thì **có thể sai**, vì video có thể trending đúng lúc crawler tắt. Độ phủ (`coverage_72h`) đo crawler có mặt bao nhiêu phần trong 72 giờ đầu của **chính video đó**.
- Độ phủ thấp thì nhãn 0 không đáng tin, nên loại video đó.
- Video nhãn 1 có độ phủ thấp **cũng phải loại theo**. Tỉ lệ = trending / tổng, mà các nhãn 0 cùng hoàn cảnh đã bị loại khỏi mẫu số. Nếu giữ riêng nhãn 1 thì tỉ lệ bị thổi lên giả tạo. Ví dụ: tuần máy tắt có 100 video, 1 video trending được chụp, 99 video kia bị loại vì độ phủ thấp. Nếu giữ video trending thì tỉ lệ thành 1/1 = 100%.
- Chỉ khi **mô tả** video trending (danh mục nào, dài bao lâu), không cần mẫu số, thì mới dùng mọi nhãn 1.
- Hai nhãn có **hai tập sạch riêng**: `is_clean` (độ phủ chart chính ≥ 0,6) cho `is_trending_main`, `is_clean_category` (độ phủ chart danh mục ≥ 0,3) cho `is_trending_category`. Hai chart chạy theo lịch khác nhau nên crawler "có mặt" ở những giờ khác nhau (P15).

---

## P1. Thiết kế lược đồ database

- **Vấn đề.** Có 11 loại response khác nhau. Cần một lược đồ đủ để dựng mọi phân tích, và có khoá để chống trùng.
- **Cách giải.** Mỗi loại thông tin vào một bảng riêng:

  | Bảng | Khoá chính | Nội dung |
  |---|---|---|
  | `raw_files` | `object_key` | Nhật ký file đã nạp (truy vết MinIO → DB) |
  | `categories` | `category_id` | Danh mục video |
  | `channels` | `channel_id` | Kênh (bản mới nhất); `is_stub` đánh dấu kênh tạm |
  | `videos` | `video_id` | Metadata video (bản mới nhất) |
  | `video_sources` | `(video_id, source_job, region_code)` | Video được máy vùng nào thấy ở job nào, lần đầu khi nào |
  | `video_stats` | `(video_id, captured_at, source_job, region_code)` | View/like/comment tại từng lần chụp |
  | `trending_snapshots` | `(video_id, captured_at, source, category_id, region_code)` | Mỗi lần video có mặt trên chart (`main` hoặc `category`) của vùng nào |
  | `playlist_items` | `(video_id, playlist_id, captured_at)` | Danh sách video trong playlist kênh |
  | `discover_candidates` | `(channel_id, method, query_or_parent, captured_at)` | Kênh ứng viên của job `discover` |

- **Cài đặt.** `configs/schema.sql`.
- **Kết quả.** Cột `region_code` thêm ngày 30/10 (P20).

  | Bảng | 21/10 (chỉ VN) | 30/10 (VN + JP + US) | Trong đó VN / JP / US |
  |---|---:|---:|---|
  | `playlist_items` | 5.438.378 | 7.967.633 | (không tách vùng) |
  | `video_stats` | 1.906.571 | 2.723.654 | 2.037.032 / 552.816 / 133.806 |
  | `video_sources` | 924.378 | 1.621.859 | 1.025.456 / 323.281 / 273.122 |
  | `videos` | 244.451 | 439.870 | (dùng chung) |
  | `raw_files` | 165.393 | 241.202 | 176.023 / 52.215 / 12.964 file |
  | `trending_snapshots` | 140.640 | 180.459 | 158.930 / 9.597 / 11.932 |
  | `channels` | 7.382 | 19.219 | (dùng chung) |
  | `discover_candidates` | 4.976 | 28.911 | (không tách vùng) |
  | `categories` | 32 | 32 | (dùng chung) |

## P2. Đọc dữ liệu từ MinIO

- **Vấn đề.** Đề yêu cầu tầng Processing **đọc từ MinIO**, không đọc file trên máy.
- **Cách giải.**
  - Mặc định `--source minio`. Có thêm `--source local` để chạy thử nhanh trên `data/raw`.
  - Liệt kê object trên MinIO, bỏ các key đã có trong `raw_files`.
  - Tải song song 8 luồng, mỗi lô 500 file. Thông số đặt trong `db_config.json`.
- **Cài đặt.** `src/processing/cleaner.py` (`MinioSource`, `LocalSource`, `main`).
- **Kết quả.** Lần nạp đầu đọc 165 nghìn file trong khoảng 90 phút: tốc độ khoảng 70 file/giây lúc đầu, giảm còn khoảng 18 file/giây ở phần playlist.

## P3. Bóc tách envelope theo từng job

- **Vấn đề.** Mỗi job có cấu trúc response khác nhau, nên cần biết đọc trường nào và ghi vào bảng nào.
- **Cách giải.**

  | Job | Ghi vào |
  |---|---|
  | `trending`, `trending_category` | `videos`, `video_sources`, `video_stats`, `trending_snapshots` |
  | `uploads/videos`, `backfill/videos`, `stats` | `videos`, `video_sources`, `video_stats` |
  | `uploads/playlist_items`, `backfill/playlist_items` | `playlist_items`, `video_sources` |
  | `channels`, `discover/channels` | `channels` |
  | `discover/search` | `discover_candidates` (method `search`, kèm từ khoá) |
  | `discover/sections` | `discover_candidates` (chỉ mục loại `multipleChannels`) |
  | `videoCategories.list` | `categories` |
  | mọi file | `raw_files` |

  Hai chi tiết quan trọng:
  - `category_id` của `trending_category` lấy từ `request.params.videoCategoryId`.
  - Một video có thể đứng trên chart của nhiều danh mục trong cùng một lần chụp, nên `category_id` nằm trong khoá của `trending_snapshots`.
- **Cài đặt.** `cleaner.py` (`add_envelope`, `video_row`, `channel_row`).

## P4. Chuẩn hoá kiểu dữ liệu

- **Vấn đề.** API trả mọi thứ dưới dạng chuỗi, với định dạng riêng (thời lượng kiểu `PT1H2M3S`, số đếm kiểu `"12345"`).
- **Cách giải.**

  | Dữ liệu thô | Sau làm sạch |
  |---|---|
  | `2026-09-24T01:00:03Z` | `TIMESTAMPTZ` (UTC) |
  | `PT1H2M3S`, livestream `P0D` | `duration_s` = 3723; `P0D` → 0 |
  | `"12345"` | `BIGINT` |
  | like/comment bị chủ kênh ẩn (thiếu trường) | `NULL`, **không** điền 0 |
  | `caption: "true"/"false"` | `BOOLEAN` |
  | `tags: [...]` | `TEXT[]` |

- **Cài đặt.** `cleaner.py` (`parse_time`, `parse_duration`, `to_int`).

## P5. Thống nhất mốc thời gian chụp

- **Vấn đề.** Một lần chụp chart gồm 4 trang, mỗi trang có `crawl_time_utc` lệch nhau vài giây. Nếu dùng giá trị đó, các trang của cùng một lần chụp bị tính thành nhiều lần chụp khác nhau.
- **Cách giải.** `captured_at` lấy từ **tên object** (`dt=` + `HHMMSS`). Mọi trang của cùng một lần chạy có chung mốc này, nên tính được thứ hạng và so sánh được giữa các lần chụp.
- **Cài đặt.** `cleaner.py` (`parse_key`, `KEY_PATTERN`).
- **Hạn chế.** Mốc này là lúc **bắt đầu** lượt chạy, không phải lúc gọi API. Có 1.438 lần chụp video thường bị "chụp trước giờ đăng" dưới 1 giờ vì lý do này (check 6 trong P17).
  - Check 6b (30/10) đo độ trễ `crawl_time_utc − captured_at`: máy VN trễ trung vị 1–42 phút; máy JP 0–12 phút; **máy US trễ khoảng 7,2 giờ** ở `uploads/videos` và `stats` (lượt chạy rất dài). Vì vậy US có 1.661 dòng "chụp trước giờ đăng ≥ 1 giờ". Không ảnh hưởng phân tích VN; nếu sau này dùng đường view của US thì phải lấy `raw_files.crawl_time_utc` làm mốc.

## P6. Trùng lặp và phiên bản mới nhất

- **Vấn đề.** Một video xuất hiện ở hàng chục lần chụp, qua nhiều job. Cần giữ đúng 1 bản ghi metadata, và đó phải là bản mới nhất.
- **Cách giải.**
  - Dùng khoá chính và `INSERT ... ON CONFLICT` cho mọi bảng.
  - **Khử trùng ngay trong lô** (class `Batch`), vì Postgres không cho một câu `ON CONFLICT DO UPDATE` chạm cùng một khoá hai lần.
  - Với `channels` và `videos`:
    - Chỉ ghi đè khi bản mới có `last_seen_at` **muộn hơn**.
    - `first_seen_at` và `first_source_job` giữ theo bản **sớm nhất**.
    - Nhờ vậy, nạp file theo thứ tự nào cũng cho cùng kết quả.
  - Khoá của `video_stats` có thêm `source_job`, vì job `stats` và job `uploads` có thể chụp cùng một video vào cùng một mốc.
  - Từ 30/10, khoá của `video_sources`, `video_stats`, `trending_snapshots` có thêm `region_code`: cùng một video do máy VN và máy JP thấy là **2 dòng**, không đè nhau (P20).
- **Cài đặt.** `cleaner.py` (`Batch.keep_latest`, `UPSERT_SQL`).
- **Kết quả.** Check trùng khoá: 0 / 0 / 0.

## P7. Nạp lại an toàn: không mất, không nhân đôi

- **Vấn đề.** Lần nạp đầu dài khoảng 90 phút và có thể chết giữa chừng. Chạy lại không được nhân đôi dữ liệu, và cũng không được bỏ sót.
- **Cách giải.**
  - Mỗi lô 500 file ghi trong **một transaction**. Dữ liệu ghi trước, `raw_files` ghi **cuối cùng**. Lô lỗi thì không file nào bị đánh dấu là đã nạp, nên lần sau nạp lại.
  - Đọc lỗi thì thử lại 3 lần (`safe_read`). Vẫn lỗi thì ghi cảnh báo và **không** đánh dấu file đó.
- **Cài đặt.** `cleaner.py` (`write_batch`, `safe_read`).
- **Kết quả.**
  - Lượt nạp đầu từng dừng ở file 108.500 vì lỗi tạm thời `S3Error: IncompleteBody`. Sau khi thêm retry, lượt sau nạp nốt và không file nào lỗi.
  - Chạy lại lần thứ ba báo `0 file mới cần nạp`.

## P8. Toàn vẹn tham chiếu khi dữ liệu đến lệch thứ tự

- **Vấn đề.**
  - Job `trending` chạy mỗi giờ, còn `channels` chỉ 2 lần/ngày, nên video trending mới thường vào DB **trước** kênh của nó.
  - API Việt Nam không trả danh mục 29, nhưng có 527 video dùng mã này.
  - Có 26 video thuộc kênh mà `channels.list` không bao giờ trả về.
- **Vì sao cần.** Không có khoá ngoại thì ERD không có quan hệ và có thể có dữ liệu mồ côi. Còn nếu có khoá ngoại mà không xử lý gì, loader sẽ báo lỗi, hoặc phải bỏ video trending mới (mất positive).
- **Cách giải.**
  - **4 khoá ngoại:** `videos → channels`, `videos → categories`, `video_stats → videos`, `trending_snapshots → videos`.
  - **Dòng tạm (stub):** ngay trước khi ghi `videos`, loader chèn **kênh tạm** (chỉ có `channel_id`, `is_stub = true`) và **danh mục tạm** cho những mã chưa có.
    - Kênh tạm có `first_seen_at = infinity` và `last_seen_at = -infinity`, nên bản thật luôn thắng khi upsert.
    - Khi nạp `channels.list` của kênh đó, loader điền đủ thông tin và đặt `is_stub = false`.
  - Seed sẵn danh mục 29 ("Tổ chức phi lợi nhuận và Hoạt động xã hội").
  - **Không** đặt khoá ngoại cho `playlist_items` và `video_sources`: có 136.087 video chỉ xuất hiện trong playlist (video cũ, không gọi `videos.list`), nên không có trong `videos`. Đây là thiết kế có chủ ý.
- **Cài đặt.** `schema.sql` (khối `DO $$ ... $$`, bù dòng tạm cho dữ liệu cũ); `cleaner.py` (`channel_stubs`, `category_stubs`).
- **Kết quả.**
  - Check 8b: 0 vi phạm khoá ngoại.
  - Có 26 kênh tạm.
  - Đã thử nhánh kênh tạm bằng dữ liệu giả rồi rollback: kênh tạm được tạo đúng, và được điền đủ khi có bản thật.

## P9. Nạp tăng dần, tự động, tự nạp bù

- **Vấn đề.** Crawler ghi file mới mỗi giờ. Nếu lần nạp nào cũng quét toàn bộ 165 nghìn object thì mất 3,5 phút. Còn nếu chỉ quét vài ngày gần nhất mà máy tắt lâu hơn thế, sẽ bỏ sót dữ liệu.
- **Cách giải.**
  - Cờ `--recent-days 2`: chỉ liệt kê các phân vùng `dt=` gần nhất của từng job.
  - Khoảng ngày được lùi tới **ngày của file mới nhất đã nạp trừ 1**, nên máy tắt bao lâu thì lần chạy sau vẫn nạp bù đủ.
  - Quét toàn bộ (không có cờ) khi gộp dữ liệu từ máy khác.
  - `--recent-days` liệt kê theo ngày, **không** lọc theo máy crawl. Vì vậy file JP/US cùng ngày cũng được nạp. Điều này an toàn vì mỗi dòng đã mang `region_code` và view chỉ đọc VN (P20).
- **Cài đặt.** `cleaner.py` (`list_candidate_keys`); task "Nap DB" mỗi 3 giờ lúc :50, log ở `logs/load_db.log`.
- **Kết quả.**
  - Mỗi lần chạy mất khoảng 15 giây, so với 3,5 phút khi quét toàn bộ.
  - Đã thử với lần nạp cuối giả định cách đây 10 ngày: loader xét đủ 12 ngày.

## P10. Xác định đúng giờ ra mắt

- **Vấn đề.** Với livestream/premiere, YouTube **đổi `publishedAt` thành lúc phát xong**. Kết quả là có 12.259 lần chụp trông như "chụp trước giờ đăng".
- **Vì sao cần.** Giờ đăng là **biến trung tâm** của câu hỏi. Nếu sai thì gán sai khung giờ và sai cả cửa sổ 72 giờ.
- **Cách giải.** `release_at = COALESCE(actual_start_time, published_at)`: livestream lấy giờ bắt đầu phát, video thường lấy giờ đăng. Cohort, cửa sổ 72 giờ, giờ và thứ đăng (giờ Việt Nam) đều dùng `release_at`.
- **Cài đặt.** `configs/labels.sql` (`v_cohort`).
- **Kết quả.** 5.301 video có `release_at` khác `published_at`.

## P11. Xác định cohort: video có nhãn đáng tin

- **Vấn đề.** Không phải video nào trong DB cũng có nhãn đáng tin:
  - Video backfill được lấy **sau** khi đã đăng.
  - Video ra mắt trong 72 giờ cuối của khoảng crawl chưa được quan sát đủ.
- **Cách giải.** Cohort gồm các video:
  - do job `uploads` phát hiện,
  - có `release_at` nằm trong [lần chụp chart chính đầu tiên, lần chụp cuối − 72 giờ].
- **Cài đặt.** `labels.sql` (`v_cohort`).
- **Kết quả.** 137.264 video (21/10); 146.057 video (23/10); **156.311 video (30/10)**. Từ 30/10 cả 2 điều kiện chỉ tính trên máy VN: `uploads` của VN và khoảng chụp chart chính của VN (P20).

## P12. Gắn 2 nhãn trending

- **Vấn đề.** Nhãn phải phản ánh đúng "lọt trending sớm sau khi đăng". Hai loại chart mang ý nghĩa khác nhau.
- **Cách giải.**
  - **`is_trending_main`:** video có mặt trong chart chính trong khoảng [`release_at`, `release_at` + 72 giờ].
  - **`is_trending_category`:** tương tự, nhưng với chart theo danh mục. Nhận `NULL` nếu video ra mắt ngoài khoảng mà job `trending_category` theo dõi được đủ 72 giờ.
  - Hai nhãn **tách riêng, không gộp**.
  - Thêm `hours_to_trending_*` (số giờ tới lần đầu lên chart) và `best_rank_*` (thứ hạng cao nhất). Thứ hạng tính bằng `ROW_NUMBER()` theo từng lần chụp × nguồn × danh mục, trong view `v_trending_rank`.
- **Cài đặt.** `labels.sql` (`v_trending_rank`, `v_video_labels`).
- **Kết quả (21/10).** Chính: 964 video (0,70%). Danh mục: 2.009 / 74.208 (2,71%). Có cả 2 nhãn: 127.
- **Kết quả (30/10, check 12).** Chính: 1.029 / 156.311 (0,658%). Danh mục: 2.492 / 93.565 (2,663%). Có cả 2 nhãn: 138. Nhãn chỉ đếm chart **VN** (`v_trending_rank` lọc VN): video lên chart JP/US không được tính là trending VN.
- **Vì sao 1.508 video từng lên chart chính nhưng chỉ khoảng 960 video có nhãn 1** (phân tích ngày 21/10):
  - 298 video đăng trước khi bắt đầu crawl.
  - 167 video lên chart sau 72 giờ.
  - 42 video đăng trong 72 giờ cuối.
  - 39 video thuộc kênh không nằm trong `uploads`.
  - 962 video còn lại được tính là positive.
- **Đã thử và bỏ:** nới cửa sổ lên 7 ngày chỉ thêm 9 positive nhưng mất 33 nghìn video cohort, nên giữ cửa sổ 72 giờ.

## P13. Loại dữ liệu không dùng được cho phân tích

- **Vấn đề.**
  - Backfill không có nhãn đáng tin.
  - Video của kênh tạm thiếu biến kiểm soát.
  - Tuy vậy, đề yêu cầu **nạp hết** dữ liệu vào DB.
- **Cách giải.** Nạp đầy đủ vào DB, rồi loại ở **tầng view**:
  - `v_videos_analysis`: chỉ giữ video thấy ở ít nhất một job không phải `backfill/*`, và kênh không phải kênh tạm.
  - `v_stats_analysis`: chỉ giữ các lần chụp không phải backfill, của video thuộc `v_videos_analysis`.
- **Cài đặt.** `labels.sql`.
- **Kết quả.** 244.451 → **212.451 video**: bỏ 31.974 video chỉ có ở backfill và 26 video của kênh tạm. Không mất video trending nào trong cohort.

## P14. Biến khung giờ và biến kiểm soát

- **Vấn đề.** Câu hỏi cần biến khung giờ. Ngoài ra cần biến để kiểm tra nhiễu: kênh lớn hay đăng giờ riêng, thể loại khác nhau có lịch đăng khác nhau.
- **Cách giải.**

  | Cột | Định nghĩa |
  |---|---|
  | `time_slot` | `hanh_chinh` = 08:00–16:59, thứ 2–6, giờ VN; còn lại là `nghi` |
  | `slot_detail` | Tách giờ nghỉ thành tối ngày thường (17–24h), đêm/sáng ngày thường (0–8h), cuối tuần |
  | `day_part`, `is_weekend` | Đêm / sáng / chiều / tối; thứ 7 hoặc CN |
  | `subs_group`, `log10_subs` | < 10k, 10k–100k, 100k–1M, 1M–10M, > 10M; `log10(1 + subscriber)` |
  | `duration_group`, `is_short` | 6 nhóm thời lượng; ≤ 60 giây là Shorts |

- **Cài đặt.** `configs/features.sql` (`v_video_features`).

## P15. Nhãn 0 sai do crawler vắng mặt

- **Vấn đề.** Crawler chỉ có mặt khoảng 50% số giờ. Video lên trending đúng lúc crawler tắt bị gán nhầm nhãn 0.
- **Phân tích đã làm:**
  - Có 28 khoảng gián đoạn trên 3 giờ, chiếm khoảng 44% thời gian.
  - Video trending ở lại trên chart **trung vị 55 giờ**, P25 là 22 giờ, P10 là 6 giờ. Nghĩa là gián đoạn ngắn hiếm khi làm sót, nhưng gián đoạn dài thì có.
  - Độ phủ theo giờ trong ngày **thấp nhất lúc 10–13h** (25–39%), nằm trong giờ hành chính. Vì vậy so sánh thô **thiên vị bất lợi cho giờ hành chính**.
  - Bằng chứng nhãn bị sai: video mất dưới 12 giờ quan sát trong cửa sổ 72 giờ có tỉ lệ trending **1,38%**, so với **0,66%** ở video mất từ 12 giờ trở lên.
- **Đã thử và bỏ:** cờ `flag_crawl_gap` (gắn cho video có cửa sổ 72 giờ chạm một khoảng gián đoạn trên 3 giờ). Cờ này dính **cả 146.057 video**, nên vô dụng.
- **Cách giải.** Đo **độ phủ** thay vì đánh dấu gián đoạn:
  - `coverage_24h`, `coverage_72h` = tỉ lệ số giờ có lần chụp chart chính trong 24 giờ / 72 giờ đầu sau `release_at`.
  - Ngưỡng **0,6** (nhãn chính). Nhãn danh mục có độ phủ và ngưỡng riêng (0,3), xem mục "Độ phủ riêng cho chart danh mục" bên dưới.
- **Cài đặt.** `features.sql` (CTE `run_hours`, `coverage`; `category_runs`, `coverage_cat` cho chart danh mục).
- **Kết quả, phân tích độ nhạy:**

  | Ngưỡng độ phủ | Số video | Giờ hành chính | Giờ nghỉ | Giờ nghỉ / giờ hành chính |
  |---|---:|---:|---:|---:|
  | 0 (không lọc) | 146.057 | 0,43% | 0,80% | 1,85 |
  | 0,6 | 41.081 | 0,80% | 1,31% | 1,64 |
  | 0,8 | 11.590 | 1,36% | 1,88% | 1,38 |

- **Phân tích độ nhạy lại (giữ các cờ khác, chỉ đổi ngưỡng; notebook 1 mục 6, chạy lại 01/11):**

  | Ngưỡng | Số video | Trending chính | % hành chính | % nghỉ | Nghỉ / hành chính |
  |---|---:|---:|---:|---:|---:|
  | 0 | 154.194 | 885 | 0,322 | 0,699 | 2,17 |
  | 0,4 | 98.434 | 704 | 0,402 | 0,904 | 2,25 |
  | 0,5 | 77.895 | 622 | 0,452 | 0,986 | 2,18 |
  | **0,6** | 40.531 | 398 | 0,617 | 1,180 | 1,91 |
  | 0,7 | 20.586 | 276 | 0,853 | 1,730 | 2,03 |

  Bảng ghi 30/10 lệch nhẹ ở 2 dòng đầu (154.025 / 884 và 98.266 / 703); số trên đã kiểm lại bằng SQL. Cột trending danh mục của bảng cũ đã bỏ, vì nhãn danh mục giờ dùng độ phủ riêng (mục bên dưới).

  Ngưỡng cao thì **số** nhãn 1 giảm (video trending rơi vào giai đoạn crawler vắng cũng bị loại), nhưng **tỉ lệ** tăng (nhãn 0 sai bị loại nhiều hơn). Chênh lệch nghỉ / hành chính khoảng 2 lần ở mọi ngưỡng.
- **Vì sao chọn 0,6:** cân bằng giữa độ tin cậy nhãn và cỡ mẫu (0,8 chỉ còn khoảng 190 positive). Đây là ngưỡng **chọn theo kinh nghiệm**, được bảo vệ bằng bảng độ nhạy ở trên, không phải ngưỡng tối ưu theo công thức.
- **Hạn chế.**
  - Lọc theo độ phủ **làm thay đổi thành phần mẫu**: chỉ những ngày crawler chạy tốt được giữ lại. Ví dụ, tập sạch lệch mạnh về thứ 2 (phát hiện ở EDA cũ, cần kiểm tra lại khi làm EDA mới).
  - ~~Nghi lỗi: nhãn `is_trending_category` cũng dùng độ phủ của chart chính.~~ **Đã sửa 01/11**, xem mục dưới.

### Độ phủ riêng cho chart danh mục (01/11)

- **Vấn đề.** Trước 01/11, nhãn danh mục bị lọc theo độ phủ của chart **chính** (`run_hours` chỉ lấy `source = 'main'`). Chart danh mục chạy lịch riêng (job `trending_category`, mỗi 3 giờ từ 09/10), nên crawler "có mặt" với chart danh mục ở những giờ khác. Ở ngưỡng 0,7, số trending danh mục tụt từ 517 xuống 69.
- **Dữ liệu chart danh mục.** Chỉ **52 lần chụp trong 15 ngày** (09/10–24/10), tối đa 7 lần/ngày trên 8 lần theo lịch; 16–18/10 và 22/10 không có lần nào. 9 lần chạy chỉ chụp được 1–5 danh mục thay vì đủ 12.
- **Cách giải.**
  - Đếm theo **ô 3 giờ** kể từ `release_at` (khớp nhịp chạy của job): `coverage_cat_24h` = số ô có chụp / 8, `coverage_cat_72h` = số ô có chụp / 24. Nếu đếm theo giờ như chart chính thì độ phủ tối đa chỉ khoảng 0,33.
  - Chỉ tính lần chụp có **đúng danh mục của video**, vì lần chạy dở dang không quan sát các danh mục còn lại.
  - Tập sạch riêng `is_clean_category`: video có nhãn danh mục (không `NULL`), qua các cờ khác, và cả hai độ phủ danh mục ≥ **0,3**. Cột `is_clean` (nhãn chính) giữ nguyên.
- **Vì sao 0,3, không phải 0,6.** Độ phủ danh mục cao nhất chỉ đạt **0,708**; ngưỡng 0,6 còn 520 video và 12 nhãn 1. Tỉ lệ trending theo độ phủ cho thấy nhãn 0 đáng tin từ khoảng 0,2 (tỉ lệ đi ngang):

  | Độ phủ danh mục 72h | Số video | Tỉ lệ trending danh mục |
  |---|---:|---:|
  | 0–0,08 | 20.302 | 1,11% |
  | 0,13–0,17 | 11.872 | 2,12% |
  | 0,21–0,29 | 10.175 | 3,17% |
  | 0,33–0,38 | 2.734 | 3,55% |
  | 0,42–0,50 | 37.113 | 3,35% |
  | 0,54–0,58 | 9.452 | 3,00% |

  Khác với chart chính (tỉ lệ tăng mãi, không có điểm dừng), ở đây có đoạn đi ngang. Có thể vì video ở lại chart danh mục lâu, nên chụp thưa vẫn bắt được. 0,3 = ít nhất 3/8 ô trong 24 giờ đầu và 8/24 ô trong 72 giờ (0,3 và 0,33 cho cùng kết quả vì độ phủ chỉ nhận giá trị k/8, k/24).

- **Bảng độ nhạy (giữ các cờ khác, chỉ đổi ngưỡng độ phủ danh mục):**

  | Ngưỡng | Số video | Nhãn 1 | % hành chính | % nghỉ | Nghỉ / hành chính |
  |---|---:|---:|---:|---:|---:|
  | 0 | 92.444 | 2.441 | 2,05 | 2,89 | 1,41 |
  | 0,2 | 51.515 | 1.697 | 2,95 | 3,44 | 1,17 |
  | 0,25 | 47.941 | 1.580 | 3,00 | 3,42 | 1,14 |
  | **0,3** | **39.669** | **1.283** | **2,99** | **3,34** | **1,12** |
  | 0,4 | 20.018 | 643 | 3,05 | 3,32 | 1,09 |
  | 0,5 | 9.434 | 296 | 3,31 | 2,91 | 0,88 |
  | 0,6 | 520 | 12 | 2,20 | 2,48 | 1,13 |

- **Ý nghĩa.** Với nhãn danh mục, giờ nghỉ chỉ nhỉnh hơn giờ hành chính khoảng 1,1 lần, và ở ngưỡng 0,5 còn đảo chiều. Với nhãn chính là khoảng 2 lần ở mọi ngưỡng. "Thời điểm vàng" rõ với top chung, mờ với top theo danh mục; EDA phân tích riêng từng nhãn.
- **Kiểm chứng.** Sau khi thêm, số của nhãn chính khớp tuyệt đối với baseline 30/10 (40.531 / 398; hành chính 88, nghỉ 310; tổng `coverage_72h` 78.934,394).

## P16. Cờ làm sạch và tập `is_clean`

- **Vấn đề.** Cần một tập dữ liệu chính rõ ràng. Nhưng không được xoá dữ liệu gốc, để còn so sánh có lọc và không lọc.
- **Cách giải.** Chỉ **gắn cờ**, không xoá dòng. `is_clean` = không dính cờ nào (dùng cho nhãn chính). `is_clean_category` = không dính 3 cờ đầu và `flag_low_coverage_cat`, đồng thời có nhãn danh mục (dùng cho nhãn danh mục).

  | Cờ | Điều kiện | Số video (23/10) |
  |---|---|---:|
  | `flag_no_duration` | Thời lượng rỗng hoặc 0 giây (livestream chưa kết thúc, `P0D`) | 45 + 166 |
  | `flag_hidden_subs` | Kênh ẩn số subscriber | 0 |
  | `flag_extreme_duration` | Thời lượng > 3 giờ | 1.819 |
  | `flag_low_coverage` | `coverage_24h` < 0,6 hoặc `coverage_72h` < 0,6 | ≈ 105.000 |
  | `flag_low_coverage_cat` (01/11) | `coverage_cat_24h` < 0,3 hoặc `coverage_cat_72h` < 0,3 | 112.553 (53.378 trong số video có nhãn danh mục) |

- **Cài đặt.** `features.sql`.
- **Kết quả.**
  - 146.057 → **40.307 video sạch** (28%), trong đó **397 video trending chính**.
  - Giờ hành chính 14.071 video (34,9%); giờ nghỉ 26.236 video (65,1%).
  - **30/10:** 156.311 → **40.531 video sạch**, 398 trending chính, 517 trending danh mục. Hành chính 14.253 (88 main); nghỉ 26.278 (310 main). Không đổi sau khi nạp JP/US.
  - **01/11 (tập sạch riêng cho từng nhãn):**

    | Tập | Khung giờ | Số video | Nhãn 1 | Tỉ lệ |
    |---|---|---:|---:|---:|
    | `is_clean` (nhãn chính) | Hành chính | 14.253 | 88 | 0,617% |
    | | Nghỉ | 26.278 | 310 | 1,180% |
    | | **Tổng** | **40.531** | **398** | 0,982% |
    | `is_clean_category` (nhãn danh mục) | Hành chính | 11.736 | 351 | 2,991% |
    | | Nghỉ | 27.933 | 932 | 3,337% |
    | | **Tổng** | **39.669** | **1.283** | 3,234% |

    Hai tập chỉ trùng 14.765 video, nên mỗi nhãn được phân tích trên tập sạch của chính nó.

## P17. Kiểm tra chất lượng dữ liệu bằng SQL

- **Vấn đề.** Report 2 yêu cầu chứng minh dữ liệu đã về DB, và đánh giá chất lượng bằng SQL.
- **Cách giải.** File `configs/checks.sql`, 14 nhóm kiểm tra cộng 8b và 8c. Output lưu ở `reports/report2_sql_checks_output.txt`.

  | # | Kiểm tra | Kết quả (21/10) |
  |---|---|---|
  | 1–2 | Số dòng mỗi bảng; số file theo job | Khớp số object trên MinIO (165.393) |
  | 3 | Null ở cột quan trọng của `videos` | Chỉ có `duration_s` thiếu ở 75 video (livestream) |
  | 4 | Null số liệu tương tác | view 180 / 1,9 triệu; like 5,27%; comment 2,42% (chủ kênh ẩn) |
  | 5 | Trùng khoá | 0 |
  | 6 | Lần chụp trước giờ đăng | 12.259 dòng livestream (P10); 1.438 dòng video thường lệch dưới 1 giờ (P5); lệch từ 1 giờ trở lên: **0** |
  | 7 | View giảm giữa 2 lần chụp | 1,75%: YouTube lọc view ảo; ghi nhận, không sửa |
  | 8 / 8b / 8c | Dòng tạm; vi phạm khoá ngoại; danh sách khoá ngoại | 26 kênh tạm; **0** vi phạm; 4 khoá ngoại |
  | 9 | Khoảng trống giữa các lần chụp trending | Trung vị 1 giờ; dài nhất 94 giờ; 28 khoảng trên 3 giờ |
  | 10 | Số video mới theo ngày | Khoảng 2,5 nghìn/ngày lên 7–8,5 nghìn/ngày (sau khi `discover` mở rộng tập kênh) |
  | 11 | Số liệu có / không có backfill | Xem P13 |
  | 12–14 | Cohort, tỉ lệ nhãn, tỉ lệ theo khung giờ, theo danh mục | Xem P12 và EDA |

  **Cập nhật 30/10** (sau khi gộp JP/US; output `snapshots/region_merge_2026-10-30/checks_after_load.txt`):

  | # | Thay đổi | Kết quả 30/10 |
  |---|---|---|
  | 1b (mới) | Số dòng theo vùng của 3 bảng có `region_code` | Xem bảng P1 |
  | 2b (mới) | Số file theo máy crawl | `t1-2rbannnz` 175.746, `t1-2rban` 277, `duc` 52.215, `phat` 12.964 |
  | 5 | Kiểm tra trùng theo **khoá mới** (thêm `video_sources`, `trending_snapshots`) | 0 / 0 / 0 / 0 / 0 |
  | 6 | Tách theo vùng | VN: 28 dòng ≥ 1 giờ (có từ trước, lệch tối đa 1,38 giờ). US: 1.661 dòng, do lượt chạy dài (P5). JP: 0 |
  | 6b (mới) | Độ trễ lượt chạy theo máy | US trễ trung vị 430 phút ở `uploads/videos`, `stats` |
  | 8 / 8b | | 68 kênh tạm (551 video); **0** vi phạm khoá ngoại |
  | 9 | Khoảng trống giữa các lần chụp, tách vùng | VN 412 giờ có chụp, trung vị 1 giờ. JP 44 giờ. US 9 giờ |
  | 10, 11 | Chỉ tính VN; check 11 chỉ đếm video có dòng trong `videos` | 276.091 video VN, trong đó 244.148 không chỉ ở backfill |

## P18. Notebook làm sạch: minh chứng và quyết định

- **Vấn đề.** Report 3 yêu cầu **notebook làm sạch**. Logic làm sạch nằm trong SQL, nên cần một nơi kiểm chứng và giải thích từng quyết định.
- **Cách giải.** `notebooks/1_Exploration.ipynb` (Python, đọc `v_video_features` qua SQLAlchemy), gồm 9 mục:
  1. Đọc dữ liệu.
  2. Hình dạng dữ liệu.
  3. Giá trị thiếu.
  4. Trùng lặp và toàn vẹn.
  5. Ngoại lai: 166 video 0 giây; 1.819 video dài hơn 3 giờ; 115 kênh có 0 subscriber.
  6. Độ phủ crawler.
  7. **Bảng quyết định làm sạch**.
  8. Số video trước và sau làm sạch.
  9. Xuất mẫu `data/processed/video_features_sample.csv`.
- **Cài đặt.** Chạy bằng VS Code (kernel `.venv`) hoặc `uv run jupyter lab`. Ô thứ 2 mất khoảng 30–40 giây.

## P19. Sự cố vận hành của database

| Sự cố | Nguyên nhân | Cách xử lý |
|---|---|---|
| `could not resize shared memory segment ... No space left on device` | Container Postgres mặc định chỉ có `/dev/shm` 64 MB; join song song lớn bị thiếu bộ nhớ | `shm_size: 512mb` trong compose; `SET max_parallel_workers_per_gather = 0` trong `checks.sql` và các phiên phân tích |
| `set_session cannot be used inside a transaction` khi chạy `ANALYZE` | Còn transaction đang mở | `conn.commit()` trước khi bật `autocommit` |
| View `v_video_features` mất khoảng 35 giây | Tính độ phủ cho từng video trên 146 nghìn dòng | Chấp nhận vì phân tích chỉ đọc 1 lần; có thể chuyển sang materialized view nếu cần |
| `Connection refused` cổng 5432 | Docker Desktop tắt | Bật Docker; container có `restart: unless-stopped` |

## P20. Gộp dữ liệu nhiều khu vực: `region_code`

- **Vấn đề.**
  - Hai thành viên dùng chung code, đổi `REGION_CODE` và crawl trên máy riêng: **JP** (crawler `duc`, 28/09–26/10) và **US** (crawler `phat`, 01/10–26/10). Nhóm muốn gộp tất cả vào một DB.
  - Schema cũ không có khái niệm vùng. Nếu nạp thẳng vào thì có 4 lỗi âm thầm:
    1. **Nhãn bị lẫn.** Một video VN lên chart JP sẽ có `is_trending_main = 1`.
    2. **Cohort bị kéo giãn.** `crawl_range` lấy MIN/MAX lần chụp của cả 3 máy. Máy JP chạy tới 26/10 thì video VN đăng 21–24/10 lọt vào cohort, dù chart VN không được theo dõi đủ 72 giờ.
    3. **Độ phủ bị thổi phồng.** `run_hours` tính cả giờ máy JP/US chạy, nên video VN có độ phủ giả và qua `is_clean`, làm vô hiệu P15.
    4. **Đường view bị chen.** Lần chụp view của máy JP chen vào đường tăng view của video VN.
- **Cách giải.**
  - Thêm cột `region_code` (VN / JP / US) vào 3 bảng phụ thuộc vào "máy nào quan sát": `trending_snapshots`, `video_sources`, `video_stats`. Đưa cột này vào khoá chính, vì một video có thể có dòng ở nhiều vùng.
  - **Không** thêm vào `videos`, `channels`, `categories`, `playlist_items`. Đây là metadata chung, mỗi video/kênh chỉ có 1 dòng (bản mới nhất).
  - **`region_code` = khu vực của crawler đã thu thập**, không phải quốc gia của kênh (`channels.country`). Kênh VN mà discover của máy JP tìm ra vẫn tính là JP.
  - Vùng lấy từ **tên máy crawl** trong tên file, tra bảng `crawler_regions` trong `configs/db_config.json`. Lý do: chỉ file `trending`, `trending_category`, `discover/search` có `regionCode` trong request, còn file `uploads`, `stats`, `channels` thì không.
  - Mọi view trong `labels.sql` / `features.sql` lọc `region_code = 'VN'` (8 chỗ): `v_videos_analysis`, `v_stats_analysis`, `v_trending_rank`, `crawl_range` và join `uploads` của `v_cohort`, `category_range`, `run_hours`, `category_runs` (thêm 01/11).
- **Cài đặt.**
  - `schema.sql`: `ADD COLUMN IF NOT EXISTS region_code ... DEFAULT 'VN'` (dữ liệu cũ đều là VN, **không phải nạp lại**), rồi **bỏ DEFAULT**: loader quên gán vùng sẽ lỗi `NOT NULL` thay vì âm thầm thành VN. Khoá chính mới là `pk_video_sources`, `pk_video_stats`, `pk_trending_snapshots`.
  - `cleaner.py`: `parse_key()` trả thêm `region_code`. Có 2 chốt an toàn:
    - Crawler chưa khai báo thì **dừng trước khi nạp**.
    - Request ghi `regionCode` khác vùng đã khai báo thì báo lỗi.
- **Kiểm chứng.** Đo số liệu VN (số dòng, cohort, nhãn, `is_clean`, tỉ lệ theo khung giờ, tổng độ phủ) trước khi sửa, sau khi sửa, và sau khi nạp JP/US. Nhãn, cohort và `is_clean` **khớp tuyệt đối** qua cả 3 lần. Riêng tổng độ phủ lệch nhẹ (P22).
- **Truy vấn hay dùng.**
  ```sql
  -- Vùng đã thu thập video / vùng video trending / quốc gia kênh
  SELECT video_id, array_agg(DISTINCT region_code) FROM video_sources GROUP BY 1;
  SELECT video_id, array_agg(DISTINCT region_code) FROM trending_snapshots WHERE source = 'main' GROUP BY 1;
  SELECT v.video_id, c.country FROM videos v JOIN channels c USING (channel_id);
  ```
- **Kết quả (30/10).** Số video lên chart chính theo tập vùng: chỉ JP 3.697, chỉ VN 1.610, chỉ US 1.336, JP+US 11, JP+VN 5, US+VN 1, cả 3 vùng 3. Ba chart gần như tách biệt.
- **Hạn chế của dữ liệu JP/US.** Vì các lý do dưới đây, JP/US **chỉ dùng để mô tả** video trending, không dùng để tính tỉ lệ:
  - Chart chính chụp rất thưa: JP có 44 giờ có chụp trong 27 ngày, US có 9 giờ, so với 412 giờ của VN. Độ phủ của mọi video JP/US đều dưới 0,6, nên nhãn 0 không đáng tin.
  - Discover vẫn dùng `relevanceLanguage = 'vi'` và từ khoá tiếng Việt (đọc từ request trong raw). Phần lớn kênh tìm được có `country = VN`, nên negative của JP/US bị lệch.
  - Không có `trending_category`. Máy US trễ khoảng 7 giờ ở `uploads`/`stats` (P5).

## P21. Đưa raw của thành viên lên MinIO

- **Vấn đề.** Thành viên gửi thư mục `raw/` dạng zip (Google Drive chia JP thành 2 phần). Zip lẫn file mẫu `raw/sample/` của repo. Phải giữ nguyên dữ liệu thô và không đè dữ liệu VN.
- **Cách giải.** `python -m src.utils.import_raw_zip <zip...> [--dry-run]`:
  - Chỉ nhận entry đúng quy ước tên tầng raw. Bỏ `raw/sample/`, thư mục và file lạ.
  - Crawler chưa có trong `crawler_regions` thì dừng trước khi ghi.
  - Chép **nguyên byte** (không parse/ghi lại JSON) vào bucket `youtube-raw`. Object đã có thì bỏ qua.
  - `ZipFile` không an toàn khi nhiều luồng cùng đọc, nên script đọc tuần tự theo lô 500 file, chỉ phần ghi chạy 8 luồng.
- **Kết quả (30/10).** 65.179 file (JP 52.215, US 12.964), bỏ 25 entry khác. Tên file mang `crawler_id` riêng của từng máy (quy ước P5/C10), nên không đè file VN. Cleaner nạp 65.179 file trong 21,9 phút, 0 file lỗi.

## P22. Ảnh hưởng chéo qua bảng dùng chung

- **Vấn đề.** `videos` và `channels` dùng chung giữa các vùng, giữ **bản mới nhất** (P6). Máy JP/US có thể gọi `videos.list` cho video mà máy VN cũng theo dõi, vì discover của họ tìm ra kênh Việt.
- **Đo được (30/10).**
  - 273 video trong cohort VN có metadata được cập nhật bởi lượt chụp của máy JP/US (45 video trong đó là livestream có `actual_start_time`). Vì vậy `release_at` của vài video đổi, tổng độ phủ lệch rất nhẹ (82.782,704 → 82.782,371). Cohort, nhãn và `is_clean` không đổi.
  - `v_videos_analysis` tăng 296 video: video VN trước đây chỉ có trong playlist, nay có dòng `videos` nhờ máy JP/US gọi `videos.list`.
- **Đánh giá.** Chấp nhận được: metadata mới hơn thì đúng hơn (ví dụ `actual_start_time` chỉ có sau khi livestream bắt đầu). Điểm cần nhớ: số liệu VN **phụ thuộc nhẹ** vào dữ liệu JP/US qua 2 bảng này. Muốn tách tuyệt đối thì phải thêm `region_code` vào cả `videos`, nhưng không đáng so với mức ảnh hưởng.

---

## Kế hoạch từ đây tới EDA

Tập phân tích VN đã chốt (01/11): cohort 156.311; nhãn chính `is_clean` 40.531 video, 398 trending; nhãn danh mục `is_clean_category` 39.669 video, 1.283 trending. EDA cũ (Report 3, số liệu 23/10) **bỏ, làm lại** trên dữ liệu này. Mỗi bước làm xong thì dừng để giải thích và duyệt.

**Đã chốt 01/11:** dữ liệu dừng ở lần chụp cuối 24/10, không crawl thêm; ngưỡng độ phủ 0,6 cho nhãn chính, 0,3 cho nhãn danh mục; đóng băng tập phân tích bằng CSV.

| # | Bước | Vì sao | Sản phẩm |
|---|---|---|---|
| 1 | ✅ **Độ phủ riêng cho chart danh mục** (`coverage_cat_*`, `is_clean_category` trong `features.sql`) | Nhãn danh mục bị lọc theo lịch của chart **chính** (P15) | Xong 01/11, xem P15 |
| 2 | ✅ **Chốt ngưỡng độ phủ** cho từng nhãn bằng bảng độ nhạy | Ngưỡng phải có bằng chứng | Nhãn chính 0,6; nhãn danh mục 0,3 (P15) |
| 3 | ✅ **Đóng băng tập phân tích**: xuất `v_video_features` ra CSV (bản đầy đủ không commit, chỉ commit mẫu trong `data/processed/`) | View mất khoảng 17–90 giây mỗi lần đọc; số EDA không được trôi | `data/processed/video_features_full_2026-11-01.csv` (156.311 × 47, khớp DB) |
| 4 | ✅ **Sửa chỗ đọc thẳng bảng**: notebook 1 cell 16 lọc `region_code = 'VN'` (Rmd mới viết từ đầu cũng phải lọc) | Sau khi gộp sẽ lẫn giờ chụp JP/US | Xong 01/11 |
| 5 | ✅ **Chạy lại notebook làm sạch** (`1_Exploration.ipynb`), thêm mục 6b độ phủ danh mục | Minh chứng làm sạch phải khớp số mới | Notebook chạy từ đầu, số 01/11; mẫu 500 dòng 47 cột |
| 6 | ✅ **Data dictionary**: từng cột của `v_video_features` (kiểu, ý nghĩa, cách tính, khi nào `NULL`, giá trị); 9 bảng gốc mỗi bảng 7–10 dòng; view trung gian | Report 3 yêu cầu; có `region_code`, định nghĩa "khu vực thu thập" | [`reports/data_dictionary.md`](../../reports/data_dictionary.md) |
| 7 | ✅ (01/11: A–F và I xong, giải thích ở [03_eda.md](03_eda.md); G, H tuỳ chọn chưa làm) **EDA lại từ đầu** (`3_EDA.Rmd`), mỗi nhãn trên tập sạch riêng: A. tổng quan và độ lệch của tập sạch → B. phân phối → C. tỉ lệ trending theo thời điểm (kèm khoảng tin cậy Wilson) → D. kiểm soát nhiễu (quy mô kênh, danh mục, thời lượng, ảnh hưởng của vài kênh lớn) → E. chân dung video trending → F. nhãn danh mục → I. kết luận và đề xuất cho Report 4 | Câu hỏi "thời điểm vàng" trên dữ liệu đã chốt | `3_EDA.html`, `docs/analysis/03_eda.md` |
| 8 | (Tuỳ chọn) **So sánh mô tả JP/US**: chỉ dùng video **từng trending**, giờ đăng theo giờ địa phương (JP `Asia/Tokyo`; US chốt `America/New_York`) | Dữ liệu JP/US không tính được tỉ lệ (P20) | Một mục phụ trong EDA |
