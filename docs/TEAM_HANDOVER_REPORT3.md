# Bàn giao cho thành viên nhóm — Report 3 (Làm sạch, EDA, trình bày)

Phân công trình bày Report 3 cho 3 người, dàn ý slide, số liệu chốt và tài liệu nguồn của từng phần. Đọc kèm [`docs/analysis/`](analysis/README.md) (giải thích từng bài toán) và [`reports/data_dictionary.md`](../reports/data_dictionary.md).

## 1. Phân công

| Phần | Người trình bày | Ranh giới | Tài liệu nguồn |
|---|---|---|---|
| Mở đầu + Pipeline tự động | Thành viên 1 (đề xuất: `duc`) | Từ YouTube API tới lúc dữ liệu nằm trong 9 bảng PostgreSQL | [`analysis/01_crawl.md`](analysis/01_crawl.md), [`HOW_TO_SETUP.md`](HOW_TO_SETUP.md), P2, P7, P9, P19–P22 trong [`analysis/02_cleaning.md`](analysis/02_cleaning.md) |
| Làm sạch | Thành viên 2 (đề xuất: `phat`) | Từ 9 bảng tới bảng phân tích `v_video_features` và 2 tập sạch | [`analysis/02_cleaning.md`](analysis/02_cleaning.md) P1–P18, `notebooks/1_Exploration.ipynb`, `reports/data_dictionary.md` |
| EDA + kết luận | BanNH | Từ bản CSV đóng băng tới câu trả lời "thời điểm vàng" | [`analysis/03_eda.md`](analysis/03_eda.md), `notebooks/3_EDA.html` |

Dữ liệu JP/US (nếu muốn có): mỗi thành viên thêm 1 slide **mô tả** chart trending của khu vực mình (danh mục, thời lượng, giờ đăng theo giờ địa phương), đặt cuối phần của mình. Không tính tỉ lệ trending cho JP/US vì chart chụp quá thưa (JP 44 giờ, US 9 giờ; VN 412 giờ).

## 2. Số liệu chốt (01/11/2026) — 3 người dùng chung

| Chỉ số | Giá trị |
|---|---|
| Thời gian thu thập (máy VN) | 24/09 – 24/10/2026 |
| File raw trên MinIO | 241.202 (VN 176.023; JP 52.215; US 12.964) |
| Bảng PostgreSQL | 9 bảng, 4 khoá ngoại |
| Số giờ có chụp chart chính VN | 412 (khoảng 59% số giờ) |
| Cohort (video mới, theo dõi đủ 72 giờ) | 156.311 video, 1.029 trending chính |
| Tập sạch nhãn chính `is_clean` (độ phủ ≥ 0,6) | 40.531 video, 398 trending |
| Tập sạch nhãn danh mục `is_clean_category` (độ phủ ≥ 0,3) | 39.669 video, 1.283 trending |
| Kết quả chính (chart chính, nghỉ / hành chính) | Thô 1,91 → 1,47 (CI 1,04–2,02) sau kiểm soát ngày, quy mô kênh, danh mục → 1,24 (CI 0,93–1,69) thêm thời lượng |
| Định nghĩa Shorts | Video ≤ 3 phút (giới hạn của YouTube từ 15/10/2024), ước lượng theo thời lượng |
| Kết quả chart danh mục | Khoảng 1,0 sau kiểm soát (không khác biệt) |

## 3. Dàn ý slide (khoảng 33 slide, 50–60 phút)

### Mở đầu (Thành viên 1, 3 slide)
1. Tiêu đề, nhóm, người trình bày
2. Câu hỏi "thời điểm vàng", định nghĩa giờ hành chính và "lọt trending" (chart VN, cửa sổ 72 giờ)
3. Quy mô dữ liệu (số lớn): file raw, số bảng, cohort, giờ có chụp

### Phần 1 — Pipeline tự động (Thành viên 1, 7 slide)
| # | Slide | Nguồn |
|---|---|---|
| 1 | Sơ đồ kiến trúc Docker Compose (MinIO, Postgres, pgAdmin, app, RStudio) | `01_crawl.md`, `HOW_TO_SETUP.md` |
| 2 | 7 job crawl và vai trò: nhãn dương, nhóm so sánh, mở rộng kênh | C1–C7 |
| 3 | Lịch tự động (Task Scheduler, "Nap DB" mỗi 3 giờ) và ngân sách quota 10.000 unit | C8, C12 |
| 4 | Data lake MinIO: envelope, tên file, chứng minh dữ liệu vào lake | C10, C11 |
| 5 | Loader MinIO → Postgres: nạp tăng dần, chạy lại không trùng | P2, P7, P9 |
| 6 | Đa vùng: 3 máy crawl, `region_code`, `import_raw_zip`, hạn chế JP/US | P20–P22 |
| 7 | Sự cố vận hành: crawler chỉ có mặt khoảng 59% số giờ, khoảng tắt dài nhất 94 giờ (dẫn sang phần 2) | P19 |

### Phần 2 — Làm sạch (Thành viên 2, 9 slide)
| # | Slide | Nguồn |
|---|---|---|
| 1 | Lược đồ 9 bảng (ERD), 4 khoá ngoại, dòng tạm | P1, P8 |
| 2 | Data dictionary: nhóm cột của `v_video_features` | `reports/data_dictionary.md` |
| 3 | Chuẩn hoá: kiểu, thời lượng ISO → giây, like ẩn để NULL, `release_at` cho livestream | P4, P10 |
| 4 | Cohort: vì sao chỉ lấy video từ `uploads`, cửa sổ 72 giờ, 156.311 video | P11 |
| 5 | 2 nhãn (chart chính, chart danh mục), quy tắc NULL | P12 |
| 6 | Vấn đề lớn nhất: nhãn 0 sai do crawler vắng, ví dụ độ phủ | P15 |
| 7 | Chọn ngưỡng: bảng độ nhạy (chính 0,6), tỉ lệ đi ngang (danh mục 0,3) | P15 |
| 8 | Cờ làm sạch và phễu → `is_clean`, `is_clean_category` | P16, notebook 1 |
| 9 | Kiểm tra chất lượng bằng SQL: 0 trùng khoá, 0 vi phạm khoá ngoại, độ trễ máy US | P17 |

### Phần 3 — EDA (BanNH, 14 slide)
| # | Slide | Mục trong Rmd |
|---|---|---|
| 1 | Cách đọc kết quả: tỉ lệ, khoảng tin cậy, tỉ số | Đầu Rmd |
| 2 | Tập sạch không lệch khung giờ nhưng lệch ngày (thứ 2 chiếm 36%) | A |
| 3 | Giờ đăng và loại video: nhiều nhất 17–19h, Shorts (≤ 3 phút) 57%, 10 kênh chiếm 12% | B |
| 4 | Tỉ lệ trending theo giờ: đỉnh 16–18h | C1 |
| 5 | Hành chính và nghỉ; tối ngày thường cao nhất | C2, C3 |
| 6 | Dữ liệu bất thường: tỉ lệ nền giảm 1,32% → 0,44%; so trong cùng nhóm ngày | C4 |
| 7 | Độ vững theo ngưỡng độ phủ | C5 |
| 8 | Video "không thể trending": Shorts, Tin tức, Thể thao | D1, D2 |
| 9 | Sau kiểm soát: 1,91 → 1,47 → 1,24 | D3, D5 |
| 10 | Không do vài kênh lớn | D4 |
| 11 | Chân dung video trending | E |
| 12 | Chart danh mục: không khác biệt | F |
| 13 | Bảng kết luận và giới hạn | I1, I2 |
| 14 | Đề xuất cho Report 4 | I3 |

### Kết (1–2 slide)
Kết luận chung, Q&A.

## 4. Quy ước trình bày

- **Tiêu đề slide là kết luận** (ví dụ "Giờ nghỉ dễ lọt trending hơn khoảng 1,5 lần"), không phải tên biểu đồ.
- **Mỗi phép so sánh ghi rõ cách so sánh**: so nhóm nào với nhóm nào, mỗi nhóm bao nhiêu video.
- **Mỗi slide kết thúc bằng một dòng giới hạn** khi cần, ví dụ "chưa chứng minh giờ đăng gây ra trending".
- **Có slide bảng kết luận** cuối mỗi phần.
- **Dùng đúng số liệu ở mục 2**; nếu cần số khác, lấy từ `docs/analysis/` để 3 phần khớp nhau.

## 5. Câu hỏi dễ bị hỏi

| Câu hỏi | Trả lời ngắn | Ai trả lời |
|---|---|---|
| Vì sao không crawl liên tục 24/7? | Crawler chạy trên máy cá nhân, chỉ chạy khi máy bật và đăng nhập; đo bằng độ phủ thay vì giả định đủ | Thành viên 1 |
| Vì sao bỏ cả video đã trending khi độ phủ thấp? | Tỉ lệ = trending / tổng; nhãn 0 cùng hoàn cảnh bị loại thì nhãn 1 cũng phải loại, nếu không tỉ lệ bị thổi lên | Thành viên 2 |
| Vì sao ngưỡng 0,6 và 0,3? | Bảng độ nhạy: kết luận không đổi ở mọi ngưỡng; chart danh mục chụp mỗi 3 giờ, tỉ lệ đi ngang từ khoảng 0,2 | Thành viên 2 |
| Dữ liệu JP/US dùng để làm gì? | Chỉ mô tả; chart chụp quá thưa, không tính được tỉ lệ | Thành viên 1 |
| Tỉ lệ 1,9 lần có đáng tin không? | Bị phóng đại bởi loại video; sau kiểm soát còn khoảng 1,2–1,5 lần, không còn chắc chắn khi kiểm soát thêm thời lượng | BanNH |
| Có kết luận được giờ đăng **gây ra** trending không? | Không, dữ liệu quan sát; chỉ nói được "đi kèm" | BanNH |
