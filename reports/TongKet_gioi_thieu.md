# Báo cáo tổng kết học kỳ — Thời điểm vàng trên YouTube Việt Nam

<div class="cover">
<p class="course">ADY201m — AI, Data Science with Python &amp; SQL · FPT University</p>
<h1>Thời điểm vàng trên YouTube Việt Nam</h1>
<p class="sub">Báo cáo tổng kết toàn bộ đồ án từ đầu kỳ tới nay (Report 1 – Report 4)<br>Đề tài 4: Trending Content (YouTube)</p>
<table>
<tr><td>Câu hỏi nghiên cứu</td><td>Đăng video trong giờ hành chính hay giờ nghỉ thì dễ lọt Top Trending YouTube Việt Nam hơn?</td></tr>
<tr><td>Nhóm</td><td>BanNH — QE210137 (trưởng nhóm)<br>Nguyễn Lê Minh Đức (máy crawl JP, crawler_id <code>duc</code>)<br>Lâm Duy Phát (máy crawl US, crawler_id <code>phat</code>)</td></tr>
<tr><td>Thời gian</td><td>Repo tạo 07/09/2026 · thu thập dữ liệu 24/09 – 24/10/2026 · báo cáo chốt 15/11/2026</td></tr>
<tr><td>Repo</td><td><code>BanNH_QE210137_TRENDING_ANALYTICS</code> (GitHub, nhánh <code>main</code>)</td></tr>
<tr><td>Nộp kèm</td><td>Dữ liệu raw nhóm tự thu thập: 241.202 file JSON (3 file zip), danh sách SHA-256 từng file</td></tr>
</table>
<p class="note">Tài liệu gộp toàn bộ báo cáo của đồ án thành một file để đọc độc lập. Phần 1 tóm tắt cả kỳ; các phần sau là nguyên văn Report 1 – 4 (bản PDF riêng của từng report có cùng nội dung).</p>
</div>
<!-- TOC -->

## Tổng quan toàn kỳ

### Câu hỏi và kết luận

Đề tài hỏi: **đăng video trong giờ hành chính (08:00–16:59, thứ 2–6) hay giờ nghỉ thì dễ lọt Top Trending YouTube Việt Nam hơn**, khi đã tính tới ngày đăng, quy mô kênh, thể loại và thời lượng. Nhóm tự thu thập dữ liệu bằng YouTube Data API v3 trong một tháng, dựng pipeline Data Lake → Database → Analysis bằng Docker, làm sạch, phân tích khám phá bằng RStudio, rồi kiểm định giả thuyết bằng hai mô hình phân loại.

<div class="kq">
<p><strong>Kết luận cuối cùng: chưa đủ bằng chứng bác bỏ H₀.</strong> Tỉ lệ thô cho thấy giờ nghỉ lọt chart chính gấp 1,9 lần giờ hành chính, nhưng phần lớn chênh lệch đến từ <strong>loại video</strong> và <strong>ngày đăng</strong>. Sau khi kiểm soát, Logistic Regression cho odds ratio giờ nghỉ / giờ hành chính <strong>1,19 (CI 95% 0,81–1,72)</strong>; XGBoost xác nhận cùng chiều (biến khung giờ có permutation importance ≈ 0). Yếu tố quyết định là thể loại (Trò chơi, Âm nhạc), thời lượng (video dài 10–60 phút) và quy mô kênh. Trong phạm vi dữ liệu này không có "thời điểm vàng" theo nghĩa giờ hành chính so với giờ nghỉ.</p>
</div>

### Kết quả từng report

| Report | Yêu cầu của môn | Nhóm đã làm | Số liệu chính |
|---|---|---|---|
| 1 (10%) | Đề xuất, giả thuyết, kiến trúc Docker | Câu hỏi, H₀/H₁, định nghĩa thao tác, sáu bẫy dữ liệu và thiết kế tương ứng, 7 job thu thập, kiến trúc 5 container, cấu trúc repo | Quy tắc kết luận chốt trước: CI 95% của OR khung giờ chứa 1 hay không |
| 2 (20%) | MinIO trên Docker; pipeline Crawl → MinIO → DB; SQL kiểm tra | 7 job crawl tự động (Task Scheduler), Data Lake MinIO lưu nguyên văn, loader nạp tăng dần vào PostgreSQL (9 bảng, 4 khoá ngoại), gộp dữ liệu 3 khu vực, 14 nhóm SQL kiểm tra | 241.202 file raw; 156.311 video cohort VN; 0 trùng khoá, 0 vi phạm khoá ngoại |
| 3 (10%) | Notebook làm sạch, EDA bằng RStudio, data dictionary | Đo độ phủ crawler để sửa nhãn 0 sai, hai tập sạch, bảng độ nhạy; EDA A–F với khoảng tin cậy Wilson, Mantel–Haenszel, bootstrap theo kênh; data dictionary 47 cột | Tập sạch 40.531 video, 398 trending; thô 1,91 → 1,47 → 1,24 sau kiểm soát |
| 4 (20%) | 2 mô hình ML khác nhau kiểm định giả thuyết; đánh giá và so sánh | Tách train/test theo kênh, Logistic Regression (OR + bootstrap), XGBoost (tinh chỉnh 48 tổ hợp, ablation, permutation importance), so sánh trên tập test với 2 mô hình mốc | OR 1,19 (0,81–1,72); test PR-AUC XGBoost 0,228, LR 0,154, mốc 0,038 |
| 5 (20%) | Đóng gói Docker Compose, demo, bảo vệ | `docker-compose.yml` 5 service đã chạy suốt kỳ; demo và bảo vệ chưa tới lịch | — |

### Dòng thời gian

| Ngày | Việc |
|---|---|
| 07/09 – 11/09 | Tạo repo, cấu trúc thư mục theo yêu cầu môn, `docker-compose.yml` (MinIO, PostgreSQL, pgAdmin) |
| 24/09 | Crawler chạy tự động lần đầu (máy VN); lần chụp chart chính đầu tiên 24/09 23:52 giờ VN |
| 25/09 – 28/09 | Hoàn thiện các job `trending`, `channels`, `uploads`, `stats`, `discover`, `backfill` và quota tự động; Report 1 |
| 28/09 – 01/10 | Hai thành viên chạy cùng mã nguồn ở khu vực JP (`duc`) và US (`phat`) |
| 09/10 | Thêm job chart theo danh mục (`trending_category`) |
| 21/10 – 22/10 | Loader MinIO → PostgreSQL, 9 bảng, 4 khoá ngoại, nạp đầy đủ 165.393 file; SQL kiểm tra (Report 2) |
| 24/10 | Lần chụp cuối (06:00 giờ VN); dừng thu thập |
| 30/10 – 31/10 | Gộp dữ liệu JP/US vào cùng DB bằng `region_code`; thêm RStudio vào Docker |
| 01/11 | Độ phủ riêng cho chart danh mục; đóng băng bảng phân tích; EDA lại từ đầu; data dictionary (Report 3) |
| 11/11 | Sửa định nghĩa Shorts thành ≤ 3 phút theo quy định YouTube từ 15/10/2024; rà lại toàn bộ số liệu |
| 12/11 – 14/11 | Kế hoạch Report 4; tách train/test theo kênh; Logistic Regression; XGBoost (phat, duc); PDF Report 1–3 |
| 15/11 | Gộp kết quả, kết luận về giả thuyết, Report 4; báo cáo tổng kết và gói dữ liệu raw để nộp |

### Phân công

| Thành viên | Đóng góp |
|---|---|
| BanNH — QE210137 | Thiết kế câu hỏi, giả thuyết, kiến trúc; viết crawler, loader, schema, view; vận hành máy crawl VN; làm sạch và đo độ phủ; EDA khu vực VN; data dictionary; quy tắc kiểm định, tách dữ liệu, Logistic Regression, kết luận; viết các báo cáo |
| Nguyễn Lê Minh Đức | Chạy máy crawl khu vực JP (52.215 file raw); trình bày pipeline (Report 3); XGBoost: so có / bỏ biến thời gian, permutation importance, kiểm tra theo thời gian, bảng so sánh trên tập test (Report 4) |
| Lâm Duy Phát | Chạy máy crawl khu vực US (12.964 file raw); trình bày phần làm sạch (Report 3); XGBoost: huấn luyện, tinh chỉnh tham số, chọn ngưỡng (Report 4) |

Lịch sử Git (mọi nhánh, tới 15/11): 82 commit của BanNH, 12 của Lâm Duy Phát (`ZuniVer06`), 6 của Nguyễn Lê Minh Đức (`aries03298`); nhánh `main` có 87 commit. Commit theo quy ước conventional (`feat:`, `fix:`, `docs:`, `chore:`).

### Dữ liệu raw nộp kèm

Toàn bộ dữ liệu do nhóm **tự thu thập** bằng YouTube Data API v3 (không dùng bộ dữ liệu có sẵn). Mỗi file là response nguyên văn của API, bọc trong envelope ghi máy crawl (`crawler_id`), job, thời điểm gọi API và tham số request (không có API key). Tên file mang `crawler_id` và giờ chạy, nên dữ liệu của nhóm không thể trùng với dữ liệu của nhóm khác hay kỳ khác.

| File nộp | Khu vực | Máy crawl | Số file JSON | Khoảng thời gian |
|---|---|---|---:|---|
| `raw_VN_t1-2rbannnz.zip` | VN | `t1-2rbannnz` (175.746), `t1-2rban` (277) | 176.023 | 24/09 – 24/10/2026 |
| `raw_JP_duc.zip` | JP | `duc` | 52.215 | 28/09 – 26/10/2026 |
| `raw_US_phat.zip` | US | `phat` | 12.964 | 01/10 – 26/10/2026 |
| **Tổng** | | | **241.202** | |

- Đường dẫn trong zip giống tên object trên MinIO: `youtube/<job>/dt=<ngày UTC>/<crawler_id>_<HHMMSS>_p<trang>.json`.
- `MANIFEST_raw.csv`: mỗi dòng một file (khu vực, máy crawl, job, ngày, đường dẫn, kích thước, **SHA-256**), để đối chiếu từng file.
- `CHECKSUMS.txt`: SHA-256 của từng file zip và của manifest.
- Số file khớp tuyệt đối với bảng `raw_files` trong database (Report 2): mọi file đã được nạp, không file nào thiếu.

### Giới hạn chung của đồ án

1. Crawler chạy trên máy cá nhân nên chỉ có mặt 58,5% số giờ; nhóm xử lý bằng độ phủ crawler và tập sạch, nhưng tập sạch chỉ đến từ 14 ngày ra mắt.
2. Từ 07/2025 YouTube chỉ lấy chart `mostPopular` từ bảng Âm nhạc, Phim, Game, nên positive ít và lệch thể loại.
3. Dữ liệu quan sát: kết luận chỉ nói được giờ đăng **đi kèm** với khả năng trending hay không, không nói được **gây ra**.
4. Chỉ 398 video trending trong tập sạch (315 ở train mô hình), nên khoảng tin cậy rộng; CI của OR không loại trừ lợi thế tới 1,7 lần.
5. Dữ liệu JP/US chụp chart quá thưa nên chỉ dùng để mô tả; phân tích và mô hình chỉ dùng khu vực VN.
