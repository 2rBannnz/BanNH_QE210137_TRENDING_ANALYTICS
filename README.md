# Thời điểm vàng trên YouTube Việt Nam

**Đồ án ADY201m — Advanced Data Engineering & Science Bootcamp, FPT University**
Chủ đề 4: Trending Content (YouTube) · Thành viên: BanNH – QE210137

> Upload video vào **giờ hành chính** hay **giờ nghỉ ngơi** thì dễ lọt Top Trending hơn?

Repo này chứa toàn bộ pipeline: thu thập dữ liệu từ YouTube Data API v3 → Data Lake (MinIO) → làm sạch (PostgreSQL) → phân tích (RStudio) và mô hình hoá. README gồm hai phần: **Phần A** giải thích bài toán và vì sao dữ liệu được thu thập theo cách này; **Phần B** hướng dẫn cài đặt và chạy.

| Tài liệu | Nội dung |
|---|---|
| [`docs/HOW_TO_SETUP.md`](docs/HOW_TO_SETUP.md) | Cài đặt, lịch chạy tự động, quota, quy ước dữ liệu, xử lý sự cố |
| [`docs/analysis/`](docs/analysis/README.md) | Giải thích từng bài toán của 3 phần Crawl / Làm sạch / EDA, kèm số liệu thật |
| [`reports/data_dictionary.md`](reports/data_dictionary.md) | Ý nghĩa từng bảng, từng cột |

---

# PHẦN A — BÀI TOÁN

## 1. Câu hỏi và giả thuyết

**Đơn vị phân tích:** một video mới đăng, của một kênh YouTube Việt Nam đang được theo dõi.

**H₀:** Khả năng lọt trending của video đăng trong giờ hành chính **bằng** video đăng trong giờ nghỉ, khi đã kiểm soát ngày đăng, quy mô kênh, thể loại và thời lượng.
**H₁:** Hai khả năng này **khác nhau**.

Cách đánh giá:
- **Report 3 (EDA):** so tỉ lệ trending giữa các khung giờ, kèm khoảng tin cậy 95%, rồi kiểm soát từng yếu tố gây nhiễu (tỉ số Mantel–Haenszel, khoảng tin cậy bootstrap theo kênh). Không dùng kiểm định p-value.
- **Report 4 (mô hình):** Logistic Regression và XGBoost phân loại video có lọt trending hay không; so mức đóng góp của biến khung giờ khi có và không có các biến kiểm soát.

## 2. Định nghĩa

| Khái niệm | Định nghĩa trong đồ án |
|---|---|
| **Giờ ra mắt** (`release_at`) | `snippet.publishedAt`. Với Premiere/livestream, dùng `liveStreamingDetails.actualStartTime` (giờ khán giả thực sự xem được), vì YouTube đổi `publishedAt` thành lúc phát xong |
| **Giờ hành chính** | 08:00–16:59, thứ 2 đến thứ 6, giờ Việt Nam (UTC+7) |
| **Giờ nghỉ** | Mọi thời điểm còn lại: buổi tối, ban đêm, cả ngày thứ 7 và chủ nhật |
| **Lọt trending (chart chính)** | Xuất hiện trong ít nhất một lần chụp danh sách `mostPopular` khu vực VN trong vòng **72 giờ** kể từ lúc ra mắt |
| **Lọt trending (chart danh mục)** | Như trên, với danh sách `mostPopular` của từng danh mục (`videoCategoryId`). Hai nhãn tách riêng |
| **Độ phủ crawler** | Tỉ lệ số giờ có lần chụp chart trong 24 / 72 giờ đầu của video. Độ phủ thấp thì nhãn 0 không đáng tin |
| **Kênh Việt Nam** | Kênh có `country = VN`, hoặc không khai quốc gia nhưng ngôn ngữ mặc định là tiếng Việt |

## 3. Bảng dữ liệu đích

Mọi quyết định thu thập đều nhằm dựng được bảng `v_video_features`. Mỗi dòng là một video:

| video_id | giờ ra mắt (VN) | khung giờ | trending chính? | trending danh mục? | subscriber kênh | thể loại | thời lượng | độ phủ 72h |
|---|---|---|---|---|---|---|---|---|
| abc | 19:30 T6 | nghỉ | 1 | 1 | 2,1 triệu | Music | 4 phút | 0,75 |
| xyz | 10:00 T3 | hành chính | 0 | NULL | 2,1 triệu | Music | 3 phút | 0,64 |

Crawler chỉ thu thập nguyên liệu thô. Bảng này được dựng ở tầng Processing (`configs/labels.sql`, `configs/features.sql`).

## 4. Vì sao không chỉ cần "gọi API lấy trending"

Nếu chỉ lấy danh sách trending, nghiên cứu sẽ rơi vào sáu cái bẫy. Mỗi bẫy dẫn đến một quyết định thiết kế:

| # | Bẫy | Hậu quả nếu bỏ qua | Cách giải quyết |
|---|---|---|---|
| 1 | Trending là **khoảnh khắc**, API không lưu lịch sử | Video trending vài giờ bị bỏ lỡ, gán nhầm là "không trending" | Chụp trending **mỗi giờ**, lưu nguyên văn; đo **độ phủ** để loại video crawler không theo dõi đủ |
| 2 | Chỉ có video trending thì **không có gì để so sánh** (survivorship bias) | "70% video trending đăng buổi tối" không chứng minh được gì | Thu thập **mọi video** của cùng các kênh làm nhóm so sánh |
| 3 | Nhóm so sánh phải **công bằng** | Tìm video ngẫu nhiên cho ra video khác ngôn ngữ, khác thời kỳ | Nhóm so sánh lấy từ **chính các kênh đó**, cùng giai đoạn đăng |
| 4 | **Biến gây nhiễu**: kênh lớn vừa dễ trending vừa có thói quen đăng giờ riêng | Kết luận nhầm "giờ X là giờ vàng" | Thu thập số subscriber, thể loại, thời lượng làm biến kiểm soát |
| 5 | Định nghĩa trending đã **bị YouTube thay đổi** (07/2025) | Nhãn trending lệch về Âm nhạc/Game | Không có biến thay thế trong đồ án này — ghi nhận là **hạn chế** (mục 6). EDA xác nhận: 74% video trending chính là Trò chơi hoặc Âm nhạc |
| 6 | **Thời gian phức tạp**: API trả giờ UTC; Premiere có giờ phát sóng riêng; video có thể trending muộn | Lệch 7 tiếng, nhãn sai | Lưu giờ gốc, xử lý múi giờ và gắn nhãn ở tầng Processing, sau khi có đủ lịch sử |

## 5. Dữ liệu được thu thập như thế nào

### Bảy job, mỗi job trả lời một mảnh của câu hỏi

```
trending, trending_category ──► channels ──► discover ──► uploads ──► stats
                                                  └──────► backfill
```

| Job | Làm gì | Cung cấp cho nghiên cứu |
|---|---|---|
| `trending` | Chụp danh sách trending VN mỗi giờ (~200 video/lần) | **Nhãn chính** (`is_trending_main`), kèm thứ hạng |
| `trending_category` | Chụp trending theo từng danh mục mỗi 3 giờ | **Nhãn danh mục** (`is_trending_category`) |
| `channels` | Tra thông tin các kênh từng có video trending | **Biến kiểm soát**: subscriber, quốc gia |
| `discover` | Mở rộng danh sách kênh Việt Nam qua tìm kiếm theo từ khoá và mục "kênh nổi bật" | Tăng số kênh, **đa dạng thể loại** ngoài Âm nhạc/Game |
| `uploads` | Lấy **mọi** video mới đăng của các kênh đang theo dõi, 2 lần/ngày | **Nhóm so sánh** (video không trending) và **biến giải thích** (giờ đăng) |
| `stats` | Chụp view/like/comment của video mới mỗi 3 giờ trong 3 ngày đầu | Không dùng để kiểm định giả thuyết (view là hệ quả của lọt trending); giữ cho tham khảo |
| `backfill` | Lấy lùi video 30 ngày của mọi kênh, tối đa 50 video/kênh | Không có nhãn trending, không vào cohort; giữ cho khối lượng Data Lake |

Nhãn trending/không trending **không** được gắn lúc thu thập, vì một video đăng hôm nay có thể lên trending vào ngày mai. Việc này làm ở tầng Processing khi đã đủ 72 giờ quan sát.

### Số liệu thật (chốt 01/11/2026)

Thu thập từ **24/09 đến 24/10/2026** (máy crawl VN). Nhãn chỉ gắn cho video ra mắt từ lần chụp chart đầu tiên tới **lần chụp cuối trừ 72 giờ**, để mọi video có đủ 72 giờ quan sát.

| Tầng | Nguồn | Số lượng | Nhãn trending | Dùng cho |
|---|---|---|---|---|
| **Data Lake** | 7 job, 3 máy crawl (VN, JP, US) | 241.202 file raw | — | Lưu nguyên văn |
| **Cohort** | `uploads` của máy VN | 156.311 video, 1.029 trending chính | Có | Mẫu gốc |
| **Tập sạch nhãn chính** | Cohort, độ phủ chart chính ≥ 0,6 | 40.531 video, 398 trending | Có | Phân tích và mô hình chính |
| **Tập sạch nhãn danh mục** | Cohort, độ phủ chart danh mục ≥ 0,3 | 39.669 video, 1.283 trending | Có | Phân tích nhãn danh mục |

### Các biện pháp bảo đảm chất lượng

| Rủi ro | Biện pháp |
|---|---|
| Crawler vắng mặt làm nhãn 0 sai | Đo độ phủ cho từng video, chỉ phân tích tập `is_clean` / `is_clean_category`; bảng độ nhạy theo ngưỡng |
| Video đăng sát ngày chốt chưa kịp trending | Cohort chỉ gồm video có đủ 72 giờ quan sát |
| Vài kênh đăng rất nhiều áp đảo dữ liệu | Khoảng tin cậy bootstrap theo kênh; kiểm tra lại khi bỏ các kênh lớn |
| Rất ít video lọt trending so với không lọt | Dùng class weight; đánh giá bằng PR-AUC thay vì accuracy |
| Rò rỉ dữ liệu giữa tập train và test | Chia train/test **theo kênh**: mọi video của một kênh nằm cùng một phía |

## 6. Phạm vi và hạn chế

- **Định nghĩa trending đã thay đổi.** Từ 21/07/2025, chart `mostPopular` của YouTube Data API chỉ lấy video từ các bảng xếp hạng Âm nhạc, Phim và Game. Chart chính trong dữ liệu gần như không có Shorts, Tin tức, Thể thao.
- **Crawler chạy trên máy cá nhân, chỉ có mặt khoảng 59% số giờ.** Tập sạch chỉ đến từ 14 ngày ra mắt, nặng về thứ 2; kết luận phải kiểm soát ngày đăng.
- **Nhóm kênh không đại diện cho toàn bộ YouTube Việt Nam.** Kênh đến từ trending và từ tìm kiếm theo từ khoá, nên thiên về kênh đang hoạt động.
- **Không có dislike.** API không trả số dislike từ 2021; đề tài không dùng biến này.
- **Số subscriber là số tại lần chụp kênh mới nhất**, đã bị YouTube làm tròn.
- **Dữ liệu JP, US** (2 thành viên crawl) nằm cùng DB với cột `region_code` nhưng chụp chart quá thưa, chỉ dùng để mô tả.
- **Quota 10.000 unit/ngày** giới hạn tốc độ mở rộng; không dùng nhiều project để lách quota vì vi phạm chính sách của YouTube.

---

# PHẦN B — CHẠY DỰ ÁN

## 7. Kiến trúc

```
YouTube Data API v3
        │
        ▼
 [1] Ingestion (Python)    src/ingestion/  — 7 job, lưu JSON nguyên văn
        │
        ▼
   MinIO (Data Lake)       bucket youtube-raw (+ bản sao ở data/raw/)
        │
        ▼
 [2] Processing            src/processing/cleaner.py — đọc MinIO, chuẩn hoá, nạp tăng dần
        │                  configs/schema.sql, labels.sql, features.sql — 9 bảng, view cohort, nhãn, độ phủ
        ▼
   PostgreSQL              v_video_features (bảng phân tích)
        │
        ▼
 [3] Phân tích & mô hình   notebooks/1_Exploration.ipynb (làm sạch), notebooks/3_EDA.Rmd (RStudio)
```

| Container | Vai trò | Địa chỉ |
|---|---|---|
| `ady201m_minio` | Data Lake, lưu JSON thô | Console: `http://localhost:9001` |
| `ady201m_postgres` | Database sau khi làm sạch | `localhost:5432` |
| `ady201m_pgadmin` | Giao diện quản trị Postgres | `http://localhost:5050` |
| `ady201m_app` | Crawler và loader trong container (không cần cài Python) | — |
| `ady201m_rstudio` | RStudio cho EDA | `http://localhost:8787` |

## 8. Cài đặt

**Yêu cầu:** Docker Desktop, Python 3.11+ với [uv](https://docs.astral.sh/uv/), một YouTube Data API key (Google Cloud Console → bật **YouTube Data API v3**).

```powershell
git clone <repo-url>
cd BanNH_QE210137_TRENDING_ANALYTICS

# 1. Tạo .env từ mẫu rồi điền giá trị thật (KHÔNG commit .env)
copy .env.example .env

# 2. Bật hạ tầng
docker compose up -d minio postgres pgadmin rstudio
docker compose ps

# 3. Cài Python
uv sync
```

Các biến quan trọng trong `.env` (xem đầy đủ trong `.env.example` và [`docs/HOW_TO_SETUP.md`](docs/HOW_TO_SETUP.md)):

| Biến | Ý nghĩa |
|---|---|
| `YOUTUBE_API_KEY` | API key của bạn |
| `REGION_CODE` | Khu vực crawl (mặc định `VN`) |
| `CRAWLER_ID` | Định danh máy crawl (chữ thường, số, `_`, `-`), gắn vào tên mọi file; phải khai báo trong `crawler_regions` của `configs/db_config.json` |
| `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` | Phải khớp với container MinIO |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Database `youtube_trending_db` |
| `RSTUDIO_PASSWORD` | Mật khẩu RStudio (user `rstudio`) |
| `QUOTA_DAILY_BUDGET`, `QUOTA_CORE_RESERVE` | Ngân sách quota theo ngày (mặc định 9.500 và 2.500) |

## 9. Chạy

Luôn chạy bằng `python -m` từ **thư mục gốc repo**.

```powershell
# Crawl (lịch tự động bằng Task Scheduler, xem docs/HOW_TO_SETUP.md mục 2)
python -m src.ingestion.crawler --job trending               # mỗi giờ
python -m src.ingestion.crawler --job trending_category      # mỗi 3 giờ
python -m src.ingestion.crawler --job stats                  # mỗi 3 giờ
python -m src.ingestion.crawler --job channels uploads       # 09:00 và 21:00
python -m src.ingestion.crawler --job discover backfill      # 14:30, ngay sau khi quota reset

# Nạp MinIO -> PostgreSQL (lần đầu không tham số; lịch tự động dùng --recent-days 2)
python -m src.processing.cleaner --recent-days 2

# Kiểm tra chất lượng dữ liệu
docker exec -i ady201m_postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < configs/checks.sql
```

Exit code của crawler: `0` thành công · `1` lỗi · `2` hết quota. Log ở `logs/crawl_<ngày>.log` và `logs/load_db.log`.

EDA: mở `notebooks/3_EDA.Rmd` trong RStudio (`http://localhost:8787`) rồi Knit. Notebook đọc bản đóng băng `data/processed/video_features_full_2026-11-01.csv` (xem `docs/HOW_TO_SETUP.md` mục 5.4).

## 10. Cấu trúc thư mục

```
├── README.md
├── AI_Log.md                 # Nhật ký sử dụng AI
├── docker-compose.yml        # MinIO, PostgreSQL, pgAdmin, app, RStudio
├── docker/app/Dockerfile     # Container crawler + loader
├── docker/rstudio/Dockerfile # Container RStudio cho EDA
├── requirements.txt, pyproject.toml
├── .env.example              # Mẫu biến môi trường
├── configs/
│   ├── db_config.json        # Kết nối DB, file SQL, crawler_regions
│   ├── schema.sql            # 9 bảng, khoá ngoại, region_code
│   ├── labels.sql            # Cohort, 2 nhãn trending (chỉ VN)
│   ├── features.sql          # v_video_features: khung giờ, độ phủ, cờ làm sạch
│   ├── checks.sql            # Kiểm tra chất lượng dữ liệu
│   └── discover_keywords.txt # Từ khoá tìm kênh cho job discover
├── src/
│   ├── ingestion/            # crawler.py + 7 job trong jobs/
│   ├── processing/cleaner.py # Loader MinIO -> PostgreSQL
│   ├── modeling/             # Mô hình (Report 4)
│   └── utils/                # config, minio_client, sync_local, sync_state, import_raw_zip, data_stats
├── data/raw/sample/          # Mẫu raw (mỗi job 1 file)
├── data/processed/           # Mẫu CSV của các bảng (bản đầy đủ không commit)
├── notebooks/                # 1_Exploration.ipynb (làm sạch), 3_EDA.Rmd/.html (EDA)
├── docs/                     # HOW_TO_SETUP.md, analysis/ (giải thích từng bài toán)
└── reports/                  # Báo cáo, data dictionary
```

## 11. Tiến độ

| Report | Nội dung | Trạng thái |
|---|---|---|
| 1 | Giả thuyết, kiến trúc | Đang hoàn thiện |
| 2 | Pipeline Crawl → MinIO → DB | Xong: 7 job chạy tự động, loader nạp tăng dần, `checks.sql` 0 lỗi |
| 3 | Làm sạch, EDA, Data Dictionary | Phân tích xong (notebook làm sạch, `3_EDA.html`, `reports/data_dictionary.md`); báo cáo và slide đang làm |
| 4 | Hai mô hình phân loại, chấp nhận / bác bỏ giả thuyết | Chưa bắt đầu |
| 5 | Đóng gói Docker Compose, bảo vệ | Chưa bắt đầu |
