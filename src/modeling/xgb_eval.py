"""XGBoost: giải thích và đánh giá (phần của duc, Report 4).

Quy ước: docs/TEAM_HANDOVER_REPORT4.md (mục 5, 6, 7). File này CHỈ THÊM hàm mới, không sửa
model.py (phần của phat/BanNH). Dùng lại build_features, cv_folds, cv_oof, evaluate, baselines
từ model.py nên cùng bộ feature, cùng cách chia fold, cùng cách tính chỉ số.

Luồng dùng trong notebook:
    from src.modeling import model as M
    from src.modeling import xgb_eval as E
    d = E.so_sanh_co_bo_thoi_gian(train, best_params)           # 3c: bộ C và bộ C bỏ thời gian
    imp = E.permutation_importance_cv(train, best_params)       # 3c: permutation importance
    kq = E.kiem_tra_dot(train, best_params)                     # kiểm tra phụ: đợt 1 -> đợt 2
    bang, cms = E.bang_so_sanh_test(train, test, best_params, threshold_xgb,
                                    lr_score=..., lr_threshold=..., da_chot=True)   # bước 4
"""
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score
from sklearn.pipeline import Pipeline

from src.modeling import model as M

N_REPEATS = 10  # số lần hoán vị mỗi feature trong mỗi fold

# Kiểm tra phụ (mục 6): train đợt 1, test đợt 2 (ngày theo giờ Việt Nam)
DOT_1 = ("2026-09-25", "2026-10-05")
DOT_2 = ("2026-10-10", "2026-10-12", "2026-10-19")


# --------------------------------------------------------------------------- tiện ích
def _pipeline(cols, params, y_train, model_factory):
    """Pipeline một fold: one-hot + mô hình, scale_pos_weight tính từ y của phần train."""
    return Pipeline([("pre", M.make_preprocessor(cols, scale=False)),
                     ("clf", model_factory(params, M.scale_pos_weight(y_train)))])


def _ten_cot(cols):
    """Tên cột thật có trong X (bộ C kiểu tree), để hoán vị theo từng cột."""
    return list(cols["num"]) + list(cols["cat"])


# --------------------------------------------------------------------------- 1. có / bỏ thời gian
def so_sanh_co_bo_thoi_gian(train, params, model_factory=M.make_xgb):
    """So PR-AUC của bộ C và bộ C bỏ biến thời gian, cùng fold, cùng tham số (mục 2, 6).

    Hai lần chạy dùng chung cv_folds (cùng y, cùng nhóm kênh, cùng random_state) nên fold khớp
    nhau từng dòng và ΔPR-AUC từng fold có nghĩa. delta = PR-AUC(C) - PR-AUC(C bỏ thời gian):
    dương = biến thời gian giúp dự đoán; âm = bỏ thời gian lại tốt hơn.

    Trả về dict: bang (từng fold), tom_tat (trung bình, độ lệch chuẩn, min, max, số fold dương).
    """
    X_c, y, g, cols_c = M.build_features(train, "C", "tree", drop_time=False)
    X_n, y2, g2, cols_n = M.build_features(train, "C", "tree", drop_time=True)
    assert (y == y2).all() and (g == g2).all()

    _, pr_c = M.cv_oof(X_c, y, g, cols_c, params, model_factory)
    _, pr_n = M.cv_oof(X_n, y, g, cols_n, params, model_factory)
    delta = pr_c - pr_n

    bang = pd.DataFrame({"fold": range(len(delta)), "pr_auc_C": pr_c,
                         "pr_auc_C_bo_thoi_gian": pr_n, "delta": delta})
    tom_tat = {
        "pr_auc_C_tb": pr_c.mean(), "pr_auc_C_bo_thoi_gian_tb": pr_n.mean(),
        "delta_tb": delta.mean(), "delta_std": delta.std(ddof=1),
        "delta_min": delta.min(), "delta_max": delta.max(),
        "so_fold_delta_duong": int((delta > 0).sum()), "so_fold": len(delta),
        "so_cot_thoi_gian_bi_bo": len(M.TIME_COLS),
    }
    return {"bang": bang, "tom_tat": tom_tat}


# --------------------------------------------------------------------------- 2. permutation importance
def permutation_importance_cv(train, params, model_factory=M.make_xgb,
                              n_repeats=N_REPEATS, gom_thoi_gian=True):
    """Permutation importance trên phần validation của từng fold CV (KHÔNG dùng tập test).

    Mỗi fold: huấn luyện trên phần train của fold, rồi trên validation hoán vị ngẫu nhiên MỘT
    cột (giữ nguyên các cột khác) và đo PR-AUC giảm bao nhiêu. Giảm càng nhiều = càng quan trọng.
    Các cột thời gian tương quan mạnh với nhau (time_slot, slot_detail, giờ, thứ, cuối tuần), nên
    hoán vị từng cột lẻ sẽ bị cột còn lại "gánh" và cho số thấp giả. Vì vậy thêm dòng
    "NHÓM: thời gian" hoán vị cả 5 cột CÙNG MỘT hoán vị hàng (giữ tương quan giữa chúng).

    Trả về DataFrame: feature, giam_pr_auc_tb, giam_pr_auc_std_fold, so_fold_giam_duong.
    """
    X, y, g, cols = M.build_features(train, "C", "tree")
    ten_cot = _ten_cot(cols)
    nhom = {c: [c] for c in ten_cot}
    if gom_thoi_gian:
        nhom["NHÓM: thời gian"] = [c for c in M.TIME_COLS if c in X.columns]

    rng = np.random.default_rng(M.RANDOM_STATE)
    giam = {k: [] for k in nhom}  # k -> danh sách mức giảm TB (qua n_repeats) của từng fold

    for tr, va in M.cv_folds(y, g):
        pipe = _pipeline(cols, params, y[tr], model_factory)
        pipe.fit(X.iloc[tr], y[tr])
        Xv, yv = X.iloc[va].reset_index(drop=True), y[va]
        goc = average_precision_score(yv, pipe.predict_proba(Xv)[:, 1])
        for ten, cac_cot in nhom.items():
            mat = []
            for _ in range(n_repeats):
                perm = rng.permutation(len(Xv))        # một hoán vị hàng cho cả nhóm cột
                Xp = Xv.copy()
                for c in cac_cot:                      # từng cột, để giữ nguyên dtype
                    Xp[c] = Xv[c].to_numpy()[perm]
                mat.append(goc - average_precision_score(yv, pipe.predict_proba(Xp)[:, 1]))
            giam[ten].append(float(np.mean(mat)))

    rows = [{"feature": k, "giam_pr_auc_tb": np.mean(v), "giam_pr_auc_std_fold": np.std(v, ddof=1),
             "so_fold_giam_duong": int(sum(x > 0 for x in v)), "so_fold": len(v)}
            for k, v in giam.items()]
    return (pd.DataFrame(rows).sort_values("giam_pr_auc_tb", ascending=False)
            .reset_index(drop=True))


# --------------------------------------------------------------------------- 3. kiểm tra phụ: đợt 1 -> đợt 2
def kiem_tra_dot(train, params, model_factory=M.make_xgb, bo_release_date=True):
    """Train đợt 1 (25/09-05/10), test đợt 2 (10, 12, 19/10) (mục 6).

    - Chỉ dùng `train` (các kênh train), KHÔNG đụng vào kênh của tập test giữ riêng.
    - Ngưỡng chọn bằng CV theo kênh trong đợt 1 (mục 5.4), không chọn trên đợt 2.
    - bo_release_date=True: bỏ biến ngày đăng khỏi bộ feature, vì ngày của đợt 2 chưa từng xuất
      hiện lúc train (one-hot ra toàn 0), giữ lại chỉ làm mô hình học tỉ lệ riêng từng ngày.
    - Cùng kênh có thể xuất hiện ở cả hai đợt, nên đây là kiểm tra ổn định theo thời gian,
      không phải kiểm tra trên kênh mới (khác tập test giữ riêng).
    Trả về dict: bang_chi_so (XGB + 2 mốc), thong_ke (kích thước từng đợt), threshold.
    """
    ngay = train["release_at_vn"].astype(str).str[:10]
    la_dot1 = (ngay >= DOT_1[0]) & (ngay <= DOT_1[1])
    la_dot2 = ngay.isin(DOT_2)
    d1, d2 = train[la_dot1].reset_index(drop=True), train[la_dot2].reset_index(drop=True)

    X1, y1, g1, cols = M.build_features(d1, "C", "tree")
    X2, y2, _, _ = M.build_features(d2, "C", "tree")
    if bo_release_date:
        X1, X2 = X1.drop(columns="release_date"), X2.drop(columns="release_date")
        cols = {"num": cols["num"], "cat": [c for c in cols["cat"] if c != "release_date"]}

    oof, pr_cv = M.cv_oof(X1, y1, g1, cols, params, model_factory)
    thr = M.best_f1_threshold(y1, oof)

    pipe = _pipeline(cols, params, y1, model_factory)
    pipe.fit(X1, y1)
    rows = {"XGBoost (train đợt 1 -> test đợt 2)": M.evaluate(y2, pipe.predict_proba(X2)[:, 1], thr)}
    for ten, clf in M.baselines().items():
        clf.fit(X1, y1)
        rows[ten] = M.evaluate(y2, clf.predict_proba(X2)[:, 1], 0.5)

    thong_ke = pd.DataFrame([
        {"dot": "đợt 1 (train)", "so_video": len(d1), "so_trending": int(y1.sum()),
         "ti_le_%": round(100 * y1.mean(), 2)},
        {"dot": "đợt 2 (test)", "so_video": len(d2), "so_trending": int(y2.sum()),
         "ti_le_%": round(100 * y2.mean(), 2)}])
    return {"bang_chi_so": pd.DataFrame(rows).T, "thong_ke": thong_ke, "threshold": thr,
            "pr_auc_cv_dot1_tb": float(pr_cv.mean()), "pr_auc_cv_dot1_std": float(pr_cv.std())}


# --------------------------------------------------------------------------- 4. bảng so sánh trên tập test
def bang_so_sanh_test(train, test, params, threshold_xgb, lr_score=None, lr_threshold=None,
                      model_factory=M.make_xgb, da_chot=False):
    """Bảng 4 dòng trên tập test: 2 mốc, Logistic Regression, XGBoost (mục 5, 6, bước 4).

    CHỈ CHẤM TEST MỘT LẦN, khi cả 2 mô hình đã chốt (mục 5.1). Vì vậy hàm từ chối chạy nếu
    chưa truyền da_chot=True. Đặt da_chot=True khi phat đã chốt tham số + ngưỡng XGBoost và BanNH
    đã chốt LR, rồi chạy đúng một lần.

    lr_score: điểm dự đoán xác suất của LR cho từng video test, cùng thứ tự với `test`
              (BanNH cung cấp: pipeline.predict_proba(X_test)[:, 1]); lr_threshold: ngưỡng F1 từ CV.
    Nếu chưa có LR, dòng LR để trống (NaN) để bảng vẫn đủ 4 dòng.
    Trả về (bang, ma_tran): bang = DataFrame 4 dòng; ma_tran = {tên: [[tn, fp], [fn, tp]]}.
    """
    if not da_chot:
        raise RuntimeError("Tập test chỉ chấm một lần, khi cả 2 mô hình đã chốt (mục 5.1). "
                           "Chạy lại với da_chot=True khi phat và BanNH đã chốt.")

    X_tr, y_tr, _, cols = M.build_features(train, "C", "tree")
    X_te, y_te, _, _ = M.build_features(test, "C", "tree")

    rows = {}
    for ten, clf in M.baselines().items():
        clf.fit(X_tr, y_tr)
        rows[ten] = M.evaluate(y_te, clf.predict_proba(X_te)[:, 1], 0.5)

    if lr_score is not None:
        assert len(lr_score) == len(y_te), "lr_score phải cùng thứ tự và số dòng với test"
        rows["Logistic Regression"] = M.evaluate(y_te, lr_score, lr_threshold)
    else:
        rows["Logistic Regression"] = {k: np.nan for k in M.evaluate([0, 1], [0.1, 0.9], 0.5)}

    pipe = _pipeline(cols, params, y_tr, model_factory)  # fit trên toàn bộ train
    pipe.fit(X_tr, y_tr)
    rows["XGBoost"] = M.evaluate(y_te, pipe.predict_proba(X_te)[:, 1], threshold_xgb)

    thu_tu = ["mốc: luôn đoán 0", "mốc: ngẫu nhiên theo tỉ lệ", "Logistic Regression", "XGBoost"]
    bang = pd.DataFrame(rows).T.loc[thu_tu]
    ma_tran = {t: [[int(bang.loc[t, "tn"]), int(bang.loc[t, "fp"])],
                   [int(bang.loc[t, "fn"]), int(bang.loc[t, "tp"])]]
               for t in thu_tu if not np.isnan(bang.loc[t, "tn"])}
    return bang, ma_tran


def doc_diem_lr(test, path, cot_diem="p_lr_c"):
    """Đọc file điểm LR của BanNH (lr_test_predictions.csv) và xếp đúng thứ tự dòng của `test`.

    Khớp theo video_id, và dừng ngay nếu thiếu video, trùng video, hoặc nhãn y lệch với test.
    cot_diem: "p_lr_c" = LR bộ C (bộ chính); "p_lr_b" = LR bộ B (chỉ kiểm soát).
    Trả về (lr_score, lr_threshold) để truyền vào bang_so_sanh_test.
    """
    lr = pd.read_csv(path)
    assert lr["video_id"].is_unique, "file LR có video_id trùng"
    lr = lr.set_index("video_id").reindex(test["video_id"])
    assert lr[cot_diem].notna().all(), "test có video không có điểm LR"
    y_test = test[M.LABEL].astype(int).to_numpy()
    assert (lr["y"].to_numpy() == y_test).all(), "nhãn y trong file LR lệch với test"
    thr = float(lr["nguong_lr_c"].iloc[0])
    return lr[cot_diem].to_numpy(), thr


def ve_confusion(ma_tran, ax_per_row=2):
    """Vẽ các confusion matrix (nhãn tiếng Việt). Trả về figure."""
    import matplotlib.pyplot as plt
    n = len(ma_tran)
    nrow = int(np.ceil(n / ax_per_row))
    fig, axes = plt.subplots(nrow, ax_per_row, figsize=(4.2 * ax_per_row, 3.6 * nrow))
    axes = np.atleast_1d(axes).ravel()
    for ax, (ten, cm) in zip(axes, ma_tran.items()):
        cm = np.array(cm)
        ax.imshow(cm, cmap="Blues")
        for i in range(2):
            for j in range(2):
                ax.text(j, i, f"{cm[i, j]:,}", ha="center", va="center",
                        color="white" if cm[i, j] > cm.max() / 2 else "black")
        ax.set_xticks([0, 1], ["đoán: không", "đoán: trending"])
        ax.set_yticks([0, 1], ["thật: không", "thật: trending"])
        ax.set_title(ten, fontsize=10)
    for ax in axes[n:]:
        ax.axis("off")
    fig.tight_layout()
    return fig
