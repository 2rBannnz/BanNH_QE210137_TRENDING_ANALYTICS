"""Tách tập test giữ riêng cho Report 4, theo kênh (dùng chung cho mọi mô hình).

Quy ước (docs/TEAM_HANDOVER_REPORT4.md mục 5):
- Dữ liệu: bản đóng băng v_video_features, chỉ lấy is_clean = TRUE, nhãn is_trending_main.
- StratifiedGroupKFold(5, shuffle=True, random_state=42) theo channel_id; fold đầu làm test
  (khoảng 20% số kênh). Video cùng kênh luôn nằm cùng phía.
- Danh sách kênh test ghi ra data/processed/test_channels.csv (commit). Tập test chỉ chấm một lần ở cuối.
- Tập mô hình chính = video "có khả năng trending" (EDA D5): bỏ Shorts (is_short, <= 3 phút),
  Tin tức và Chính trị, Thể thao. Ba nhóm này gần như không bao giờ lên chart chính
  (5/23.093, 0/9.632, 0/3.021 trong is_clean) nên chỉ làm loãng phép so sánh khung giờ.
  Kênh test chọn trên toàn bộ is_clean rồi mới lọc, để tập đầy đủ (kiểm tra độ vững) dùng cùng kênh.

Chạy từ thư mục gốc repo (ghi file):
    python -m src.modeling.split

Dùng trong notebook:
    from src.modeling.split import doc_tap_sach, tach_train_test, loc_co_kha_nang
    df = doc_tap_sach()
    train, test = tach_train_test(df)                         # toàn bộ is_clean (độ vững)
    train, test = loc_co_kha_nang(train), loc_co_kha_nang(test)  # tập chính
"""
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

from src.utils.config import Config

CSV_DONG_BANG = Config.LOCAL_DATA_DIR / "processed" / "video_features_full_2026-11-01.csv"
FILE_KENH_TEST = Config.LOCAL_DATA_DIR / "processed" / "test_channels.csv"
RANDOM_STATE = 42
SO_FOLD = 5
DANH_MUC_BO = ("Tin tức và Chính trị", "Thể thao")


def doc_tap_sach(path=CSV_DONG_BANG) -> pd.DataFrame:
    """Đọc CSV đóng băng, chuyển cột t/f về bool, lọc is_clean."""
    df = pd.read_csv(path, low_memory=False)
    cot_bool = [c for c in df.columns if df[c].dropna().isin(["t", "f"]).all() and df[c].notna().any()]
    for c in cot_bool:
        df[c] = df[c].map({"t": True, "f": False})
    return df[df["is_clean"].fillna(False)].reset_index(drop=True)


def loc_co_kha_nang(df: pd.DataFrame) -> pd.DataFrame:
    """Giữ video có khả năng lên chart chính: không phải Shorts, không thuộc Tin tức, Thể thao."""
    giu = ~df["is_short"].fillna(True) & ~df["category_title"].isin(DANH_MUC_BO)
    return df[giu].reset_index(drop=True)


def chon_kenh_test(df: pd.DataFrame) -> pd.Series:
    """Fold đầu của StratifiedGroupKFold theo kênh -> tập kênh test (sắp xếp để file ổn định)."""
    skf = StratifiedGroupKFold(n_splits=SO_FOLD, shuffle=True, random_state=RANDOM_STATE)
    _, idx_test = next(skf.split(df, df["is_trending_main"], groups=df["channel_id"]))
    return pd.Series(sorted(df["channel_id"].iloc[idx_test].unique()), name="channel_id")


def tach_train_test(df: pd.DataFrame, file_kenh_test=FILE_KENH_TEST):
    """Trả về (train, test) theo danh sách kênh đã ghi; nếu chưa có file thì tạo rồi ghi."""
    if file_kenh_test.exists():
        kenh_test = pd.read_csv(file_kenh_test)["channel_id"]
    else:
        kenh_test = chon_kenh_test(df)
        kenh_test.to_frame().to_csv(file_kenh_test, index=False)
    la_test = df["channel_id"].isin(set(kenh_test))
    return df[~la_test].reset_index(drop=True), df[la_test].reset_index(drop=True)


def tom_tat(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    """Bảng kiểm tra: số video, số kênh, số trending, tỉ lệ ở mỗi phía."""
    rows = []
    for ten, d in [("train", train), ("test", test)]:
        rows.append({"tap": ten, "so_video": len(d), "so_kenh": d["channel_id"].nunique(),
                     "so_trending": int(d["is_trending_main"].sum()),
                     "ti_le_trending": round(d["is_trending_main"].mean() * 100, 2),
                     "pct_hanh_chinh": round((d["time_slot"] == "hanh_chinh").mean() * 100, 1)})
    return pd.DataFrame(rows)


def main():
    df = doc_tap_sach()
    train, test = tach_train_test(df)
    assert not set(train["channel_id"]) & set(test["channel_id"]), "kênh nằm ở cả train và test"
    print(f"Đã ghi {FILE_KENH_TEST}")
    print("Toàn bộ is_clean (kiểm tra độ vững):")
    print(tom_tat(train, test).to_string(index=False))
    print("Tập chính, video có khả năng trending (bỏ Shorts, Tin tức, Thể thao):")
    print(tom_tat(loc_co_kha_nang(train), loc_co_kha_nang(test)).to_string(index=False))


if __name__ == "__main__":
    main()
