# Phần 1 — Crawl: YouTube Data API → MinIO

[← Tổng quan](README.md) · [Phần 2 — Làm sạch →](02_cleaning.md)

**Mục tiêu của phần:** thu thập đủ **nguyên liệu thô** để sau này dựng được bảng "mỗi dòng = 1 video mới, biết giờ đăng, biết có lọt trending hay không, kèm biến kiểm soát". Phần này chỉ thu thập và lưu nguyên văn. **Không gắn nhãn, không làm sạch**, vì video đăng hôm nay có thể ngày mai mới lên trending.

## Tổng quan 7 job

```
trending ─┐
          ├─► channels ──► uploads ──► stats
trending_category ┘          ▲
                 discover ───┘──► backfill
```

| Job | Endpoint | Lịch | Bài toán |
|---|---|---|---|
| `trending` | `videos.list chart=mostPopular` | mỗi giờ, :00 | C1 |
| `trending_category` | `videoCategories.list` + `videos.list chart=mostPopular videoCategoryId=…` | mỗi 3 giờ, :40 | C2 |
| `channels` | `channels.list` | 09:00, 21:00 | C3 |
| `uploads` | `playlistItems.list` + `videos.list id=…` | 09:00, 21:00 (sau `channels`) | C4 |
| `discover` | `search.list`, `channelSections.list`, `channels.list` | 14:30 | C5 |
| `stats` | `videos.list id=…` | mỗi 3 giờ, :10 | C6 |
| `backfill` | `playlistItems.list` + `videos.list id=…` | 14:30 (sau `discover`) | C7 |

Khối lượng thu được (bảng `raw_files`, ngày 21/10):

| Job | Số file | Số item |
|---|---:|---:|
| `trending` | 1.546 | 76.489 |
| `trending_category` | 1.413 | 65.546 |
| `channels` | 783 | 37.583 |
| `uploads/playlist_items` | 121.017 | 5.243.825 |
| `uploads/videos` | 14.480 | 723.133 |
| `stats` | 18.873 | 935.374 |
| `backfill/playlist_items` | 4.470 | 199.312 |
| `backfill/videos` | 2.405 | 115.928 |
| `discover/search` | 104 | 5.202 |
| `discover/sections` | 204 | 1.469 |
| `discover/channels` | 98 | 4.823 |
| **Tổng** | **165.393** | (9,32 GB trên MinIO) |

---

## C1. Bắt được "khoảnh khắc" trending

- **Vấn đề.** API `mostPopular` chỉ trả bảng xếp hạng **tại thời điểm gọi**, không có lịch sử. Một video có thể chỉ ở trên chart vài giờ.
- **Vì sao cần.** Nhãn "lọt trending" chỉ dựng được từ một **chuỗi ảnh chụp** chart. Chụp thưa thì bỏ lỡ video trending ngắn, và video đó bị gán nhầm nhãn 0.
- **Cách giải.**
  - Chụp **mỗi giờ** toàn bộ chart chính VN: `videos.list(chart=mostPopular, regionCode=VN, maxResults=50)`, đi theo `nextPageToken`. Thường được 4 trang, khoảng 200 video.
  - Mỗi trang lưu thành 1 file.
  - Lấy kèm `statistics`, nên có luôn view của video tại thời điểm nó đang trending.
  - `MAX_PAGES = 10` chặn vòng lặp vô hạn nếu API trả `nextPageToken` bất thường.
- **Cài đặt.** `src/ingestion/jobs/trending.py`; task "Trending" chạy mỗi giờ lúc :00.
- **Kết quả.** 1.546 file, 398 lần chụp. **1.508 video** khác nhau từng xuất hiện trên chart chính. Tốn khoảng 4 unit/lần, 96 unit/ngày.
- **Hạn chế.** Độ chính xác chỉ tới mức giờ. Máy chạy crawler có lúc tắt nên nhiều giờ không có lần chụp (xem C12 và P15).

## C2. Trần số positive, tách 2 định nghĩa trending

- **Vấn đề.**
  - Chart chính chỉ có khoảng 200 video, mỗi ngày chỉ thêm khoảng 60 video trending mới.
  - Từ 21/07/2025, chart `mostPopular` chính chỉ lấy video từ các bảng xếp hạng Âm nhạc, Phim và Game.
  - Kết quả: positive rất ít và lệch về vài thể loại.
- **Vì sao cần.** Ít positive thì mọi so sánh đều kém chắc chắn. Video ở các thể loại khác gần như không bao giờ có nhãn 1.
- **Cách giải.**
  - Gọi `videoCategories.list(regionCode=VN, hl=vi)` để lấy các danh mục gán được (`assignable`).
  - Với từng danh mục, gọi `videos.list(chart=mostPopular, videoCategoryId=X)`, tối đa 4 trang (`MAX_PAGES_PER_CATEGORY = 4`).
  - Danh mục không có chart (API trả 400/404) thì bỏ qua, ghi vào log.
  - Lưu sang **thư mục raw riêng** `raw/youtube/trending_category/`, để tầng xử lý tạo được **2 nhãn tách riêng**: `is_trending_main` và `is_trending_category`.
- **Cài đặt.** `src/ingestion/jobs/trending_category.py`; task "Trending danh muc" chạy mỗi 3 giờ lúc :40, bắt đầu từ 09/10.
- **Kết quả.** 1.413 file. **4.990 video** khác nhau lên chart danh mục, gấp khoảng 3,3 lần chart chính. Tốn khoảng 60 unit/lần.
- **Hạn chế.**
  - Job bắt đầu muộn (09/10), nên nhãn danh mục chỉ có cho video ra mắt từ 09/10.
  - "Top của một danh mục" dễ đạt hơn "trending" nói chung, nên nhãn này mang nghĩa khác nhãn chính.

## C3. Biết cần theo dõi những kênh nào

- **Vấn đề.** Muốn lấy nhóm so sánh (C4) thì phải biết theo dõi kênh nào, và playlist uploads của từng kênh.
- **Cách giải.**
  - Đọc lại raw `trending` và `trending_category` của 7 ngày gần nhất (`LOOKBACK_DAYS = 7`) để lấy `channelId`. Chỉ đọc, không sửa raw.
  - Gọi `channels.list` theo lô 50 kênh, lưu raw (subscriber, quốc gia, playlist uploads...).
  - Cập nhật `state/channels.json`: `uploads_playlist`, `last_seen_trending_utc`. Entry cũ chỉ được cập nhật, không bị ghi đè, để giữ trường do job khác thêm vào (ví dụ `discovered_utc`).
- **Cài đặt.** `src/ingestion/jobs/channels.py`; chạy cùng `uploads` lúc 09:00 và 21:00, luôn chạy **trước** `uploads`.
- **Kết quả.** 783 file, 37.583 dòng.
- **Hạn chế.** Số subscriber là số **hiện tại** và đã bị YouTube làm tròn, không phải số tại thời điểm video đăng.

## C4. Nhóm so sánh: video **không** trending

- **Vấn đề.** Nếu chỉ có video trending thì không so sánh được gì. Ví dụ, "70% video trending đăng buổi tối" không chứng minh gì nếu 70% video nói chung cũng đăng buổi tối (thiên lệch người sống sót, survivorship bias).
- **Vì sao cần.** Cần **mọi** video mới của **cùng các kênh**, trong **cùng giai đoạn**, để so tỉ lệ lọt trending một cách công bằng.
- **Cách giải.**
  - **Chọn kênh để quét:** kênh do `discover` tìm ra (luôn quét), hoặc kênh có mặt trên chart trong 14 ngày gần nhất (`CHANNEL_ACTIVE_DAYS = 14`).
  - **Lấy video bằng playlist uploads:** `playlistItems.list`, 1 unit cho 50 video, rẻ hơn `search.list` 100 lần.
  - Chỉ lấy video đăng trong 7 ngày gần nhất (`UPLOAD_LOOKBACK_DAYS = 7`). Playlist xếp từ mới đến cũ, nên **gặp video cũ là dừng**. Tối đa 4 trang/kênh.
  - Playlist bị xoá (404) thì bỏ qua kênh đó, không làm hỏng cả job.
  - Gọi `videos.list` lấy chi tiết video mới (giờ đăng, thời lượng, view...).
  - Thêm video vào `state/tracked_videos.json` để job `stats` theo dõi.
- **Cài đặt.** `src/ingestion/jobs/uploads.py`; task "Uploads" (`--job channels uploads`) lúc 09:00 và 21:00.
- **Kết quả.** 121.017 file playlist (5,24 triệu dòng) và 14.480 file chi tiết video (723.133 dòng). Đây là **nguồn của cohort**: 146.057 video ngày 23/10.
- **Hạn chế.** Chỉ thấy video của các kênh trong danh sách theo dõi. Kết luận vì vậy chỉ đúng cho *các kênh Việt Nam đang hoạt động* trong tập này, không phải toàn bộ YouTube Việt Nam.

## C5. Mở rộng và đa dạng hoá tập kênh

- **Vấn đề.** Kênh lấy từ trending thiên về Game, Nhạc và kênh lớn, nên nhóm so sánh hẹp và lệch.
- **Cách giải.** Có 2 nguồn **ứng viên**:
  1. `search.list(type=channel)` theo **76 từ khoá** trong `configs/discover_keywords.txt`, phủ nhiều mảng nội dung. Mỗi từ khoá tối đa 3 trang, mỗi lần chạy tối đa 60 lệnh search, mỗi lệnh tốn 100 unit.
  2. `channelSections.list`: đọc mục "kênh nổi bật" (`multipleChannels`) của các kênh đã biết, mỗi lệnh 1 unit.

  Mọi ứng viên được tra bằng `channels.list` và **chỉ giữ kênh Việt Nam**: `country = VN`, hoặc không khai quốc gia nhưng `defaultLanguage` bắt đầu bằng "vi". Kênh bị loại được ghi vào `rejected_channels`.

  Thứ tự các bước được thiết kế để kênh tìm được không bao giờ bị mất vì hết quota:
  - **A.** Tra các ứng viên còn tồn từ lần trước.
  - **B.** Đọc mục kênh nổi bật.
  - **C.** Search theo từ khoá.
  - **D.** Tra các ứng viên mới.

  Ngoài ra:
  - Luôn chừa 200 unit (`LOOKUP_RESERVE_UNITS`) cho bước D.
  - Dừng khi state đã đủ 2.500 kênh (`TARGET_CHANNELS`).
  - Bỏ hẳn nguồn "kênh nổi bật" nếu đã đọc 200 kênh mà không ra ứng viên nào.
- **Cài đặt.** `src/ingestion/jobs/discover.py`; task "Mo rong du lieu" (`--job discover backfill`) lúc 14:30, ngay sau khi quota reset.
- **Kết quả.** 104 file search (5.202 kết quả); 204 file sections; 98 file tra cứu (4.823 kênh ứng viên). Bảng `channels` có **7.356 kênh** (21/10). Con số này vượt mục tiêu 2.500 vì job `channels` cũng thêm kênh.
- **Hạn chế.**
  - Kênh Việt Nam không khai quốc gia lẫn ngôn ngữ sẽ bị bỏ sót.
  - Nguồn "kênh nổi bật" gần như không ra ứng viên.
  - Tập kênh thiên về kênh tìm thấy được qua từ khoá.

## C6. Theo dõi tốc độ tăng view

- **Vấn đề.** Muốn biết video trending tăng view khác video thường ra sao thì cần nhiều ảnh chụp view theo thời gian.
- **Cách giải.**
  - Mỗi 3 giờ, gọi `videos.list` cho mọi video trong `state/tracked_videos.json`.
  - Chỉ theo dõi **3 ngày đầu** (`TRACK_DAYS = 3`). Video quá hạn tự bị bỏ khỏi danh sách, để quota không tăng mãi.
- **Cài đặt.** `src/ingestion/jobs/stats.py`; task "Stats" mỗi 3 giờ lúc :10, lệch 10 phút so với `trending` để ít chạy chồng.
- **Kết quả.** 18.873 file, 935.374 dòng. Dùng ở EDA phần 5.
- **Hạn chế.**
  - View là **hệ quả** của việc lọt trending, nên không được làm biến giải thích (leakage).
  - Chu kỳ 3 giờ khá thô.

## C7. Lịch sử đăng của kênh

- **Vấn đề.** Cần thông tin về thói quen đăng và quy mô của kênh, đồng thời tăng khối lượng cho Data Lake.
- **Cách giải.**
  - Mỗi kênh chỉ backfill **1 lần**: lấy video của 30 ngày gần nhất (`BACKFILL_DAYS = 30`), đọc 1 trang playlist (`MAX_PAGES_PER_CHANNEL = 1`, tối đa 50 video/kênh).
  - Tối đa 100 kênh mỗi lượt. Cứ xong 20 kênh thì lưu tiến độ một lần vào `state/backfill.json`.
  - Playlist bị xoá (404) thì đánh dấu kênh đã xong, để không thử lại mãi.
  - Video backfill **không** đưa vào `stats`.
- **Cài đặt.** `src/ingestion/jobs/backfill.py`; chạy sau `discover` trong task 14:30, dùng phần quota còn lại.
- **Kết quả.** 4.470 file playlist và 2.405 file chi tiết (115.928 dòng).
- **Hạn chế.**
  - **Không có nhãn đáng tin**: lúc những video này mới đăng, crawler chưa theo dõi chart cho chúng. Vì vậy chúng bị loại khỏi phân tích (P13).
  - Comment trong code vẫn ghi "tối đa 200 video/kênh", trong khi giá trị thật là 1 trang (50 video).

## C8. Ngân sách quota 10.000 unit/ngày

- **Vấn đề.** `search.list` tốn 100 unit/lần. Nếu job nặng dùng hết quota thì job thiết yếu (`trending`) không chạy được, và snapshot của giờ đó **mất vĩnh viễn**.
- **Cách giải.**
  - **Ngày quota** tính theo giờ Thái Bình Dương, vì Google reset quota lúc 14:00 giờ VN (15:00 từ tháng 11 đến tháng 3).
  - Tổng unit đã dùng lưu ở `state/quota/<ngày>.json` trên MinIO. Mọi lần chạy cộng dồn vào cùng chỗ. Trước khi ghi luôn đọc lại con số mới nhất, để giảm sai lệch khi hai lần chạy chồng nhau. Cứ 50 unit thì đồng bộ một lần.
  - **Hai mức trần:**
    - Job thiết yếu: 9.500 unit (`QUOTA_DAILY_BUDGET`).
    - Job nặng (`discover`, `backfill`): 9.500 − 2.500 (`QUOTA_CORE_RESERVE`) = 7.000 unit.
  - Kiểm tra ngân sách **trước** mỗi request:
    - Job nặng chạm trần thì dừng an toàn, crawler chạy tiếp job sau, exit code 0.
    - Job thiết yếu chạm trần thì crawler dừng với exit code 2.
  - Chi phí từng endpoint khai báo trong bảng `QUOTA_COST`.
- **Cài đặt.** `src/ingestion/quota.py` (`QuotaTracker`), `youtube_client.py`, `crawler.py` (`HEAVY_JOBS`, `job_limit`).
- **Hạn chế.**
  - Bộ đếm chỉ tính các lệnh gọi qua code này.
  - Không dùng nhiều project Google để lách quota, vì vi phạm chính sách YouTube.

## C9. Lỗi tạm thời của API và mạng

- **Vấn đề.** API trả lỗi 429/5xx, mạng chập chờn. Nếu không xử lý thì cả lượt crawl hỏng vì một lỗi tạm thời.
- **Cách giải.**
  - Thử lại tối đa 3 lần với 429, 500–504, `rateLimitExceeded` và lỗi mạng. Thời gian chờ tăng dần (2 giây, 4 giây...) cộng một khoảng ngẫu nhiên.
  - `quotaExceeded` / `dailyLimitExceeded`: dừng ngay, vì thử lại vô ích.
  - 400/401/404 (lỗi tham số, sai key): không thử lại.
  - Quota tính cả request bị lỗi, vì Google cũng tính như vậy.
  - API key truyền qua `developerKey`, nên **không nằm trong `params`** được lưu vào raw.
- **Cài đặt.** `src/ingestion/youtube_client.py` (`YouTubeClient.call`).

## C10. Lưu dữ liệu thô truy vết được (Data Lake)

- **Vấn đề.** Dữ liệu trending **không thu thập lại được**. Mọi bước xử lý phải chạy lại được từ dữ liệu gốc.
- **Cách giải.**
  - Mỗi response lưu **nguyên văn** trong một envelope: `{crawler_id, job, crawl_time_utc, request{endpoint, params}, page_index, response}`. Không sửa, không lọc, không bỏ bớt.
  - Tên object có dạng `raw/youtube/<job>/dt=<ngày UTC>/<crawler_id>_<HHMMSS>_p<NN>.json`:
    - Chia theo ngày (`dt=`) để liệt kê nhanh.
    - Mọi trang của cùng một lần chạy dùng chung `HHMMSS`.
    - `crawler_id` giúp gộp dữ liệu từ nhiều máy mà không bị đè.
  - MinIO là bản chính. Bản sao local nằm ở `data/raw/` (`SAVE_LOCAL_COPY`).
  - Tiện ích đi kèm: `sync_local` (tải raw về máy), `sync_state` (tải state), `data_stats` (thống kê nhanh).
- **Cài đặt.** `src/ingestion/raw.py`, `jobs/_helpers.py` (`save_raw`), `src/utils/minio_client.py`.
- **Kết quả.** 165.393 object, 9,32 GB.
- **Hạn chế.** `HHMMSS` là lúc **bắt đầu** lượt chạy, không phải lúc gọi API; lệch vài phút. Phần 2 xử lý điểm này ở P5.

## C11. Ghi nhớ tiến độ giữa các lần chạy

- **Vấn đề.** Job dài (`discover`, `backfill`) bị ngắt giữa chừng vì quota hoặc lỗi. Các job phụ thuộc nhau theo chuỗi `channels` → `uploads` → `stats`.
- **Cách giải.**
  - Dữ liệu điều khiển lưu ở `state/` trên MinIO: `channels.json`, `tracked_videos.json`, `discover.json`, `backfill.json`, `quota/`.
  - Lưu sau mỗi lô, nên lần chạy sau làm tiếp từ chỗ dừng.
  - Xoá `state/` không mất dữ liệu, chỉ tốn quota để dựng lại. Xoá `raw/` thì **mất vĩnh viễn**.

## C12. Chạy tự động, độ phủ thời gian

- **Vấn đề.** Crawler phải chạy liên tục nhiều tuần mà không cần người trông.
- **Cách giải.**
  - Task Scheduler, thư mục `\ADY201m\`:

    | Task | Lệnh | Lịch |
    |---|---|---|
    | Trending | `--job trending` | mỗi giờ :00 |
    | Stats | `--job stats` | mỗi 3 giờ :10 |
    | Trending danh muc | `--job trending_category` | mỗi 3 giờ :40 |
    | Uploads | `--job channels uploads` | 09:00, 21:00 |
    | Mo rong du lieu | `--job discover backfill` | 14:30 |

  - Task chạy ẩn qua `conhost.exe --headless`, tự đánh thức máy, và chạy bù khi lỡ giờ.
  - Container MinIO và Postgres có `restart: unless-stopped`.
- **Kết quả và hạn chế.**
  - **Chỉ khoảng 50% số giờ có lần chụp trending.** Có 28 khoảng gián đoạn trên 3 giờ, dài nhất 94 giờ. Độ phủ **thấp nhất lúc 10–13h (25–39%)**, nằm ngay trong giờ hành chính. Điểm này ảnh hưởng trực tiếp tới câu hỏi nghiên cứu (xem P15, EDA 1.2).
  - Task chỉ chạy khi đã **đăng nhập Windows**: khoá màn hình thì vẫn chạy, nhưng sign out thì dừng. **Docker Desktop phải đang chạy.**
  - Các khoảng mất dữ liệu đã biết:
    - 21/10 22:10 → 23/10 08:00 (Docker tắt).
    - Từ 24/10 06:00 không còn lần chụp nào.
  - `conhost --headless` làm Task Scheduler luôn báo mã 0, kể cả khi job lỗi.
  - Khi lỗi xảy ra trước lúc vào job, log ghi `Job 'None' thất bại` mà không có tên job.

## C13. Lấy đủ trường dữ liệu cho câu hỏi nghiên cứu

- **Vấn đề.** Mỗi endpoint chỉ trả các nhóm trường (`part`) được yêu cầu. Thiếu trường thì sau này không dựng được biến.
- **Cách giải.**

  | Hằng số | Các `part` | Dùng cho |
  |---|---|---|
  | `VIDEO_PARTS` | `snippet` | giờ đăng, kênh, danh mục, title |
  | | `contentDetails` | thời lượng |
  | | `statistics` | view, like, comment |
  | | `liveStreamingDetails` | giờ phát thật của livestream / premiere |
  | `CHANNEL_PARTS` | `snippet` | quốc gia, tuổi kênh |
  | | `statistics` | subscriber |
  | | `contentDetails` | playlist uploads |
  | (playlist) | `contentDetails` | `videoId`, ngày đăng |

  Xin thêm `part` **không tốn thêm quota**.
- **Cài đặt.** `src/ingestion/parts.py`.
- **Hạn chế.** API không còn trả số dislike từ 2021, nên đề tài không dùng biến này.
