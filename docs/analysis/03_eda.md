# Phần 3 — EDA: thời điểm vàng đăng video

[← Phần 2 — Làm sạch](02_cleaning.md) · [Tổng quan](README.md)

**Mục tiêu của phần:** trả lời câu hỏi "đăng video trong **giờ hành chính** (08:00–16:59, thứ 2–6, giờ VN) hay **giờ nghỉ** thì dễ lọt **Top Trending** YouTube Việt Nam hơn", và kiểm tra câu trả lời đó có đứng vững khi loại bỏ các yếu tố khác đi kèm giờ đăng hay không.

## Dữ liệu và cách làm

```
v_video_features ─► data/processed/video_features_full_2026-11-01.csv ─► notebooks/3_EDA.Rmd ─► 3_EDA.html
(view, 156.311 video)      (bản đóng băng, 47 cột, không commit)          (RStudio container)
```

- **Bản đóng băng** mốc 01/11: dữ liệu chụp tới 24/10, không crawl thêm. EDA đọc CSV chứ không đọc view, vì view mất khoảng 1,5 phút mỗi lần đọc và số liệu không được trôi khi DB thay đổi.
- **Mỗi nhãn một tập sạch** (P15, P16 ở [02_cleaning.md](02_cleaning.md)):

  | Nhãn | Tập sạch | Số video | Trending |
  |---|---|---:|---:|
  | `is_trending_main` (chart chính) | `is_clean` (độ phủ chart chính ≥ 0,6) | 40.531 | 398 |
  | `is_trending_category` (chart danh mục) | `is_clean_category` (độ phủ chart danh mục ≥ 0,3) | 39.669 | 1.283 |

- **Tỉ lệ trending** = số video lên chart trong 72 giờ / số video. Mọi tỉ lệ kèm **khoảng tin cậy 95% Wilson**. Tỉ số sau kiểm soát dùng **Mantel–Haenszel** với khoảng tin cậy **bootstrap theo kênh**. Không làm kiểm định p-value.
- **Chạy lại:** bật container `rstudio`, mở `notebooks/3_EDA.Rmd` ở http://localhost:8787 rồi Knit; hoặc chạy

  ```bash
  MSYS_NO_PATHCONV=1 docker exec -w /home/rstudio/project/notebooks ady201m_rstudio Rscript -e 'rmarkdown::render("3_EDA.Rmd")'
  ```

  (khoảng 1 phút, chủ yếu do bootstrap). Ý nghĩa từng cột: [reports/data_dictionary.md](../../reports/data_dictionary.md).

| ID | Bài toán | Mục trong Rmd |
|---|---|---|
| E1 | Tập sạch có còn đại diện cho cohort không | A |
| E2 | Phân phối từng biến | B |
| E3 | Tỉ lệ trending theo giờ đăng | C1 |
| E4 | Giờ hành chính hay giờ nghỉ | C2, C3 |
| E5 | Tỉ lệ nền thay đổi theo ngày | C4 |
| E6 | Độ vững theo ngưỡng độ phủ | C5 |
| E7 | Kiểm soát nhiễu | D1–D3, D5 |
| E8 | Ảnh hưởng của vài kênh lớn | D4 |
| E9 | Chân dung video trending | E |
| E10 | Nhãn danh mục | F |
| E11 | Kết luận và đề xuất cho Report 4 | I |

---

## E1. Tập sạch có còn đại diện cho cohort không

- **Vấn đề.** Lọc độ phủ chỉ giữ khoảng 1/4 cohort. Nếu bộ lọc giữ lại video theo một kiểu nhất định (ngày, giờ, loại video), kết luận trên tập sạch sẽ không áp dụng cho cohort.
- **Vì sao cần.** Bộ lọc dựa trên lịch chạy của crawler. Crawler tắt theo đợt dài, nên rất có thể bộ lọc giữ lại theo **ngày**.
- **Cách giải.** So tỉ trọng từng nhóm (ngày, thứ, khung giờ, quy mô kênh, thời lượng, danh mục) giữa cohort và 2 tập sạch; vẽ độ phủ trung bình và tỉ lệ qua ngưỡng theo giờ đăng.
- **Kết quả.**
  - Phễu nhãn chính: 156.311 → 154.194 (qua cờ thời lượng, subscriber) → **40.531** (26%). Tỉ lệ trending tăng 0,57% → 0,98% khi lọc độ phủ, đúng như dự kiến (video bị loại mang nhiều nhãn 0 sai).
  - **Không lệch khung giờ:** giờ hành chính chiếm 33,1% cohort, 35,2% `is_clean`. Tỉ lệ qua ngưỡng 27,9% (hành chính) so với 25,5% (nghỉ). Bộ lọc không thiên vị khung giờ nào.
  - **Lệch mạnh theo ngày:** `is_clean` chỉ đến từ khoảng **13 ngày** (25/09–05/10 cộng 10/10, 12/10, 19/10). Hai ngày 12/10 và 19/10 là thứ 2, nên **thứ 2 chiếm 36%** tập sạch (cohort 16%).
  - Shorts chiếm 36% `is_clean` so với 45% cohort. Quy mô kênh lệch không quá 3 điểm %.
- **Hạn chế.** Kết quả của các phần sau phản ánh những ngày cụ thể đó. Phải kiểm soát ngày đăng (E5, E7).

## E2. Phân phối từng biến

- **Vấn đề.** Cần biết hình dạng dữ liệu trước khi so với nhãn: biến nào lệch, nhóm nào quá nhỏ, biến nào vô dụng.
- **Cách giải.** Histogram giờ đăng, heatmap giờ × thứ, thời lượng và subscriber trên thang log, số video theo danh mục, tỉ trọng các loại video.
- **Kết quả.**
  - Video đăng nhiều nhất **17–19h** (26%) và 10–11h. 4 đoạn thời gian (hành chính 35%, cuối tuần 32%, tối ngày thường 24%, đêm/sáng ngày thường 9%) đều đủ lớn.
  - Thời lượng và subscriber **lệch phải mạnh** (trung vị 118 giây, 184.000 subscriber): dùng nhóm hoặc thang log.
  - 3.356 kênh, nhưng **10 kênh chiếm 12,4% video** (chủ yếu kênh tin tức).
  - 3 danh mục lớn nhất chiếm 69% video. **HD 99,5%, phụ đề 0,6%**: gần như hằng số, bỏ khỏi phân tích.

## E3. Tỉ lệ trending theo giờ đăng

- **Vấn đề.** Giờ nào trong ngày có tỉ lệ lọt chart chính cao nhất?
- **Cách giải.** Tỉ lệ và khoảng tin cậy Wilson cho từng giờ 0–23 trên `is_clean`.
- **Kết quả.**
  - **Đỉnh 16–18h:** 17h đạt 2,3% (75 video trending), gấp hơn 2 lần tỉ lệ chung 0,98%. Các giờ 9–15h đều dưới tỉ lệ chung; thấp nhất 13h (0,2%).
  - 4h có 7,1% nhưng chỉ 337 video, 14/24 video trending đến từ 2 kênh âm nhạc: hiệu ứng của kênh, không phải của giờ.
- **Hạn chế.** Mỗi giờ chỉ có vài chục video trending, khoảng tin cậy rộng; 0–3h và 22–23h không kết luận được.

## E4. Giờ hành chính hay giờ nghỉ

- **Vấn đề.** Trả lời trực tiếp câu hỏi nghiên cứu, rồi tách "giờ nghỉ" thành các đoạn để biết chênh lệch đến từ đâu.
- **Cách giải.** Tỉ lệ theo `time_slot` và `slot_detail`, cho cả 2 nhãn.
- **Kết quả.**

  | Chart | Hành chính | Nghỉ | Nghỉ / hành chính |
  |---|---|---|---:|
  | Chính | 0,62% (CI 0,50–0,76) | 1,18% (CI 1,06–1,32) | **1,91** |
  | Danh mục | 2,99% (CI 2,70–3,31) | 3,34% (CI 3,13–3,55) | 1,12 |

  - Chart chính: **tối ngày thường (17–24h) cao nhất 1,33%**, gấp 2,1 lần giờ hành chính dù cùng là thứ 2–6. Cuối tuần thấp nhất trong giờ nghỉ (1,04%), nên chênh lệch **không** đến từ cuối tuần.
  - Chart danh mục: khoảng tin cậy 2 khung giờ chồng nhau.

## E5. Tỉ lệ nền thay đổi theo ngày

- **Vấn đề.** Heatmap thứ × buổi cho thấy thứ 2 thấp ở mọi buổi. Nếu do ngày đăng chứ không do giờ đăng, so sánh ở E4 bị lệch.
- **Cách giải.** Tỉ lệ theo đợt ngày; so giờ hành chính với tối ngày thường **trong cùng nhóm ngày**.
- **Kết quả.**
  - Tỉ lệ nền **giảm từ 1,32% (đợt 1: 25/09–05/10) xuống 0,44% (đợt 2: 10, 12, 19/10)**. Giải thích hợp lý nhất: chart chính chỉ có khoảng 200 chỗ, còn số video mới mỗi ngày tăng từ khoảng 2.500 lên 7.000–8.500 sau khi `discover` mở rộng tập kênh.
  - 12/10 và 19/10 (thứ 2, đợt 2) chiếm **57% video giờ hành chính** trong tập sạch, nên kéo tỉ lệ giờ hành chính xuống.
  - Trong cùng nhóm ngày, chênh lệch vẫn còn: thứ 2 là 0,31% so với 0,64% (gấp 2,1); thứ 3–6 là 1,03% so với 1,86% (gấp 1,8).

## E6. Độ vững theo ngưỡng độ phủ

- **Vấn đề.** Ngưỡng 0,6 là lựa chọn kinh nghiệm. Kết luận có phụ thuộc vào nó không?
- **Cách giải.** Lặp lại E4 ở ngưỡng 0 / 0,4 / 0,5 / 0,6 / 0,7, giữ các cờ khác.
- **Kết quả.** Giờ nghỉ gấp **1,9–2,25 lần**, tối ngày thường gấp **2,0–2,15 lần** giờ hành chính ở mọi ngưỡng. Ngưỡng đổi **mức** tỉ lệ, không đổi **chênh lệch**.

## E7. Kiểm soát nhiễu

- **Vấn đề.** Chênh lệch có thể đến từ yếu tố đi kèm giờ đăng: ngày đăng, quy mô kênh, danh mục, thời lượng.
- **Vì sao cần.** Nếu giờ hành chính có nhiều loại video "khó trending" hơn, thì "giờ nghỉ tốt" chỉ là "loại video đăng giờ nghỉ tốt".
- **Cách giải.**
  - So thành phần video giữa 2 khung giờ; so tỉ lệ trong từng nhóm.
  - Gộp các so sánh trong từng nhóm bằng tỉ số **Mantel–Haenszel**, kiểm soát tăng dần từng yếu tố.
  - Khoảng tin cậy **bootstrap theo kênh** (300 lần), vì video cùng kênh không độc lập.
  - Lặp lại trên nhóm video "có khả năng trending" (bỏ Shorts, Tin tức, Thể thao).
- **Kết quả.**
  - Giờ hành chính có **nhiều Tin tức hơn** (27% so với 22%), **ít video dài hơn** (25% so với 32% trên 10 phút), **nhiều video đợt 2 hơn** (48% so với 33%): đều bất lợi cho giờ hành chính.
  - **Phát hiện lớn:** trong toàn bộ cohort, 1.029 video trending chính có 2 Shorts, 0 Tin tức, 1 Thể thao. Chart chính VN gần như không chứa các loại này.

  | Kiểm soát | Toàn bộ `is_clean` | Bỏ Shorts, Tin tức, Thể thao |
  |---|---|---|
  | Không | 1,91 (1,38–2,49) | 1,65 (1,23–2,17) |
  | + ngày đăng | 1,84 | 1,54 |
  | + quy mô kênh | 1,79 | 1,50 |
  | + danh mục | **1,47 (1,04–2,02)** | **1,43 (1,04–1,96)** |
  | + thời lượng | 1,26 (0,95–1,71) | 1,25 (0,91–1,70) |

  - Danh mục và thời lượng giải thích khoảng **một nửa** chênh lệch. Phần còn lại khoảng 1,25–1,5 lần.
- **Hạn chế.**
  - Kiểm soát ngày đăng chỉ giữ ngày có cả 2 khung giờ (thứ 2–6, 27.273 video), nên so sánh thực chất là giờ hành chính với tối và đêm/sáng ngày thường.
  - Kiểm soát đủ 4 yếu tố tạo 618 tầng, nhiều tầng rất nhỏ; khoảng tin cậy rộng.

## E8. Ảnh hưởng của vài kênh lớn

- **Vấn đề.** Nếu vài kênh hay trending lại đăng dồn vào giờ nghỉ, chúng tạo ra "hiệu ứng khung giờ" giả.
- **Cách giải.** Xem kênh có nhiều video trending nhất; tính lại tỉ số (kiểm soát ngày, quy mô kênh) khi bỏ 5, 10, 20 kênh đầu.
- **Kết quả.** 398 video trending đến từ 221 kênh; 10 kênh đầu chỉ chiếm 14,8%, mỗi kênh tối đa 8 video. Bỏ các kênh đầu, tỉ số tăng nhẹ 1,79 → 1,91. **Không do vài kênh tạo ra.**

## E9. Chân dung video trending

- **Vấn đề.** Video đã lên trending trông như thế nào; giờ đăng có ảnh hưởng tới tốc độ, thứ hạng không.
- **Cách giải.** Trên 398 video trending của `is_clean`: phân phối số giờ tới chart, hạng cao nhất, giờ lần đầu thấy trên chart, so đặc điểm với video không trending.
- **Kết quả.**
  - Video đăng giờ hành chính lên chart nhanh hơn một chút (trung vị 21,4 giờ so với 24,9 giờ); hạng cao nhất gần như giống nhau (110 so với 101,5). Giờ đăng ảnh hưởng tới **có lọt hay không**, ít ảnh hưởng tới tốc độ, thứ hạng.
  - Video trending: thời lượng trung vị **22,4 phút** (video thường 1,9 phút), 82% dài trên 10 phút, 0,5% Shorts, 0% Tin tức / Thể thao, **74% là Trò chơi hoặc Âm nhạc** (video thường 12%), kênh lớn hơn (360.000 so với 184.000 subscriber).
- **Hạn chế.** Giờ lần đầu thấy trên chart dồn vào 4h, 14h, 18h, nhưng không tách được nhịp cập nhật của YouTube khỏi việc crawler bắt bù sau khi tắt. Không dùng để chọn giờ đăng.

## E10. Nhãn danh mục

- **Vấn đề.** Kết luận của chart chính có đúng với chart theo từng danh mục không?
- **Cách giải.** Lặp lại E7 cho `is_trending_category` trên `is_clean_category`.
- **Kết quả.**
  - Chart danh mục chọn video **ngược với chart chính**: Shorts có tỉ lệ cao nhất (3,85%), Tin tức vẫn lọt được (1,3%).
  - Tỉ số nghỉ / hành chính: 1,12 (thô) → 1,02 (kiểm soát ngày) → **0,97 (CI 0,85–1,11)** khi kiểm soát đủ. **Giờ đăng không tạo khác biệt** với chart danh mục.

## E11. Kết luận và đề xuất cho Report 4

- **Trả lời câu hỏi.**
  1. **Chart chính:** giờ nghỉ, rõ nhất **chiều tối 16–18h ngày thường**, có **lợi thế vừa phải**. Thô gần 2 lần; sau kiểm soát ngày đăng, quy mô kênh, danh mục còn khoảng **1,5 lần** (khoảng tin cậy trên 1); kiểm soát thêm thời lượng còn khoảng **1,25 lần**, không còn chắc chắn.
  2. **Chart danh mục:** không có khác biệt.
  3. **Loại video quan trọng hơn giờ đăng nhiều:** chart chính gần như chỉ chứa video dài, không Shorts, không tin tức.
- **Giới hạn.** Crawler chỉ có mặt khoảng 59% số giờ; tập sạch đến từ khoảng 13 ngày, nặng về thứ 2; tỉ lệ nền giảm theo thời gian; chỉ theo dõi các kênh trong danh sách; `channel_subscribers` lấy tại lần chụp mới nhất; dữ liệu quan sát nên **không kết luận nhân quả**.
- **Đề xuất cho Report 4 (Logistic Regression, XGBoost).**
  - Nhãn `is_trending_main` trên `is_clean`; khoảng 1% nhãn 1, nên dùng `class_weight` và đánh giá bằng **PR-AUC**, recall, F1.
  - Feature: khung giờ (`time_slot`, `slot_detail`, giờ, cuối tuần); loại video (thời lượng, danh mục, Shorts, livestream); quy mô kênh (`log10_subs`); **đợt / ngày đăng** (vì tỉ lệ nền thay đổi). Bỏ `definition`, `caption`.
  - Chia train / test **theo kênh** (GroupKFold) để video cùng kênh không nằm ở cả hai tập.
  - So độ quan trọng của khung giờ khi có và không có feature loại video, để kiểm tra lại kết luận bằng mô hình.
