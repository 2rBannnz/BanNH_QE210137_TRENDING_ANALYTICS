# Phần 4 — Mô hình: kiểm định giả thuyết "thời điểm vàng"

[← Phần 3 — EDA](03_eda.md) · [Tổng quan](README.md)

**Mục tiêu của phần:** dùng mô hình phân loại để trả lời H₀ đã nêu ở Report 1, bằng một quy tắc chốt trước khi chạy; rồi đo xem mô hình dự đoán video trending tốt tới đâu và khung giờ đóng góp bao nhiêu vào dự đoán đó.

- **H₀:** khả năng lọt trending của video đăng trong giờ hành chính **bằng** video đăng trong giờ nghỉ, khi đã kiểm soát ngày đăng, quy mô kênh, thể loại và thời lượng.
- **H₁:** hai khả năng này **khác nhau**.

Tài liệu này ghi phần đã làm (Logistic Regression, BanNH). Phần XGBoost (phat, duc) và kết luận chung sẽ ghi tiếp vào M7–M9 khi có kết quả. Phân công và quy ước: [`docs/TEAM_HANDOVER_REPORT4.md`](../TEAM_HANDOVER_REPORT4.md).

## Dữ liệu và cách làm

```
video_features_full_2026-11-01.csv ─► split.py (tập sạch, tách test theo kênh, lọc video có khả năng trending)
                                   ─► features.py (bộ feature A / B / C, cột cấm)
                                   ─► logistic.py (OR + bootstrap theo kênh; LR dự đoán)  ─► notebooks/2_Modeling.ipynb
```

- **Chạy lại:** `uv run jupyter nbconvert --to notebook --execute --inplace notebooks/2_Modeling.ipynb` (khoảng 5 phút, chủ yếu do bootstrap). Cần bản CSV đóng băng (không commit).
- Mọi chỗ ngẫu nhiên dùng `random_state=42`.

| ID | Bài toán | Mục trong notebook |
|---|---|---|
| M1 | Tập mô hình và tách train / test theo kênh | 1.1 |
| M2 | Feature và cột cấm | 1.2 |
| M3 | Odds ratio của khung giờ, thô và sau kiểm soát | 1.3, 1.4 |
| M4 | Độ vững của odds ratio | 1.5 |
| M5 | LR dự đoán: chọn tham số, ngưỡng, chấm tập test | 1.6 |
| M6 | Kết luận phần Logistic Regression | 1.7 |
| M7 | XGBoost: huấn luyện và tinh chỉnh (phat) | Phần 2 |
| M8 | XGBoost: khung giờ đóng góp bao nhiêu; so sánh mô hình (duc) | Phần 2, 3 |
| M9 | Kết luận chung | Phần 4 |

---

## M1. Tập mô hình và tách train / test theo kênh

- **Vấn đề.** Chọn video nào để mô hình hoá, và chia train / test thế nào để điểm đánh giá không bị thổi phồng.
- **Vì sao cần.** EDA D2 cho thấy ba nhóm video gần như **không bao giờ** lên chart chính: Shorts (≤ 3 phút) 5/23.093, Tin tức và Chính trị 0/9.632, Thể thao 0/3.021. Giữ chúng trong mô hình chỉ làm loãng phép so sánh khung giờ (giờ hành chính có nhiều Shorts và tin tức hơn). Video cùng kênh rất giống nhau; chia ngẫu nhiên theo video thì mô hình "nhớ kênh" và điểm test cao giả.
- **Cách giải.**
  - **Tập chính** = `is_clean` bỏ Shorts, Tin tức, Thể thao (nhóm "có khả năng trending" của EDA D5). Tập đầy đủ `is_clean` chỉ dùng để kiểm tra độ vững.
  - **Tách theo kênh:** `StratifiedGroupKFold(5, shuffle, random_state=42)` theo `channel_id` trên toàn bộ `is_clean`, fold đầu làm test. Kênh test cố định trong `data/processed/test_channels.csv`, chọn **trước** khi lọc, nên tập chính và tập đầy đủ dùng cùng kênh test.
  - Tập test chỉ chấm **một lần**, khi mô hình đã chốt tham số và ngưỡng bằng cross-validation trên train.
- **Cài đặt.** `src/modeling/split.py`: `doc_tap_sach()`, `tach_train_test()`, `loc_co_kha_nang()`, `tom_tat()`.
- **Kết quả.**

  | Tập | Train | Test |
  |---|---|---|
  | Đầy đủ `is_clean` | 32.423 video, 2.681 kênh, 318 trending (0,98%) | 8.108 video, 675 kênh, 80 trending (0,99%) |
  | **Chính** (có khả năng trending) | **8.152 video, 1.100 kênh, 315 trending (3,86%)** | **2.079 video, 291 kênh, 78 trending (3,75%)** |

  Lọc bỏ 75% video nhưng chỉ mất 5/398 video trending. Tỉ trọng giờ hành chính 29% ở cả train và test.
- **Hạn chế.** Tập test chỉ có 78 video trending, nên mọi chỉ số trên test có sai số lớn. Kết luận về H₀ không dựa vào tập test mà dựa vào khoảng tin cậy bootstrap trên train (M3).

## M2. Feature và cột cấm

- **Vấn đề.** Dùng cột nào, và chặn những cột nào "biết trước kết quả".
- **Cách giải.** Ba bộ feature, chốt trong handover mục 4 trước khi chạy:

  | Bộ | Cột | Ghi chú |
  |---|---|---|
  | **A** — thời gian | `time_slot` | Một biến nhị phân để có đúng một odds ratio. XGBoost dùng thêm `slot_detail`, `publish_hour_vn`, `publish_dow_vn`, `is_weekend` |
  | **B** — kiểm soát | `ngay` (ngày ra mắt, 14 mức trong train), `log10_subs`, `cat_gop` (Mọi người và Blog, Giải trí, Âm nhạc, Trò chơi, Khác), `duration_group` (3–10, 10–20, 20–60, > 60 phút), `is_live_or_premiere`, `title_length`, `n_tags` | Theo EDA D3. `is_short` không còn là feature vì tập chính đã bỏ Shorts |
  | **C** = A + B | 25 cột sau one-hot | Bộ dùng để kết luận H₀ |

  - **Cột cấm** (`COT_CAM`, kiểm tra bằng `kiem_tra_cot_cam()`): nhãn và mọi cột chỉ biết sau khi video đã trending (`hours_to_trending_*`, `best_rank_*`), cột độ phủ, cờ làm sạch, `video_id`, `channel_id`.
  - **Không dùng:** `definition`, `caption` (hằng số); `channel_view_count`, `channel_video_count` (lấy ở lần chụp mới nhất, sau khi video có thể đã trending); `default_audio_language`, `channel_country` (thiếu 26% và 8%).
  - Mức tham chiếu của one-hot là mức đầu theo bảng chữ cái: `hanh_chinh`, ngày 25/09, Giải trí, 10–20 phút. 3 video ra mắt 23:53 ngày 24/09 gộp vào 25/09.
- **Cài đặt.** `src/modeling/features.py` (dùng chung cho LR và XGBoost); `logistic.bo_bien_doi()` one-hot và chuẩn hoá.
- **Hạn chế.** Vì mỗi ngày là một biến giả và giờ hành chính chỉ có ở thứ 2–6, hệ số khung giờ thực chất so **giờ hành chính với giờ nghỉ cùng ngày thường**; video cuối tuần chỉ giúp ước lượng các hệ số kiểm soát. Đây cũng là cách EDA D3 làm (các tầng cuối tuần không có nhóm hành chính để so).

## M3. Odds ratio của khung giờ, thô và sau kiểm soát

- **Vấn đề.** Sau khi so các video giống nhau về ngày đăng, quy mô kênh, thể loại, thời lượng, giờ nghỉ còn lợi thế không, và lớn bao nhiêu.
- **Cách giải.**
  - Logistic Regression **gần như không phạt** (`C = 1e4`), không trọng số lớp, để hệ số là ước lượng hợp lý cực đại, không bị co về 0. Kết quả không đổi khi thử `C` từ 100 tới 10⁶.
  - **CI 95% bootstrap theo kênh:** rút lại các kênh có hoàn lại, kênh được rút *k* lần thì mọi video của nó có trọng số *k*, fit lại LR; 500 lần; percentile 2,5–97,5. Bootstrap theo kênh vì video cùng kênh không độc lập (EDA D3 cũng làm vậy).
  - Thêm từng nhóm biến kiểm soát để thấy yếu tố nào kéo OR xuống.
- **Cài đặt.** `logistic.bootstrap_or()`; notebook mục 1.3–1.4.
- **Kết quả** (train tập chính, 8.152 video, 315 trending):

  | Kiểm soát | OR nghỉ / hành chính (CI 95%) | EDA D5, Mantel–Haenszel, train + test |
  |---|---|---|
  | Không (bộ A) | **1,36 (1,00–1,88)** | 1,43 (1,07–1,90) |
  | + ngày đăng | 1,22 (0,89–1,76) | 1,31 |
  | + quy mô kênh | 1,21 (0,86–1,77) | 1,30 |
  | + danh mục | 1,22 (0,84–1,76) | 1,28 (0,93–1,78) |
  | + thời lượng | 1,19 (0,82–1,74) | 1,19 (0,87–1,67) |
  | + livestream, tiêu đề, tag (**bộ C**) | **1,19 (0,81–1,72)** | — |

  - **Theo quy tắc đã chốt:** CI của bộ C **chứa 1** → **chưa đủ bằng chứng bác bỏ H₀**.
  - Ngay OR thô cũng chỉ **chạm** 1 (cận dưới 1,002). Trên tập này, **ngày đăng** là yếu tố kéo OR xuống nhiều nhất (1,36 → 1,22): hai ngày thứ 2 của đợt 2 có tỉ lệ nền thấp (OR của 12/10 so với 25/09 là 0,34, của 19/10 là 0,43) và chiếm gần nửa video giờ hành chính. Danh mục và thời lượng không kéo thêm nhiều, vì Shorts và Tin tức đã bị lọc từ đầu.
  - Các hệ số kiểm soát đúng như EDA: so với Giải trí, **Trò chơi** OR 9,7 (4,4–30,6), **Âm nhạc** 5,5 (2,4–17,7), Blog 2,1 (0,8–7,2), nhóm Khác 0,06 (1 video trending trên 1.534); video **3–10 phút** 0,41 (0,23–0,69) và **trên 60 phút** 0,48 (0,27–0,74) so với 10–20 phút; mỗi lần số subscriber tăng gấp 10 (1 bậc log), OR tăng khoảng **1,8** (CI 1,5–2,3, tính trên 1 độ lệch chuẩn ≈ 1 bậc log). Livestream, độ dài tiêu đề, số tag không khác biệt.
  - LR và Mantel–Haenszel cho cùng một bức tranh (cột phải), dù một bên là OR trên train, một bên là tỉ số nguy cơ trên cả train lẫn test.
- **Hạn chế.** CI rộng (0,81–1,72): dữ liệu **không loại trừ** được lợi thế tới 1,7 lần, cũng không loại trừ được bất lợi 20%. "Chưa đủ bằng chứng" không có nghĩa là "không có tác dụng"; chỉ 315 video trending nên độ nhạy của phép kiểm thấp.

## M4. Độ vững của odds ratio

- **Vấn đề.** Kết quả M3 có phụ thuộc vào cách chọn tập, nhãn, hay cách gộp giờ nghỉ không.
- **Cách giải.** Lặp lại mô hình bộ C với 4 thay đổi, mỗi thay đổi một thứ; bootstrap theo kênh 300 lần.
- **Kết quả.**

  | Mã | Kiểm tra | Số video / trending | OR (CI 95%) |
  |---|---|---|---|
  | R1 | Tập chính, **train + test** | 10.231 / 393 | 1,30 (0,95–1,77) |
  | R2 | **Toàn bộ `is_clean`** (có Shorts, Tin tức, Thể thao), `duration_group` 6 mức, danh mục 6 nhóm + Khác | 32.423 / 318 | 1,23 (0,84–1,70) |
  | R3 | **Nhãn chart danh mục** trên `is_clean_category`, kênh ngoài tập test | 32.225 / 1.017 | 0,95 (0,79–1,12) |
  | R4a | Ngày thường: **tối 17–24h** so với hành chính | 5.697 / 207 | 1,26 (0,89–1,79) |
  | R4b | Ngày thường: **sáng sớm 0–8h** so với hành chính | 5.697 / 207 | 0,89 (0,44–1,81) |

  - Mọi CI đều chứa 1; kết luận M3 không đổi theo tập, nhãn hay cách chia giờ nghỉ.
  - R2 khớp EDA D3 (1,24; CI 0,93–1,69): giữ cả Shorts và Tin tức rồi kiểm soát bằng biến cho cùng kết quả với việc lọc chúng ra.
  - R3 khớp EDA F (0,98): với chart theo danh mục, khung giờ không tạo khác biệt, CI hẹp hơn vì có 1.017 video trending.
  - R4 cho thấy phần "lợi thế" nằm ở **buổi tối**, không phải sáng sớm, nhưng ngay cả buổi tối cũng chưa chắc chắn.
- **Hạn chế.** R2 và R3 có nhóm danh mục với 0 video trending (Tin tức, Thể thao): hệ số của chúng rất âm, chỉ hữu hạn nhờ mức phạt nhỏ; không ảnh hưởng tới hệ số khung giờ.

## M5. LR dự đoán: chọn tham số, ngưỡng, chấm tập test

- **Vấn đề.** Mô hình đoán được video nào sẽ trending tới đâu, và khung giờ góp bao nhiêu vào dự đoán đó. Đây cũng là các dòng LR và mô hình mốc cho bảng so sánh với XGBoost (M8).
- **Cách giải.**
  - `class_weight="balanced"` vì chỉ 3,9% video trending.
  - Chọn `C` ∈ {0,01 … 10} bằng `StratifiedGroupKFold(5)` theo kênh trên train, tiêu chí **PR-AUC trung bình**; làm riêng cho bộ C và bộ B (bỏ khung giờ).
  - **Ngưỡng** phân loại chọn theo F1 trên dự đoán out-of-fold. Không chọn gì trên tập test.
  - Chấm tập test **một lần**: accuracy, precision, recall, F1, PR-AUC, ROC-AUC, precision ở top 1% và top 5%, ma trận nhầm lẫn; kèm 2 mô hình mốc (`DummyClassifier`).
- **Cài đặt.** `logistic.tinh_chinh_C()`, `chon_nguong()`, `chi_so()`, `mo_hinh_moc()`. Dự đoán trên test lưu ở `data/processed/lr_test_predictions.csv` (cột `p_lr_c`, `p_lr_b`, `du_doan_lr_c`, `nguong_lr_c`) để duc ghép bảng so sánh.
- **Kết quả.**
  - **Cross-validation:** `C = 0,03` cho cả hai bộ. PR-AUC trung bình bộ C **0,206** (từng fold 0,10–0,32), bộ B **0,208**. Chênh lệch C − B trên cùng fold: **−0,002**, dao động −0,013 tới +0,005 → **khung giờ không thêm được gì cho dự đoán**. Ngưỡng theo F1: 0,748 (bộ C), 0,725 (bộ B).
  - **Tập test** (2.079 video, 78 trending):

    | Mô hình | Accuracy | Precision | Recall | F1 | PR-AUC | ROC-AUC | P@1% | P@5% | TP / FP / FN |
    |---|---|---|---|---|---|---|---|---|---|
    | Mốc: luôn đoán "không" | **0,963** | 0 | 0 | 0 | 0,038 | 0,500 | 0,048 | 0,029 | 0 / 0 / 78 |
    | Mốc: ngẫu nhiên theo tỉ lệ | 0,921 | 0,011 | 0,013 | 0,012 | 0,037 | 0,485 | 0 | 0,010 | 1 / 87 / 77 |
    | LR bộ B (không khung giờ) | 0,904 | 0,141 | 0,308 | 0,194 | 0,151 | 0,809 | 0,190 | 0,154 | 24 / 146 / 54 |
    | **LR bộ C (có khung giờ)** | 0,917 | 0,148 | 0,256 | 0,188 | **0,154** | **0,811** | 0,238 | 0,135 | 20 / 115 / 58 |

  - Mô hình mốc có accuracy cao nhất (96,3%) nhưng không tìm ra video trending nào: accuracy vô dụng ở đây, đúng như handover mục 5.
  - LR xếp hạng khá: ROC-AUC 0,81; PR-AUC 0,154 gấp **4 lần** mốc ngẫu nhiên (0,038); trong 21 video được chấm cao nhất có 5 video trending (24%). Nhưng ở ngưỡng F1, chỉ bắt được 26% video trending với precision 15%: dự đoán từng video vẫn rất khó.
  - Bộ C và bộ B gần như bằng nhau trên test (PR-AUC 0,154 so với 0,151), khớp cross-validation: điều mô hình học được nằm ở thể loại, quy mô kênh, thời lượng và ngày đăng, không phải khung giờ.
- **Hạn chế.** PR-AUC từng fold dao động 0,10–0,32 vì mỗi fold chỉ có khoảng 60 video trending; chênh lệch dưới 0,01 giữa hai mô hình không có ý nghĩa. Ngưỡng 0,75 chọn theo F1 trên train; trên test F1 thấp hơn (0,19 so với 0,21 out-of-fold).

## M6. Kết luận phần Logistic Regression

1. **Chưa đủ bằng chứng bác bỏ H₀.** Sau khi kiểm soát ngày đăng, quy mô kênh, thể loại và thời lượng, OR giờ nghỉ / giờ hành chính là **1,19 (CI 95% 0,81–1,72)**. Lợi thế thô 1,36 lần chủ yếu đến từ việc giờ hành chính có nhiều video của những ngày tỉ lệ nền thấp.
2. **Kết luận vững** qua 5 kiểm tra (tập train + test, tập đầy đủ, nhãn danh mục, tối, sáng sớm): mọi CI đều chứa 1; với chart danh mục OR gần đúng 1.
3. **Khung giờ không giúp dự đoán:** bỏ khung giờ khỏi LR, PR-AUC không đổi (−0,002 trong CV, +0,003 trên test). Yếu tố quyết định là **thể loại** (Trò chơi, Âm nhạc), **quy mô kênh** và **thời lượng** (10–60 phút).
4. **Chưa phải lời cuối:** CI còn rộng, không loại trừ lợi thế tới 1,7 lần. Cần XGBoost (M7–M8) để xác nhận chiều, và nhiều dữ liệu hơn để thu hẹp khoảng tin cậy.

## M7. XGBoost: huấn luyện và tinh chỉnh (phat)

*Chưa có. Dùng cùng `train`, `test`, `folds`, `BO_A_XGB`, `BO_B_XGB` và `chi_so()`; `scale_pos_weight` ≈ 25 trên tập chính.*

## M8. XGBoost: khung giờ đóng góp bao nhiêu; so sánh mô hình (duc)

*Chưa có. Theo quy tắc: XGBoost cùng chiều với LR (bỏ biến thời gian không làm PR-AUC giảm) → kết luận vững.*

## M9. Kết luận chung

*Viết sau khi có M7–M8.* Phần LR đã trả lời: không bác bỏ H₀; giờ đăng không phải "thời điểm vàng" sau khi tính tới loại video và ngày đăng.

**Giới hạn chung của phần mô hình:** dữ liệu quan sát (chỉ nói được "đi kèm", không nói được "gây ra"); tập sạch chỉ gồm 14 ngày của các kênh đang theo dõi; Shorts ước lượng theo thời lượng; `channel_subscribers` lấy ở lần chụp mới nhất; 315 video trending trên train nên khoảng tin cậy rộng.
