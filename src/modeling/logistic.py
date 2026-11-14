"""Logistic Regression cho Report 4 (phần của BanNH): mô hình quyết định giả thuyết H₀.

Hai việc riêng biệt, cùng một bộ feature:
1. Suy luận: odds ratio (OR) giờ nghỉ / giờ hành chính của time_slot, LR gần như không phạt
   (C = 1e4) và không trọng số lớp, khoảng tin cậy 95% bằng bootstrap theo kênh (percentile).
2. Dự đoán: LR có class_weight="balanced", chọn C bằng StratifiedGroupKFold theo kênh (PR-AUC),
   chọn ngưỡng theo F1 trên dự đoán out-of-fold, chấm tập test đúng một lần.

Quy ước chung: docs/TEAM_HANDOVER_REPORT4.md mục 5. Dùng trong notebooks/2_Modeling.ipynb.
"""
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, confusion_matrix, precision_recall_curve,
                             roc_auc_score)
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.modeling.features import COT_PHAN_LOAI, kiem_tra_cot_cam

RANDOM_STATE = 42
C_SUY_LUAN = 1e4          # phạt gần bằng 0: hệ số là ước lượng hợp lý cực đại, không bị co về 0
LUOI_C = (0.01, 0.03, 0.1, 0.3, 1, 3, 10)


# ---------------------------------------------------------------- ma trận đặc trưng
def bo_bien_doi(cot) -> ColumnTransformer:
    """One-hot các cột phân loại (bỏ mức đầu theo thứ tự chữ cái làm tham chiếu), chuẩn hoá cột số."""
    kiem_tra_cot_cam(cot)
    phan_loai = [c for c in cot if c in COT_PHAN_LOAI]
    so = [c for c in cot if c not in COT_PHAN_LOAI]
    return ColumnTransformer([
        ("pl", OneHotEncoder(drop="first", handle_unknown="ignore", sparse_output=False), phan_loai),
        ("so", StandardScaler(), so),
    ], verbose_feature_names_out=False)


def ma_tran(df: pd.DataFrame, cot, bien_doi=None):
    """Trả về (X dạng DataFrame có tên cột, bộ biến đổi đã fit)."""
    if bien_doi is None:
        bien_doi = bo_bien_doi(cot).fit(df[cot])
    X = pd.DataFrame(bien_doi.transform(df[cot]), columns=bien_doi.get_feature_names_out(), index=df.index)
    return X.astype(float), bien_doi


# ---------------------------------------------------------------- suy luận: OR và bootstrap theo kênh
def lr_suy_luan() -> LogisticRegression:
    return LogisticRegression(C=C_SUY_LUAN, max_iter=20000, tol=1e-6)


def he_so(df: pd.DataFrame, cot, nhan="is_trending_main", w=None) -> pd.Series:
    """Hệ số LR gần như không phạt trên df[cot]; w = trọng số dòng (dùng cho bootstrap)."""
    X, _ = ma_tran(df, cot)
    m = lr_suy_luan().fit(X, df[nhan].astype(int), sample_weight=w)
    return pd.Series(m.coef_[0], index=X.columns)


def bootstrap_or(df: pd.DataFrame, cot, nhan="is_trending_main", n_boot=500, seed=RANDOM_STATE) -> pd.DataFrame:
    """OR điểm và CI 95% percentile cho mọi hệ số, bootstrap theo kênh (lấy mẫu lại kênh có hoàn lại).

    Mỗi lần: rút ngẫu nhiên các kênh có hoàn lại, kênh được rút k lần thì mọi video của nó có trọng số k;
    fit lại LR với trọng số đó. Cách này tương đương nối các kênh được rút lại với nhau.
    """
    X, _ = ma_tran(df, cot)
    y = df[nhan].astype(int).to_numpy()
    kenh = df["channel_id"].to_numpy()
    kenh_dn = np.unique(kenh)
    rng = np.random.default_rng(seed)
    goc = lr_suy_luan().fit(X, y).coef_[0]
    mau = np.empty((n_boot, X.shape[1]))
    for b in range(n_boot):
        dem = pd.Series(rng.choice(kenh_dn, size=len(kenh_dn), replace=True)).value_counts()
        w = pd.Series(kenh).map(dem).fillna(0).to_numpy()
        mau[b] = lr_suy_luan().fit(X, y, sample_weight=w).coef_[0]
    lo, hi = np.percentile(mau, [2.5, 97.5], axis=0)
    return pd.DataFrame({"he_so": goc, "or": np.exp(goc), "ci_thap": np.exp(lo), "ci_cao": np.exp(hi)},
                        index=X.columns)


def dong_or(bang: pd.DataFrame, ten="time_slot_nghi") -> str:
    """Chuỗi 'OR (CI thấp – CI cao)' cho một hệ số, dấu phẩy thập phân."""
    r = bang.loc[ten]
    return f"{r['or']:.2f} ({r['ci_thap']:.2f}–{r['ci_cao']:.2f})".replace(".", ",")


# ---------------------------------------------------------------- dự đoán: chọn C, ngưỡng, chỉ số
def lr_du_doan(C: float) -> LogisticRegression:
    return LogisticRegression(C=C, class_weight="balanced", max_iter=5000)


def ong_du_doan(cot, C: float) -> Pipeline:
    return Pipeline([("bien_doi", bo_bien_doi(cot)), ("lr", lr_du_doan(C))])


def chia_fold(df: pd.DataFrame, nhan="is_trending_main", n_splits=5, seed=RANDOM_STATE):
    """Các cặp (idx_train, idx_val) của StratifiedGroupKFold theo kênh trên df."""
    skf = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    return list(skf.split(df, df[nhan], groups=df["channel_id"]))


def tinh_chinh_C(df: pd.DataFrame, cot, nhan="is_trending_main", luoi=LUOI_C, folds=None):
    """Chọn C theo PR-AUC trung bình trên các fold. Trả về (bảng kết quả, C tốt nhất, xác suất OOF ở C đó)."""
    folds = folds or chia_fold(df, nhan)
    y = df[nhan].astype(int).to_numpy()
    ket_qua, oof_theo_C = [], {}
    for C in luoi:
        oof = np.full(len(df), np.nan)
        pr = []
        for i_tr, i_va in folds:
            m = ong_du_doan(cot, C).fit(df.iloc[i_tr][cot], y[i_tr])
            oof[i_va] = m.predict_proba(df.iloc[i_va][cot])[:, 1]
            pr.append(average_precision_score(y[i_va], oof[i_va]))
        ket_qua.append({"C": C, "pr_auc_tb": np.mean(pr), "pr_auc_min": np.min(pr), "pr_auc_max": np.max(pr)})
        oof_theo_C[C] = oof
    bang = pd.DataFrame(ket_qua)
    C_tot = float(bang.loc[bang["pr_auc_tb"].idxmax(), "C"])
    return bang, C_tot, oof_theo_C[C_tot]


def pr_auc_tung_fold(df: pd.DataFrame, cot, C: float, nhan="is_trending_main", folds=None) -> np.ndarray:
    """PR-AUC từng fold của một bộ feature ở một C (để so hai bộ feature trên cùng fold)."""
    folds = folds or chia_fold(df, nhan)
    y = df[nhan].astype(int).to_numpy()
    out = []
    for i_tr, i_va in folds:
        m = ong_du_doan(cot, C).fit(df.iloc[i_tr][cot], y[i_tr])
        out.append(average_precision_score(y[i_va], m.predict_proba(df.iloc[i_va][cot])[:, 1]))
    return np.array(out)


def chon_nguong(y, p) -> float:
    """Ngưỡng cho F1 cao nhất trên (y, p); dùng với dự đoán out-of-fold, không dùng trên tập test."""
    prec, rec, ng = precision_recall_curve(y, p)
    f1 = 2 * prec[:-1] * rec[:-1] / np.clip(prec[:-1] + rec[:-1], 1e-12, None)
    return float(ng[int(np.argmax(f1))])


def chi_so(y, p, nguong: float) -> dict:
    """Bộ chỉ số theo handover mục 5: accuracy, precision, recall, F1, PR-AUC, ROC-AUC, precision@1%, @5%, ma trận nhầm lẫn."""
    y = np.asarray(y).astype(int)
    p = np.asarray(p, dtype=float)
    du_doan = (p >= nguong).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, du_doan, labels=[0, 1]).ravel()
    thu_tu = np.argsort(-p, kind="stable")

    def prec_tai(ti_le):
        k = max(1, int(np.ceil(ti_le * len(p))))
        return y[thu_tu[:k]].mean()

    return {"accuracy": (tp + tn) / len(y),
            "precision": tp / (tp + fp) if tp + fp else 0.0,
            "recall": tp / (tp + fn) if tp + fn else 0.0,
            "f1": 2 * tp / (2 * tp + fp + fn) if tp else 0.0,
            "pr_auc": average_precision_score(y, p),
            "roc_auc": roc_auc_score(y, p) if len(np.unique(p)) > 1 else 0.5,
            "prec_top1pct": prec_tai(0.01), "prec_top5pct": prec_tai(0.05),
            "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp), "nguong": nguong}


def mo_hinh_moc(y_train, y_test, seed=RANDOM_STATE) -> dict:
    """Hai mô hình mốc: luôn đoán lớp nhiều nhất; đoán ngẫu nhiên theo tỉ lệ lớp."""
    X_tr = np.zeros((len(y_train), 1))
    X_te = np.zeros((len(y_test), 1))
    out = {}
    for ten, chien_luoc in [("Mốc: luôn đoán không trending", "most_frequent"), ("Mốc: ngẫu nhiên theo tỉ lệ", "stratified")]:
        m = DummyClassifier(strategy=chien_luoc, random_state=seed).fit(X_tr, y_train)
        out[ten] = chi_so(y_test, m.predict_proba(X_te)[:, 1], 0.5)
    return out
