# Bàn giao cho thành viên nhóm — Report 4 (Modeling & Validation)

Phân công Report 4 cho 3 người: ai làm gì, dùng dữ liệu nào, quy ước chung, sản phẩm phải nộp. Đọc kèm [`docs/analysis/03_eda.md`](analysis/03_eda.md) (kết quả EDA, mục E11 đề xuất cho Report 4) và [`reports/data_dictionary.md`](../reports/data_dictionary.md).

## 1. Yêu cầu của môn

Report 4 = On-going 3 (10%) + Progress Test 2 (10%) = **20%**. Nội dung:
- Xây dựng **2 mô hình ML khác nhau để kiểm định giả thuyết**. Nhóm làm 2 mô hình: **Logistic Regression** và **XGBoost**.
- **Đánh giá độ chính xác (Model Evaluation) và so sánh hiệu quả.**

Cấu trúc repo bắt buộc: `src/modeling/model.py`, `notebooks/2_Modeling.ipynb`, `reports/Report_4_*.pdf`. Mỗi người tự commit phần của mình, message theo conventional commit (`feat(modeling): ...`), nhóm đủ ≥ 2 commit/tuần.

## 2. Giả thuyết và quy tắc kết luận (đã chốt, không đổi sau khi xem kết quả)

- **H₀:** khả năng lọt trending của video đăng trong giờ hành chính **bằng** video đăng trong giờ nghỉ, khi đã kiểm soát ngày đăng, quy mô kênh, thể loại và thời lượng.
- **H₁:** hai khả năng này **khác nhau**.

**Quy tắc quyết định:**
1. **Chính (Logistic Regression):** odds ratio (OR) giờ nghỉ / giờ hành chính trong mô hình đủ kiểm soát (bộ feature C, mục 4).
   - CI 95% bootstrap theo kênh **không chứa 1** → **bác bỏ H₀**.
   - CI **chứa 1** → **chưa đủ bằng chứng bác bỏ H₀**.
2. **Độ vững (XGBoost):** so PR-AUC của bộ C và bộ C bỏ các biến thời gian.
   - XGBoost cùng chiều với LR → kết luận **vững**.
   - Ngược chiều → ghi kết luận là **yếu**.
   - XGBoost không đổi kết luận của LR.

Lý do LR là mô hình chính: chỉ LR cho ra một con số có chiều và độ lớn (OR) kèm khoảng tin cậy, ứng đúng với H₀. XGBoost thường dự đoán tốt hơn, nhưng chỉ cho biết biến "quan trọng bao nhiêu".

## 3. Dữ liệu chung

- **File:** `data/processed/video_features_full_2026-11-01.csv`. Đây là bản đóng băng, không commit. Ai chưa có thì xin file từ BanNH, hoặc xuất theo `docs/HOW_TO_SETUP.md` mục 5.4.
- **Tập mô hình chính:** `is_clean = TRUE` **bỏ Shorts (`is_short`), Tin tức và Chính trị, Thể thao** = video "có khả năng trending" (EDA D5). Lý do: ba nhóm này gần như không bao giờ lên chart chính (Shorts 5/23.093, Tin tức 0/9.632, Thể thao 0/3.021) nên chỉ làm loãng phép so sánh khung giờ. Còn **10.231 video, 393 trending (3,8%)**. Hàm: `loc_co_kha_nang()` trong `src/modeling/split.py`.
- **Tập đầy đủ** `is_clean` (40.531 video, 398 trending, 0,98%) chỉ dùng cho kiểm tra độ vững của LR, với `is_short` và thời lượng làm biến kiểm soát.
- **Nhãn:** `is_trending_main`.
- **Shorts** = `is_short` = video ≤ 3 phút (giới hạn của YouTube từ 15/10/2024). Đây là ước lượng theo thời lượng.

**Cài thư viện (đã thêm vào repo):** `scikit-learn` là thư viện chung; `xgboost` nằm trong nhóm riêng `xgboost` của `pyproject.toml`, chỉ ai làm XGBoost mới cần cài. `requirements.txt` (image Docker `app`) có đủ cả hai.

| Người | Lệnh sau khi `git pull` |
|---|---|
| BanNH | `uv sync` |
| phat, duc | `uv sync --group xgboost` |

**Code dùng chung đã có (14/11, BanNH), không viết lại:**

| File | Dùng gì |
|---|---|
| `src/modeling/split.py` | `doc_tap_sach()`, `tach_train_test()`, `loc_co_kha_nang()`: đọc CSV, tách theo kênh test đã cố định, lọc tập chính |
| `src/modeling/features.py` | `them_bien()` (thêm `ngay`, `cat_gop`, `log10_duration`), `BO_A_XGB`, `BO_B_XGB`, `COT_CAM`, `kiem_tra_cot_cam()` |
| `src/modeling/logistic.py` | `chia_fold()` (cùng fold với LR), `chon_nguong()`, `chi_so()` (đủ chỉ số mục 5), `mo_hinh_moc()` |
| `data/processed/lr_test_predictions.csv` | Dự đoán LR trên tập test: `video_id`, `channel_id`, `y`, `p_lr_c`, `p_lr_b`, `du_doan_lr_c`, `nguong_lr_c` |
| `notebooks/2_Modeling.ipynb` | Phần 1 (LR) đã chạy; Phần 2, 3 để trống cho phat, duc |

## 4. Feature (đã chốt)

| Bộ | Feature | Ghi chú |
|---|---|---|
| **A — thời gian** | `time_slot`; cho XGBoost thêm `slot_detail`, `publish_hour_vn`, `publish_dow_vn`, `is_weekend` | LR dùng `time_slot` để có 1 OR. Biến nào xác định "giờ nghỉ" đều thuộc nhóm này |
| **B — kiểm soát** | Ngày đăng (`release_at_vn` lấy phần ngày, biến phân loại 15 giá trị), `log10_subs`, `category_title` (Mọi người và Blog, Giải trí, Âm nhạc, Trò chơi, còn lại gộp "Khác"; Tin tức, Thể thao đã bỏ), thời lượng (LR: `duration_group`; XGBoost: `log10(duration_s)`), `is_live_or_premiere`, `title_length`, `n_tags` | Theo EDA D3. `is_short` không còn là feature vì tập chính đã bỏ Shorts |
| **C** | A + B | Bộ chính để kết luận |

**Cấm đưa vào mô hình** (lộ nhãn hoặc là cột làm sạch): `is_trending_main`, `hours_to_trending_*`, `best_rank_*`, `is_trending_category`, `coverage_*`, `flag_*`, `is_clean*`, `video_id`, `channel_id`.

**Không dùng:**
- `definition`, `caption`: gần như hằng số.
- `channel_view_count`, `channel_video_count`: lấy ở lần chụp kênh mới nhất, sau khi video có thể đã trending.
- `default_audio_language`, `channel_country`: thiếu 26% và 8%.

## 5. Quy ước validation (mọi mô hình dùng chung)

1. **Tập test giữ riêng (đã tách, BanNH):** `StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)` theo `channel_id`, fold đầu làm test. Code: `src/modeling/split.py`; danh sách kênh test: `data/processed/test_channels.csv` (đã commit, **không tạo lại**). Trong notebook dùng `doc_tap_sach()` và `tach_train_test()` của file này.
   - Kênh test chọn trên toàn bộ `is_clean`, rồi mới lọc `loc_co_kha_nang()`, nên tập chính và tập đầy đủ dùng cùng kênh.
   - Tập chính: train 8.152 video, 1.100 kênh, 315 trending (3,86%); test 2.079 video, 291 kênh, 78 trending (3,75%).
   - Tập đầy đủ: train 32.423 video, 318 trending; test 8.108 video, 80 trending.
   - **Mỗi mô hình chấm tập test đúng một lần**, sau khi đã chốt tham số và ngưỡng bằng CV trên train. LR đã chấm 14/11 (notebook mục 1.6); XGBoost chấm khi phat chốt xong.
2. **Tinh chỉnh tham số:** trên 80% còn lại, `StratifiedGroupKFold` 5 fold theo kênh, chọn tham số theo **PR-AUC trung bình**.
3. **Mất cân bằng nhãn:**
   - LR dùng `class_weight="balanced"`.
   - XGBoost dùng `scale_pos_weight = số nhãn 0 / số nhãn 1`, tính trong từng fold, khoảng 25 trên tập chính.
   - Không dùng SMOTE.
4. **Ngưỡng phân loại:** chọn trong CV, lấy ngưỡng cho F1 cao nhất. Không chọn trên tập test.
5. **Chỉ số báo cáo:** accuracy, precision, recall, F1, PR-AUC, ROC-AUC, precision ở top 1% và top 5%, confusion matrix.
   - **Chọn mô hình bằng PR-AUC.**
   - Accuracy luôn đặt cạnh mô hình mốc, vì mô hình luôn đoán "không trending" đã đạt **96,2%** trên tập chính (99,02% trên tập đầy đủ).
6. **Mô hình mốc:** `DummyClassifier(strategy="most_frequent")` và `DummyClassifier(strategy="stratified")`.
7. `random_state=42` ở mọi chỗ có ngẫu nhiên.

## 6. Phân công

| Người | Phần việc | Sản phẩm |
|---|---|---|
| **BanNH** | **Xong 14/11:** quy tắc H₀, feature, tách train/test, code dùng chung; **Logistic Regression**: OR khung giờ bộ A 1,36 (1,00–1,88), bộ C **1,19 (0,81–1,72)**, 5 kiểm tra độ vững đều chứa 1, ΔPR-AUC khi bỏ khung giờ ≈ 0 → **chưa đủ bằng chứng bác bỏ H₀** (`docs/analysis/04_modeling.md` M1–M6). **Còn lại:** kết luận chung sau khi có XGBoost, ghép notebook và báo cáo | Phần 1 của `2_Modeling.ipynb`; `04_modeling.md`; `reports/Report_4_*.pdf` |
| **phat** | **XGBoost — huấn luyện**, viết trong `src/modeling/model.py` và Phần 2 của notebook. Dữ liệu: `train`, `test` của notebook (tập chính); feature `BO_A_XGB + BO_B_XGB` (cột phân loại `time_slot`, `slot_detail`, `ngay`, `cat_gop` → one-hot hoặc `enable_categorical`); fold: `lg.chia_fold(train)` để cùng fold với LR. Tinh chỉnh trong CV theo PR-AUC: `max_depth` (2–4), `learning_rate`, `n_estimators`, `min_child_weight`, `subsample`; `scale_pos_weight` ≈ 25 tính trong fold; ngưỡng theo F1 trên OOF (`lg.chon_nguong`). Chấm test **một lần** bằng `lg.chi_so()`; ghi `data/processed/xgb_test_predictions.csv` cùng cột như file của LR. Giao duc bộ tham số đã chốt | `model.py`; phần huấn luyện XGB trong notebook; mục "Dữ liệu và phương pháp" của báo cáo |
| **duc** | **XGBoost — giải thích và đánh giá** (dùng tham số phat đã chốt): so bộ C và bộ C bỏ `BO_A_XGB` trên cùng fold (ΔPR-AUC từng fold, trung bình, khoảng dao động; LR cho −0,002, từ −0,013 tới +0,005), permutation importance trên OOF. **Bảng so sánh 4 dòng** (2 mốc, LR bộ C, XGB) trên tập test từ `lr_test_predictions.csv` và `xgb_test_predictions.csv`, kèm confusion matrix (các dòng mốc và LR đã có ở notebook mục 1.6). Kiểm tra phụ: train đợt 1 (25/09–05/10), test đợt 2 (10, 12, 19/10) | Phần 3 của notebook; mục "Đánh giá và so sánh" của báo cáo |

## 7. Thứ tự và mốc

| # | Việc | Người | Cần có trước |
|---|---|---|---|
| 1 | Quy tắc H₀, feature, quy ước validation, tách train/test, code dùng chung | BanNH | Xong 12–14/11 |
| 2 | Logistic Regression, kết luận phần LR (`04_modeling.md` M1–M6) | BanNH | Xong 14/11 |
| 3 | XGBoost: `model.py`, tinh chỉnh tham số, ngưỡng, chấm test, `xgb_test_predictions.csv` | phat | Bắt đầu được ngay |
| 4 | XGBoost: so có / bỏ thời gian, permutation importance; bảng so sánh; kiểm tra đợt | duc | 3 |
| 5 | Kết luận chung (M9), ghép notebook, báo cáo PDF | BanNH | 4 |

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
| Accuracy 96% có tốt không? | Không. Mô hình luôn đoán "không trending" đã đạt 96,2%; xem recall, F1, PR-AUC | duc |
| Vì sao bỏ Shorts, Tin tức, Thể thao? | Gần như không bao giờ lên chart chính (5/23.093, 0/9.632, 0/3.021); giữ lại chỉ làm loãng so sánh khung giờ. Kết luận trên tập đầy đủ giống nhau (EDA D3 1,24 so với D5 1,28) | BanNH |
| Vì sao chia train/test theo kênh? | Video cùng kênh giống nhau; chia ngẫu nhiên thì mô hình "nhớ kênh", điểm bị thổi lên | phat |
| Vì sao 2 mô hình mà chỉ LR quyết định H₀? | LR cho OR có chiều, độ lớn, khoảng tin cậy; XGBoost kiểm tra độ vững | BanNH |
| Kết quả LR nói gì? | OR 1,19 (CI 0,81–1,72) sau kiểm soát: chưa đủ bằng chứng bác bỏ H₀; CI rộng nên không loại trừ được lợi thế tới 1,7 lần | BanNH |
| Mô hình chứng minh giờ đăng gây ra trending không? | Không, dữ liệu quan sát; chỉ nói "đi kèm" khi đã kiểm soát các yếu tố khác | BanNH |
