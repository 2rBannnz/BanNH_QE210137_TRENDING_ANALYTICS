"""Tiện ích dùng chung cho Report 4 (Modeling & Validation).

Logistic Regression (BanNH) và XGBoost (phat, duc) dùng chung file này để cùng bộ
feature, cùng cách chia fold và cùng cách tính chỉ số. Quy ước: docs/TEAM_HANDOVER_REPORT4.md
(mục 3, 4, 5).

Việc đọc dữ liệu và tách train/test theo kênh nằm ở src/modeling/split.py (BanNH đã làm,
test_channels.csv đã commit, KHÔNG tạo lại). File này chỉ nhận DataFrame đã tách.

Luồng dùng trong notebook:
    from src.modeling.split import doc_tap_sach, tach_train_test, loc_co_kha_nang
    from src.modeling import model as M

    train, test = ...                       # lấy từ split.py, tập "có khả năng trending"
    X, y, groups, cols = M.build_features(train, "C", model_type="tree")
    res = M.tune_xgb(X, y, groups, cols)    # phat: tinh chỉnh + chọn ngưỡng
    # gửi duc: res["best_params"], res["threshold"]
"""
import itertools

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.metrics import (accuracy_score, average_precision_score, confusion_matrix,
                             f1_score, precision_recall_curve, precision_score,
                             recall_score, roc_auc_score)
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

RANDOM_STATE = 42
N_SPLITS = 5
LABEL = "is_trending_main"
GROUP = "channel_id"

# Cột cấm: lộ nhãn hoặc là cột làm sạch (mục 4)
FORBIDDEN_EXACT = {"is_trending_main", "is_trending_category", "video_id", "channel_id"}
FORBIDDEN_PREFIX = ("hours_to_trending_", "best_rank_", "coverage_", "flag_", "is_clean")

# Bộ A: thời gian. LR chỉ dùng time_slot để có đúng 1 OR; XGBoost dùng thêm các cột còn lại
FEATURES_A_LR = ["time_slot"]
FEATURES_A_TREE = ["time_slot", "slot_detail", "publish_hour_vn", "publish_dow_vn", "is_weekend"]
TIME_COLS = FEATURES_A_TREE  # mọi cột xác định "giờ nghỉ" đều thuộc nhóm A

# Bộ B: thể loại giữ 4 nhóm (Tin tức, Thể thao đã bị loại khỏi tập chính), còn lại gộp "Khac"
KEEP_CATEGORIES = ["Mọi người và Blog", "Giải trí", "Âm nhạc", "Trò chơi"]


def is_forbidden(col):
    return col in FORBIDDEN_EXACT or col.startswith(FORBIDDEN_PREFIX)


# --------------------------------------------------------------------------- feature
def _to_bool(s):
    """CSV từ psql ghi t/f; CSV từ pandas ghi True/False."""
    if s.dtype != bool:  # object hoặc str (pandas mới) đều có thể chứa chữ t/f
        s = s.astype("string").str.strip().str.lower().map(
            {"t": True, "f": False, "true": True, "false": False}).fillna(False)
    return s.astype(bool)


def build_features(df, feature_set="C", model_type="tree", drop_time=False):
    """Dựng bảng feature từ DataFrame đã tách (train hoặc test).

    feature_set: "A" (thời gian), "B" (kiểm soát) hoặc "C" (A + B, bộ chính).
    model_type:  "lr"   -> time_slot (1 OR) + duration_group
                 "tree" -> thêm slot_detail, giờ, thứ, cuối tuần; thời lượng dạng log10(duration_s)
    drop_time:   True = bỏ toàn bộ biến thời gian (so bộ C với bộ C bỏ thời gian).
    Trả về (X, y, groups, cols) với cols = {"num": [...], "cat": [...]}.
    """
    assert feature_set in ("A", "B", "C"), feature_set
    assert model_type in ("lr", "tree"), model_type
    out = pd.DataFrame(index=df.index)
    num, cat = [], []

    if feature_set in ("A", "C") and not drop_time:
        time_cols = FEATURES_A_LR if model_type == "lr" else FEATURES_A_TREE
        for col in time_cols:
            out[col] = df[col]
        cat += [c for c in time_cols if c in ("time_slot", "slot_detail")]
        num += [c for c in time_cols if c not in ("time_slot", "slot_detail")]
        if "is_weekend" in out:
            out["is_weekend"] = _to_bool(out["is_weekend"]).astype(int)

    if feature_set in ("B", "C"):
        # ngày đăng dạng nhóm (15 giá trị): kiểm soát hiệu ứng ngày
        out["release_date"] = df["release_at_vn"].astype(str).str[:10]
        out["category_group"] = df["category_title"].where(
            df["category_title"].isin(KEEP_CATEGORIES), "Khac")
        out["log10_subs"] = df["log10_subs"]
        out["is_live_or_premiere"] = _to_bool(df["is_live_or_premiere"]).astype(int)
        out["title_length"] = df["title_length"]
        out["n_tags"] = df["n_tags"]
        cat += ["release_date", "category_group"]
        num += ["log10_subs", "is_live_or_premiere", "title_length", "n_tags"]
        if model_type == "lr":
            out["duration_group"] = df["duration_group"]
            cat.append("duration_group")
        else:
            out["log10_duration"] = np.log10(1 + df["duration_s"].clip(lower=0))
            num.append("log10_duration")
        # is_short KHÔNG phải feature: tập chính đã bỏ Shorts (mục 4)

    bad = [c for c in out.columns if is_forbidden(c)]
    assert not bad, f"Cột cấm lọt vào feature: {bad}"
    y = _to_bool(df[LABEL]).astype(int).to_numpy()
    return out, y, df[GROUP].to_numpy(), {"num": num, "cat": cat}


def make_preprocessor(cols, scale=False, drop_first=False):
    """One-hot cho cột nhóm; chuẩn hoá số khi scale=True (dùng cho Logistic Regression)."""
    num_step = StandardScaler() if scale else "passthrough"
    cat_step = OneHotEncoder(handle_unknown="ignore", drop="first" if drop_first else None)
    return ColumnTransformer([("num", num_step, cols["num"]), ("cat", cat_step, cols["cat"])])


# --------------------------------------------------------------------------- chia fold
def cv_folds(y, groups, n_splits=N_SPLITS):
    """Chia fold theo kênh trên tập train (mục 5.2): sinh (chỉ số train, chỉ số validation)."""
    sgkf = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=RANDOM_STATE)
    yield from sgkf.split(np.zeros(len(y)), y, groups=groups)


def check_folds(y, groups, n_splits=N_SPLITS):
    """Kiểm tra: không kênh nào nằm ở cả train và validation, fold nào cũng có nhãn 1."""
    rows = []
    for i, (tr, va) in enumerate(cv_folds(y, groups, n_splits)):
        assert not set(groups[tr]) & set(groups[va]), f"fold {i}: trùng kênh"
        rows.append({"fold": i, "n_train": len(tr), "n_val": len(va),
                     "pos_train": int(y[tr].sum()), "pos_val": int(y[va].sum())})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- mất cân bằng
def scale_pos_weight(y):
    """XGBoost: số nhãn 0 / số nhãn 1. Gọi trên y của TỪNG fold train (khoảng 25 trên tập chính)."""
    y = np.asarray(y)
    pos = int(y.sum())
    return float((len(y) - pos) / pos) if pos else 1.0


# --------------------------------------------------------------------------- đánh giá
def best_f1_threshold(y_true, score):
    """Ngưỡng cho F1 cao nhất. Chỉ chọn trong CV, không chọn trên tập test (mục 5.4)."""
    prec, rec, thr = precision_recall_curve(y_true, score)
    f1 = 2 * prec[:-1] * rec[:-1] / np.clip(prec[:-1] + rec[:-1], 1e-12, None)
    return float(thr[int(np.argmax(f1))]) if len(thr) else 0.5


def precision_at_top(y_true, score, frac):
    """Precision trong top frac (ví dụ 0,01) số video có điểm cao nhất."""
    y_true = np.asarray(y_true)
    k = max(1, int(np.ceil(frac * len(y_true))))
    return float(y_true[np.argsort(-np.asarray(score), kind="stable")[:k]].mean())


def evaluate(y_true, score, threshold):
    """Đủ chỉ số mục 5.5. Chọn mô hình bằng pr_auc; accuracy phải đặt cạnh mô hình mốc."""
    y_true = np.asarray(y_true)
    pred = (np.asarray(score) >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
    return {
        "accuracy": accuracy_score(y_true, pred),
        "precision": precision_score(y_true, pred, zero_division=0),
        "recall": recall_score(y_true, pred, zero_division=0),
        "f1": f1_score(y_true, pred, zero_division=0),
        "pr_auc": average_precision_score(y_true, score),
        "roc_auc": roc_auc_score(y_true, score) if len(np.unique(y_true)) > 1 else np.nan,
        "precision_top1pct": precision_at_top(y_true, score, 0.01),
        "precision_top5pct": precision_at_top(y_true, score, 0.05),
        "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
    }


def baselines():
    """Hai mô hình mốc (mục 5.6)."""
    return {
        "mốc: luôn đoán 0": DummyClassifier(strategy="most_frequent", random_state=RANDOM_STATE),
        "mốc: ngẫu nhiên theo tỉ lệ": DummyClassifier(strategy="stratified", random_state=RANDOM_STATE),
    }


# --------------------------------------------------------------------------- XGBoost (phat)
XGB_GRID = {
    "max_depth": [3, 4, 6],
    "learning_rate": [0.03, 0.1],
    "n_estimators": [200, 400],
    "min_child_weight": [1, 5],
    "subsample": [0.8, 1.0],
}


def make_xgb(params, spw):
    """XGBClassifier với scale_pos_weight cho một fold. Import muộn: chỉ ai cài nhóm xgboost mới cần."""
    from xgboost import XGBClassifier
    return XGBClassifier(objective="binary:logistic", eval_metric="aucpr",
                         scale_pos_weight=spw, random_state=RANDOM_STATE,
                         n_jobs=-1, tree_method="hist", **params)


def _grid(grid):
    keys = list(grid)
    for vals in itertools.product(*(grid[k] for k in keys)):
        yield dict(zip(keys, vals))


def cv_oof(X, y, groups, cols, params, model_factory=make_xgb, n_splits=N_SPLITS):
    """Chạy CV theo kênh, tiền xử lý và scale_pos_weight tính TRONG từng fold (không rò rỉ).

    Trả về (oof_score, pr_auc_từng_fold). oof_score là điểm dự đoán ngoài fold cho mọi video.
    """
    oof = np.zeros(len(y), dtype=float)
    fold_pr = []
    for tr, va in cv_folds(y, groups, n_splits):
        pipe = Pipeline([("pre", make_preprocessor(cols, scale=False)),
                         ("clf", model_factory(params, scale_pos_weight(y[tr])))])
        pipe.fit(X.iloc[tr], y[tr])
        oof[va] = pipe.predict_proba(X.iloc[va])[:, 1]
        fold_pr.append(average_precision_score(y[va], oof[va]))
    return oof, np.array(fold_pr)


def tune_xgb(X, y, groups, cols, grid=None, model_factory=make_xgb, verbose=True):
    """Tìm tham số theo PR-AUC trung bình trên CV, rồi chọn ngưỡng F1 từ điểm ngoài fold.

    Trả về dict: best_params, best_pr_auc_mean, best_pr_auc_std, threshold, oof_score, table
    (bảng mọi tổ hợp, sắp theo PR-AUC giảm dần). Đây là thứ giao cho duc.
    """
    rows, best = [], None
    for params in _grid(grid or XGB_GRID):
        oof, fold_pr = cv_oof(X, y, groups, cols, params, model_factory)
        row = {**params, "pr_auc_mean": fold_pr.mean(), "pr_auc_std": fold_pr.std()}
        rows.append(row)
        if best is None or row["pr_auc_mean"] > best["row"]["pr_auc_mean"]:
            best = {"row": row, "params": params, "oof": oof}
        if verbose:
            print(f"{params} -> PR-AUC {fold_pr.mean():.4f} ± {fold_pr.std():.4f}")
    return {
        "best_params": best["params"],
        "best_pr_auc_mean": best["row"]["pr_auc_mean"],
        "best_pr_auc_std": best["row"]["pr_auc_std"],
        "threshold": best_f1_threshold(y, best["oof"]),
        "oof_score": best["oof"],
        "table": pd.DataFrame(rows).sort_values("pr_auc_mean", ascending=False).reset_index(drop=True),
    }
