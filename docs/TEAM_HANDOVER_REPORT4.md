# Bàn giao cho thành viên nhóm — Report 4 (Modeling & Validation)

Phân công Report 4 cho 3 người: ai làm gì, dùng dữ liệu nào, quy ước chung, sản phẩm phải nộp. Đọc kèm [`docs/analysis/03_eda.md`](analysis/03_eda.md) (kết quả EDA, mục E11 đề xuất cho Report 4) và [`reports/data_dictionary.md`](../reports/data_dictionary.md).

## 1. Yêu cầu của môn

Report 4 = On-going 3 (10%) + Progress Test 2 (10%) = **20%**. Nội dung:
- Xây dựng **2 mô hình ML khác nhau để kiểm định giả thuyết**. Nhóm làm 3 mô hình: Logistic Regression, Random Forest, XGBoost.
- **Đánh giá độ chính xác (Model Evaluation) và so sánh hiệu quả.**

Cấu trúc repo bắt buộc: `src/modeling/model.py`, `notebooks/2_Modeling.ipynb`, `reports/Report_4_*.pdf`. Mỗi người tự commit phần của mình, message theo conventional commit (`feat(modeling): ...`), nhóm đủ ≥ 2 commit/tuần.

## 2. Giả thuyết và quy tắc kết luận (đã chốt, không đổi sau khi xem kết quả)

- **H₀:** khả năng lọt trending của video đăng trong giờ hành chính **bằng** video đăng trong giờ nghỉ, khi đã kiểm soát ngày đăng, quy mô kênh, thể loại và thời lượng.
- **H₁:** hai khả năng này **khác nhau**.

**Quy tắc quyết định:**
1. **Chính (Logistic Regression):** odds ratio (OR) giờ nghỉ / giờ hành chính trong mô hình đủ kiểm soát (bộ feature C, mục 4).
   - CI 95% bootstrap theo kênh **không chứa 1** → **bác bỏ H₀**.
   - CI **chứa 1** → **chưa đủ bằng chứng bác bỏ H₀**.
2. **Độ vững (Random Forest, XGBoost):** so PR-AUC của bộ C và bộ C bỏ các biến thời gian.
   - Hai mô hình cây cùng chiều với LR → kết luận **vững**.
   - Ngược chiều → ghi kết luận là **yếu**.
   - Mô hình cây không đổi kết luận của LR.

Lý do LR là mô hình chính: chỉ LR cho ra một con số có chiều và độ lớn (OR) kèm khoảng tin cậy, ứng đúng với H₀. Mô hình cây dự đoán tốt hơn, nhưng chỉ cho biết biến "quan trọng bao nhiêu".

## 3. Dữ liệu chung

- **File:** `data/processed/video_features_full_2026-11-01.csv`. Đây là bản đóng băng, không commit. Ai chưa có thì xin file từ BanNH, hoặc xuất theo `docs/HOW_TO_SETUP.md` mục 5.4.
- **Tập dùng:** `is_clean = TRUE`, gồm **40.531 video, 398 trending (0,98%)**, 3.356 kênh, 221 kênh có video trending.
- **Nhãn:** `is_trending_main`.
- **Shorts** = `is_short` = video ≤ 3 phút (giới hạn của YouTube từ 15/10/2024). Đây là ước lượng theo thời lượng.

**Cài thư viện (đã thêm vào repo):** `scikit-learn` là thư viện chung; `xgboost` nằm trong nhóm riêng `xgboost` của `pyproject.toml`, chỉ ai làm XGBoost mới cần cài. `requirements.txt` (image Docker `app`) có đủ cả hai.

| Người | Lệnh sau khi `git pull` |
|---|---|
| BanNH, phat | `uv sync` |
| duc | `uv sync --group xgboost` |

## 4. Feature (đã chốt)

| Bộ | Feature | Ghi chú |
|---|---|---|
| **A — thời gian** | `time_slot`; cho mô hình cây thêm `slot_detail`, `publish_hour_vn`, `publish_dow_vn`, `is_weekend` | LR dùng `time_slot` để có 1 OR. Biến nào xác định "giờ nghỉ" đều thuộc nhóm này |
| **B — kiểm soát** | Ngày đăng (`release_at_vn` lấy phần ngày, dạng nhóm), `log10_subs`, `category_title` (giữ 6 danh mục nhiều video nhất như EDA D3, còn lại gộp "Khác"), `duration_group` hoặc `log10(duration_s)`, `is_short`, `is_live_or_premiere`, `title_length`, `n_tags` | Theo kết quả EDA D3 |
| **C** | A + B | Bộ chính để kết luận |

**Cấm đưa vào mô hình** (lộ nhãn hoặc là cột làm sạch): `is_trending_main`, `hours_to_trending_*`, `best_rank_*`, `is_trending_category`, `coverage_*`, `flag_*`, `is_clean*`, `video_id`, `channel_id`.

**Không dùng:**
- `definition`, `caption`: gần như hằng số.
- `channel_view_count`, `channel_video_count`: lấy ở lần chụp kênh mới nhất, sau khi video có thể đã trending.
- `default_audio_language`, `channel_country`: thiếu 26% và 8%.

## 5. Quy ước validation (mọi mô hình dùng chung)

1. **Tập test giữ riêng:** dùng `StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)` theo `channel_id`, lấy fold đầu làm test (khoảng 20% số kênh). Danh sách kênh test lưu ở `data/processed/test_channels.csv` (commit). **Chỉ chấm trên tập test một lần, khi cả 3 mô hình đã chốt.**
2. **Tinh chỉnh tham số:** trên 80% còn lại, `StratifiedGroupKFold` 5 fold theo kênh, chọn tham số theo **PR-AUC trung bình**.
3. **Mất cân bằng nhãn:**
   - LR và RF dùng `class_weight="balanced"`.
   - XGBoost dùng `scale_pos_weight = số nhãn 0 / số nhãn 1`, tính trong từng fold, khoảng 101.
   - Không dùng SMOTE.
4. **Ngưỡng phân loại:** chọn trong CV, lấy ngưỡng cho F1 cao nhất. Không chọn trên tập test.
5. **Chỉ số báo cáo:** accuracy, precision, recall, F1, PR-AUC, ROC-AUC, precision ở top 1% và top 5%, confusion matrix.
   - **Chọn mô hình bằng PR-AUC.**
   - Accuracy luôn đặt cạnh mô hình mốc, vì mô hình luôn đoán "không trending" đã đạt **99,02%**.
6. **Mô hình mốc:** `DummyClassifier(strategy="most_frequent")` và `DummyClassifier(strategy="stratified")`.
7. `random_state=42` ở mọi chỗ có ngẫu nhiên.

## 6. Phân công

| Người | Phần việc | Sản phẩm |
|---|---|---|
| **BanNH** | Quy tắc H₀ và feature (mục 2, 4: đã chốt). **Logistic Regression**: OR khung giờ với bộ A, B, C; CI bootstrap theo kênh; kiểm tra độ vững (nhóm "có khả năng trending" bỏ Shorts, Tin tức, Thể thao; nhãn chart danh mục trên `is_clean_category`). **Kết luận H₀**, ghép báo cáo và notebook | Phần LR và kết luận trong `2_Modeling.ipynb`; `docs/analysis/04_modeling.md`; `reports/Report_4_*.pdf` |
| **phat** | **Làm trước, các bạn khác phụ thuộc** (thư viện đã thêm sẵn, xem mục 3): viết `src/modeling/model.py`: đọc CSV, lọc `is_clean`, dựng bộ A/B/C, chặn cột cấm, tách tập test theo mục 5 và ghi `test_channels.csv`, hàm chia fold, hàm tính đủ chỉ số mục 5, mô hình mốc. Sau đó: **Random Forest** (tinh chỉnh, so C và C bỏ thời gian, mức quan trọng của biến) | `model.py`, `test_channels.csv`; phần RF trong notebook; mục "Dữ liệu và phương pháp" của báo cáo |
| **duc** | **XGBoost** (tinh chỉnh, so C và C bỏ thời gian, permutation importance). **Bảng so sánh 5 dòng** (2 mốc, LR, RF, XGB) trên tập test. Kiểm tra phụ: train đợt 1 (25/09–05/10), test đợt 2 (10, 12, 19/10) | Phần XGB và so sánh trong notebook; mục "Đánh giá và so sánh" của báo cáo |

## 7. Thứ tự và mốc

| # | Việc | Người | Cần có trước |
|---|---|---|---|
| 1 | Quy tắc H₀, feature, quy ước validation | BanNH | Xong (file này) |
| 2 | `model.py`, `test_channels.csv` (thư viện đã có) | phat | 1 |
| 3 | LR, RF, XGBoost chạy song song, cùng fold và cùng feature | 3 người | 2 |
| 4 | Bảng so sánh trên tập test | duc | 3 |
| 5 | Kết luận H₀, ghép notebook, `04_modeling.md`, báo cáo PDF | BanNH | 4 |

Hạn từng mốc: ____ (nhóm điền).

## 8. Nộp phần của mình

Mỗi người gửi BanNH:
- Đoạn notebook đã chạy được.
- Bảng số liệu (chỉ số trên CV và trên tập test).
- 3–5 câu nhận xét: mô hình cho thấy gì, giới hạn gì.

Không sửa phần của người khác trong `model.py`; cần thêm hàm thì thêm hàm mới.

## 9. Câu hỏi dễ bị hỏi

| Câu hỏi | Trả lời ngắn | Ai trả lời |
|---|---|---|
| Accuracy 99% có tốt không? | Không. Mô hình luôn đoán "không trending" đã đạt 99,02%; xem recall, F1, PR-AUC | duc |
| Vì sao chia train/test theo kênh? | Video cùng kênh giống nhau; chia ngẫu nhiên thì mô hình "nhớ kênh", điểm bị thổi lên | phat |
| Vì sao 3 mô hình mà chỉ LR quyết định H₀? | LR cho OR có chiều, độ lớn, khoảng tin cậy; mô hình cây kiểm tra độ vững | BanNH |
| Mô hình chứng minh giờ đăng gây ra trending không? | Không, dữ liệu quan sát; chỉ nói "đi kèm" khi đã kiểm soát các yếu tố khác | BanNH |
