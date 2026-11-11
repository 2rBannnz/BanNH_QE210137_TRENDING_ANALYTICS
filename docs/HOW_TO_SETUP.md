# Cài đặt và vận hành pipeline

Tài liệu dành cho người cài đặt, chạy và bảo trì hệ thống thu thập và nạp dữ liệu. Bối cảnh bài toán xem ở [README](../README.md).

Luồng dữ liệu:

```
YouTube Data API v3 ──crawler──▶ MinIO (raw JSON) ──loader──▶ PostgreSQL (bảng + view) ──▶ CSV đóng băng ──▶ EDA (RStudio)
   src/ingestion/crawler.py          bucket youtube-raw    src/processing/cleaner.py   configs/*.sql    notebooks/3_EDA.Rmd
```

## 1. Cài đặt lần đầu

### 1.1. Cần có

| Phần mềm | Ghi chú |
|---|---|
| Docker Desktop | Bật **Settings → General → Start Docker Desktop when you sign in**. Pipeline cần Docker chạy liên tục |
| Python 3.11 + [uv](https://docs.astral.sh/uv/) | Quản lý môi trường ảo `.venv` |
| YouTube Data API key | Google Cloud Console → bật **YouTube Data API v3** → Credentials → API key |

### 1.2. Các bước

1. Tạo file `.env` từ mẫu, rồi điền giá trị. Ý nghĩa từng biến có ghi chú ngay trong file.

   ```bash
   copy .env.example .env
   ```

   | Biến | Bắt buộc | Ghi chú |
   |---|---|---|
   | `YOUTUBE_API_KEY` | ✅ | Không commit |
   | `REGION_CODE` | | Khu vực crawl, mặc định `VN` |
   | `CRAWLER_ID` | ✅ | Định danh máy crawl: chữ thường, số, `_` hoặc `-` (ví dụ `ban`). Có trong tên file raw. Máy mới phải được khai báo trong `crawler_regions` của `configs/db_config.json` (mục 4.3) |
   | `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` | ✅ | Mật khẩu tối thiểu 8 ký tự |
   | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | ✅ | `POSTGRES_DB=youtube_trending_db` |
   | `POSTGRES_HOST`, `POSTGRES_PORT` | | Chạy trên máy: `localhost` / `5432`. Container `app` tự đổi thành `postgres` |
   | `PGADMIN_DEFAULT_EMAIL`, `PGADMIN_DEFAULT_PASSWORD` | ✅ | Đăng nhập pgAdmin |
   | `QUOTA_DAILY_BUDGET`, `QUOTA_CORE_RESERVE` | | Mặc định 9500 / 2500 (mục 3) |
   | `SAVE_LOCAL_COPY`, `LOCAL_DATA_DIR` | | Mặc định `true` / `data` (mục 4.3) |
   | `RSTUDIO_PASSWORD` | | Mật khẩu RStudio, user `rstudio` (mục 5.4) |

2. Cài thư viện Python. Có thể dùng `start.bat`: file này chạy `uv sync` rồi mở cmd đã kích hoạt `.venv`.

   ```bash
   uv sync
   ```

3. Bật MinIO, PostgreSQL và pgAdmin. Ba container này có `restart: unless-stopped`, nên tự bật lại mỗi khi Docker khởi động.

   ```bash
   docker compose up -d minio postgres pgadmin
   ```

4. Chạy thử crawler một lần (khoảng 4 unit quota):

   ```bash
   python -m src.ingestion.crawler --job trending
   ```

5. Nạp dữ liệu từ MinIO vào PostgreSQL. Lần đầu, loader tự tạo bảng và view:

   ```bash
   python -m src.processing.cleaner
   ```

6. Tạo lịch chạy tự động (mục 2).

Luôn đứng ở **thư mục gốc repo** và chạy bằng `python -m ...`. Không bấm nút ▶ của VS Code.

### 1.3. Địa chỉ các dịch vụ

| Dịch vụ | Địa chỉ | Đăng nhập |
|---|---|---|
| MinIO Console | http://localhost:9001 | `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` |
| MinIO API | `localhost:9000` | |
| PostgreSQL | `localhost:5432` | `POSTGRES_USER` / `POSTGRES_PASSWORD` |
| pgAdmin | http://localhost:5050 | `PGADMIN_DEFAULT_EMAIL` / `PGADMIN_DEFAULT_PASSWORD` |
| RStudio | http://localhost:8787 | `rstudio` / `RSTUDIO_PASSWORD` |

Kết nối pgAdmin tới DB lần đầu:
1. Chuột phải **Servers**, chọn **Register → Server**.
2. Tab **Connection**:
   - Host: `postgres`. Phải dùng tên service, không dùng `localhost`, vì pgAdmin chạy trong Docker.
   - Port: `5432`.
   - Database, user, password: lấy theo `.env`.

### 1.4. Chạy bằng container `app` (không cần cài Python)

Container `app` (`docker/app/Dockerfile`) có sẵn crawler và loader. Bên trong container, `MINIO_ENDPOINT=minio:9000` và `POSTGRES_HOST=postgres` được đặt sẵn.

Chạy loader (lệnh mặc định của container):

```bash
docker compose run --rm app
```

Chạy crawler trong container:

```bash
docker compose run --rm app python -m src.ingestion.crawler --job trending
```

`docker compose up` (không chỉ định service) sẽ chạy loader một lần trong container `app`, rồi container đó tự dừng. File đã nạp được bỏ qua, nên chạy lại vẫn an toàn.

## 2. Lịch chạy tự động (Windows Task Scheduler)

Các tác vụ nằm trong thư mục `\ADY201m\` của Task Scheduler:

| Tác vụ | Lệnh (sau `python -m`) | Lịch | Ghi chú |
|---|---|---|---|
| Trending | `src.ingestion.crawler --job trending` | Mỗi giờ, phút :00 | ~4 unit/lần |
| Stats | `src.ingestion.crawler --job stats` | Mỗi 3 giờ, phút :10 | Lệch 10 phút với trending để ít chạy chồng |
| Trending danh muc | `src.ingestion.crawler --job trending_category` | Mỗi 3 giờ, phút :40 | ~60 unit/lần |
| Uploads | `src.ingestion.crawler --job channels uploads` | 09:00 và 21:00 | `channels` phải chạy trước `uploads` để kênh mới vào cohort |
| Mở rộng dữ liệu | `src.ingestion.crawler --job discover backfill` | 14:30 | Ngay sau khi quota reset |
| **Nap DB** | `src.processing.cleaner --source minio --recent-days 2` | Mỗi 3 giờ, phút :50 | ~15 giây/lần; log ở `logs/load_db.log` |

**Trạng thái 01/11/2026:** đã dừng thu thập sau lần chụp ngày 24/10; cả 6 tác vụ đang ở trạng thái Disabled để số liệu phân tích không trôi. Bật lại trong Task Scheduler nếu cần crawl thêm (cohort, nhãn và tập sạch sẽ thay đổi).

Tác vụ "Mở rộng dữ liệu" tự đi đúng trình tự nhờ ngân sách quota. Những ngày đầu, `discover` dùng phần lớn quota dành cho job nặng. Khi đủ 2.500 kênh hoặc hết từ khoá, `backfill` nhận phần quota còn lại. Không cần đổi lệnh theo ngày.

### 2.1. Cách tạo một tác vụ

Mọi tác vụ chạy **ẩn** qua `conhost.exe --headless`. Nếu để hiện cửa sổ console, người dùng dễ đóng nhầm cửa sổ, làm job bị ngắt với mã `0xC000013A`.

| Ô | Giá trị |
|---|---|
| Program/script | `conhost.exe` |
| Add arguments | `--headless "<repo>\.venv\Scripts\python.exe" -m src.ingestion.crawler --job trending` |
| Start in | `<repo>` (thư mục gốc repo) |

Riêng tác vụ **Nap DB** cần ghi log ra file, nên phải chạy qua `cmd`:

```
--headless cmd.exe /c cd /d <repo> && set PYTHONIOENCODING=utf-8&& <repo>\.venv\Scripts\python.exe -m src.processing.cleaner --source minio --recent-days 2 >> <repo>\logs\load_db.log 2>&1
```

Cài đặt chung cho mọi tác vụ:
- **Conditions:**
  - Bật *Wake the computer to run this task*.
  - Bỏ *Start the task only if the computer is on AC power*.
- **Settings:**
  - Bật *Run task as soon as possible after a scheduled start is missed*.
  - Ở mục *If the task is already running*, chọn *Do not start a new instance*.

⚠️ Tác vụ chạy kiểu **"Run only when user is logged on"**:
- **Khoá màn hình** hoặc máy **sleep**: tác vụ vẫn chạy, vì máy được đánh thức.
- **Sign out**: mọi tác vụ dừng.

Muốn tác vụ chạy cả khi đã sign out thì chọn *Run whether user is logged on or not*; thao tác này cần quyền admin.

## 3. Quota YouTube API

Google cấp **10.000 unit/ngày/project**, reset lúc nửa đêm giờ Thái Bình Dương: **14:00 giờ Việt Nam** (15:00 từ tháng 11 đến tháng 3).

### Ngân sách tự động

Mọi lần chạy cộng dồn số unit đã dùng vào `state/quota/<ngày>.json` trên MinIO. Ngày được tính theo giờ Thái Bình Dương.

| Loại job | Job | Được dùng tới (tổng cả ngày) |
|---|---|---|
| Thiết yếu | `trending`, `trending_category`, `stats`, `channels`, `uploads` | `QUOTA_DAILY_BUDGET` = **9.500** |
| Nặng | `discover`, `backfill` | 9.500 − `QUOTA_CORE_RESERVE` (2.500) = **7.000** |

- **Job nặng chạm trần:** crawler ghi cảnh báo `dừng vì đủ ngân sách hôm nay`, bỏ qua job đó, chạy tiếp các job sau. Tiến độ đã được lưu, nên lần sau làm tiếp. Exit code vẫn là `0`.
- **Job thiết yếu chạm trần:** crawler dừng với exit code `2`.
- Bộ đếm chỉ tính các lần gọi qua code này. Mức dùng thật xem ở Google Cloud Console → APIs & Services → YouTube Data API v3 → **Quotas**.

### Chi phí từng job

| Job | Cách tính | Ví dụ thực tế |
|---|---|---|
| `trending` | ~4 unit/lần | 4 trang × 1 unit; 24 lần/ngày ≈ 96 unit |
| `trending_category` | 1 unit danh sách danh mục + 1 unit/trang | ~15 danh mục × ≤ 4 trang ≈ 60 unit/lần; 8 lần/ngày ≈ 480 unit |
| `channels` | 1 unit / 50 kênh | 200 kênh → 4 unit |
| `uploads` | ~1 unit/kênh + 1 unit / 50 video mới | 200 kênh → 235 unit |
| `stats` | 1 unit / 50 video đang theo dõi | 1.693 video → 34 unit |
| `discover` | Search: **100 unit/lần** (tối đa 60 lần/lượt chạy); mục nổi bật: 1 unit/kênh | Gần như toàn bộ chi phí nằm ở search |
| `backfill` | ~5–8 unit/kênh | Kênh đăng nhiều tốn tới ~10 unit (giới hạn 200 video) |
| Loader (`cleaner`) | 0 unit | Chỉ đọc MinIO, không gọi API |

**Không** dùng nhiều tài khoản/project Google để tăng quota cho cùng mục đích. Chính sách YouTube cấm việc này và có thể thu hồi key hoặc khoá tài khoản. Thành viên nhóm dùng key riêng để **chạy thử** code là hợp lệ.

## 4. Quy ước dữ liệu

### 4.1. Tầng raw (MinIO)

Đường dẫn object trên MinIO (bản local nằm ở `data/` với cùng cấu trúc):

```
raw/youtube/<job>/dt=<ngày UTC>/<crawler_id>_<giờ UTC HHMMSS>_p<số trang>.json
```

Các thư mục job:
- `trending/`
- `trending_category/`
- `channels/`
- `uploads/playlist_items/`, `uploads/videos/`
- `stats/`
- `discover/search/`, `discover/sections/`, `discover/channels/`
- `backfill/playlist_items/`, `backfill/videos/`

Mỗi file là một **envelope** bọc response nguyên văn của API. Xem ví dụ thật ở `data/raw/sample/`.

```json
{
  "crawler_id": "ban",
  "job": "trending",
  "crawl_time_utc": "2026-09-24T01:00:03Z",
  "request": {"endpoint": "videos.list", "params": {"...": "..."}},
  "page_index": 0,
  "response": { "...nguyên văn API trả về..." }
}
```

Nguyên tắc: **không sửa, không lọc, không bỏ bớt** những gì API trả về. `request.params` không chứa API key. Mọi xử lý (đổi múi giờ, gắn nhãn, loại trùng) đều làm ở tầng Processing.

### 4.2. Tầng state (MinIO)

`state/` chứa dữ liệu do code tự tính ra để điều khiển lần chạy sau, **không phải** dữ liệu nghiên cứu:

| File | Nội dung | Ghi bởi → đọc bởi |
|---|---|---|
| `state/channels.json` | Kênh đang theo dõi, playlist uploads, lần cuối thấy trong trending (chính hoặc danh mục), thời điểm được discover | `channels`, `discover` → `uploads`, `backfill`, `discover` |
| `state/tracked_videos.json` | Video mới đang theo dõi view (≤ 3 ngày tuổi) | `uploads` → `stats` |
| `state/discover.json` | Từ khoá đã tìm, kênh đã đọc mục nổi bật, kênh đã loại, ứng viên chưa xử lý | `discover` |
| `state/backfill.json` | Kênh đã backfill xong | `backfill` |
| `state/quota/<ngày>.json` | Tổng unit đã dùng trong ngày | `crawler` |

Xoá `state/` thì code vẫn chạy lại được, chỉ tốn thêm quota để dựng lại. Xoá `raw/` thì dữ liệu **mất vĩnh viễn**, vì các snapshot trending không thể thu thập lại.

### 4.3. Bản sao local và gộp dữ liệu nhiều máy

- `SAVE_LOCAL_COPY=true`: mỗi file raw được ghi thêm vào `data/raw/`. MinIO vẫn là bản chính; lỗi ghi đĩa chỉ tạo cảnh báo.
- `python -m src.utils.sync_local`: tải về `data/raw/` những file có trên MinIO nhưng chưa có bản local. Chạy lại bao nhiêu lần cũng an toàn.
- `python -m src.utils.sync_state`: tải `state/` về `data/state/` để xem hoặc sao lưu. Crawler luôn đọc state từ MinIO, nên sửa bản local không có tác dụng.
- `python -m src.utils.data_stats`: thống kê nhanh bản local, gồm số file, số video và số lần chụp trending.
- **Gộp dữ liệu từ máy khác** (thành viên crawl khu vực khác, 30/10):
  1. Khai báo máy mới trong `configs/db_config.json`, mục `crawler_regions` (ví dụ `"duc": "JP"`). Loader **dừng** nếu gặp `CRAWLER_ID` chưa khai báo, để không gán nhầm khu vực.
  2. Đưa file zip raw của thành viên lên MinIO, giữ nguyên byte; file đã có thì bỏ qua:

     ```bash
     python -m src.utils.import_raw_zip <file.zip> [--dry-run]
     ```

  3. Chạy loader **không kèm** `--recent-days` để quét toàn bộ.
  - Mỗi dòng của `trending_snapshots`, `video_sources`, `video_stats` có `region_code` = khu vực của máy đã crawl (không phải quốc gia của kênh). Mọi view phân tích chỉ dùng `region_code = 'VN'`.

## 5. Tầng processing (MinIO → PostgreSQL)

### 5.1. Loader

| Lệnh (sau `python -m src.processing.cleaner`) | Khi nào dùng |
|---|---|
| *(không tham số)* | Quét toàn bộ MinIO. Lần đầu, hoặc sau khi gộp dữ liệu (~3 phút liệt kê + thời gian nạp; lần đầu 165k file mất ~90 phút) |
| `--recent-days 2` | Lịch tự động: chỉ xét các ngày gần nhất, cộng thêm phần nạp bù kể từ lần nạp cuối (~15 giây) |
| `--source local` | Đọc `data/raw` thay vì MinIO, để chạy thử nhanh |
| `--prefix raw/youtube/trending/` | Chỉ nạp một job hoặc một ngày |

Mỗi lần chạy, loader:
1. Chạy `configs/schema.sql` (bảng, khoá ngoại), `configs/labels.sql` và `configs/features.sql` (view). Cả ba chạy lại vẫn an toàn.
2. Dừng nếu có file của máy crawl chưa khai báo trong `crawler_regions`.
3. Bỏ qua file đã có trong bảng `raw_files`.
4. Ghi mỗi lô 500 file trong một transaction.

Vì vậy loader **chạy lại bao nhiêu lần cũng không trùng**, và chết giữa chừng thì lần sau làm tiếp.

### 5.2. Bảng và view

| Bảng | Nội dung |
|---|---|
| `raw_files` | Nhật ký file đã nạp (lineage MinIO → DB) |
| `channels`, `videos`, `categories` | Bản mới nhất. `channels.is_stub = true` là **kênh tạm**: video vào trước kênh, lần nạp `channels` sau sẽ điền đủ |
| `video_stats`, `trending_snapshots` | Số liệu tại từng lần chụp; mỗi lần video có mặt trên bảng xếp hạng (`main` / `category`). Có cột `region_code` |
| `video_sources`, `playlist_items`, `discover_candidates` | Video thấy ở job nào (có `region_code`); playlist của kênh; kênh ứng viên |

| View | Nội dung |
|---|---|
| `v_videos_analysis`, `v_stats_analysis` | Dữ liệu dùng cho phân tích: **bỏ backfill** và bỏ video của kênh tạm |
| `v_trending_rank` | Thứ hạng liên tục trong từng lần chụp chart |
| `v_cohort` | Video mới (job `uploads`) được theo dõi đủ 72 giờ |
| `v_video_labels` | Feature cơ bản + 2 nhãn `is_trending_main`, `is_trending_category` (cửa sổ 72 giờ từ `release_at`) |
| `v_video_features` | **Bảng chính để phân tích/mô hình**: thêm khung giờ, biến kiểm soát, độ phủ crawler, cờ làm sạch, `is_clean` (nhãn chính) và `is_clean_category` (nhãn danh mục) |

Mọi view chỉ dùng dữ liệu máy crawl VN. Ý nghĩa từng cột: [`reports/data_dictionary.md`](../reports/data_dictionary.md).

### 5.3. Kiểm tra dữ liệu

```bash
docker exec -i ady201m_postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < configs/checks.sql
```

Kết quả mong đợi: các check có nhãn `[LỖI]` (trùng khoá, vi phạm khoá ngoại) đều bằng 0. Check 6 tách theo khu vực: máy US có lượt chạy dài (~7 giờ) nên có dòng lệch ≥ 1 giờ, đã giải thích ở check 6b.

### 5.4. Đóng băng tập phân tích và EDA

EDA đọc bản CSV đóng băng thay vì đọc view (view mất 1–2 phút mỗi lần đọc; số liệu không được trôi khi DB thay đổi). Xuất lại khi cần:

```bash
docker exec -i ady201m_postgres sh -c 'PGOPTIONS="-c timezone=UTC -c max_parallel_workers_per_gather=0" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\copy (SELECT * FROM v_video_features ORDER BY video_id) TO STDOUT WITH (FORMAT csv, HEADER)"' > data/processed/video_features_full_<ngày>.csv
```

File `data/processed/*_full_*.csv` bị `.gitignore` chặn; repo chỉ giữ mẫu `video_features_sample.csv` (xuất từ `notebooks/1_Exploration.ipynb`).

Knit EDA: mở `notebooks/3_EDA.Rmd` trong RStudio (http://localhost:8787) rồi bấm Knit, hoặc chạy từ máy (Git Bash cần `MSYS_NO_PATHCONV=1` để không đổi đường dẫn):

```bash
MSYS_NO_PATHCONV=1 docker exec -w /home/rstudio/project/notebooks ady201m_rstudio Rscript -e 'rmarkdown::render("3_EDA.Rmd")'
```

## 6. Theo dõi hằng ngày

Log nằm ở `logs/crawl_<ngày>.log` (crawler) và `logs/load_db.log` (loader).

| Dòng log | Ý nghĩa |
|---|---|
| `Quota ngày ...: đã dùng X/9500 unit` | Quota đã dùng trong ngày, tính đến lúc bắt đầu chạy |
| `Trending theo danh mục: N danh mục (bỏ qua ...), ... video khác nhau` | Kết quả chụp trending theo danh mục |
| `Discover: ... thêm N kênh Việt Nam, state có X/2500 kênh` | Tiến độ mở rộng kênh |
| `Backfill: ... M video từ K kênh (còn R kênh)` | Tiến độ lấy lịch sử; R = 0 là xong |
| `Uploads: ... thêm N video vào danh sách theo dõi` | Số video mới mỗi lần quét |
| `Job '...' dừng vì đủ ngân sách hôm nay` | Bình thường, lần sau làm tiếp |
| `Nguồn MinIO: N file mới cần nạp` | Loader: số file mới kể từ lần nạp trước. N = 0 suốt nhiều lần chạy nghĩa là crawler không chạy |
| `Nạp bù: lần nạp cuối ... -> xét N ngày gần nhất` | Loader đang nạp bù sau một thời gian máy tắt |
| `N file đọc lỗi, chưa nạp` | Lỗi tạm thời khi đọc MinIO; lần chạy sau tự thử lại |

Kiểm tra nhanh trạng thái tác vụ trong PowerShell:

```bash
Get-ScheduledTask -TaskPath '\ADY201m\' | Get-ScheduledTaskInfo | Select TaskName, LastRunTime, LastTaskResult, NextRunTime
```

`LastTaskResult` = `0` là thành công.

## 7. Xử lý sự cố

| Lỗi | Nguyên nhân | Cách sửa |
|---|---|---|
| `No module named 'src'` | Chạy bằng nút ▶ của VS Code hoặc sai thư mục | Đứng ở gốc repo, chạy `python -m ...` |
| `No module named 'googleapiclient'` / `'minio'` / `'psycopg2'` | Chưa kích hoạt môi trường ảo hoặc chưa `uv sync` | `uv sync`, rồi `.\.venv\Scripts\Activate.ps1` |
| `Thiếu biến trong .env: ...` | Thiếu biến hoặc để trống | Đối chiếu `.env.example` |
| Cảnh báo `thiếu gói tzdata` | Windows không có dữ liệu múi giờ | `uv sync` (hoặc `pip install tzdata`) |
| `UnicodeEncodeError: 'charmap' codec can't encode` | Output tiếng Việt đi qua pipe/redirect trên Windows | Đặt `PYTHONIOENCODING=utf-8` trước lệnh |
| `MaxRetryError` / `Connection refused` cổng 9000 | MinIO chưa chạy hoặc sai `MINIO_ENDPOINT` | `docker compose ps`; cổng 9000 là API, 9001 là Console |
| `connection to server at "localhost" ... port 5432 failed` | Docker Desktop hoặc container Postgres chưa chạy | Mở Docker Desktop; `docker compose up -d postgres` |
| `failed to connect to the docker API at npipe://...` | Docker Desktop đang tắt | Mở Docker Desktop |
| `Crawler chưa khai báo trong crawler_regions` | File raw của máy crawl mới | Thêm máy đó vào `crawler_regions` trong `configs/db_config.json` (mục 4.3) |
| `OCI runtime exec failed: ... Cwd must be an absolute path` | Git Bash đổi đường dẫn `/home/...` trong `docker exec -w` | Thêm `MSYS_NO_PATHCONV=1` trước lệnh |
| `InvalidAccessKeyId` / `SignatureDoesNotMatch` | User/password MinIO trong `.env` khác với container | Sửa `.env` cho khớp |
| MinIO liên tục khởi động lại | `MINIO_ROOT_PASSWORD` ngắn hơn 8 ký tự | Đổi mật khẩu dài hơn |
| `API key not valid` (400) | Sai API key | Lấy lại key từ Google Cloud Console |
| `accessNotConfigured` (403) | Project chưa bật API | Bật **YouTube Data API v3** |
| Exit code `2` | Hết quota hoặc job thiết yếu chạm ngân sách | Chờ quota reset lúc 14:00 giờ VN |
| `S3Error: IncompleteBody` | Lỗi mạng tạm thời khi đọc MinIO | Loader tự thử lại 3 lần; vẫn lỗi thì chạy lại loader |
| `could not resize shared memory segment ... No space left on device` | Container Postgres thiếu `/dev/shm` khi chạy query lớn | Compose đã đặt `shm_size: 512mb`; chạy `docker compose up -d postgres` để áp dụng. Trong psql: `SET max_parallel_workers_per_gather = 0;` |
| `LastTaskResult` = `3221225786` (`0xC000013A`) | Job bị ngắt (Ctrl+C), thường do đóng cửa sổ console | Dùng `conhost.exe --headless` (mục 2.1) |
| Tác vụ không chạy đúng giờ, log không có dòng mới | Đã sign out (tác vụ chỉ chạy khi đăng nhập), hoặc Docker tắt | Giữ đăng nhập (khoá màn hình thì được). Lịch sử Task Scheduler: chạy `wevtutil sl Microsoft-Windows-TaskScheduler/Operational /e:true` (cần admin) |
| `container name already in use` | Container của project Docker Compose cũ còn sót | `docker compose -p <tên-project-cũ> down -v` |
