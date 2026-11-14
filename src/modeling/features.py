"""Định nghĩa feature dùng chung cho mọi mô hình Report 4 (LR và XGBoost dùng cùng một chỗ).

Theo docs/TEAM_HANDOVER_REPORT4.md mục 4:
- Bộ A (thời gian): LR chỉ dùng time_slot để có một odds ratio; XGBoost dùng thêm các biến giờ chi tiết.
- Bộ B (kiểm soát): ngày đăng, quy mô kênh, danh mục (gộp), thời lượng, livestream, độ dài tiêu đề, số tag.
- Bộ C = A + B.
Các cột lộ nhãn hoặc cột làm sạch không bao giờ được đưa vào mô hình (COT_CAM).
"""
import numpy as np
import pandas as pd

# Cột lộ nhãn (biết sau khi video đã trending) hoặc cột làm sạch: cấm đưa vào mô hình
COT_CAM = ("is_trending_main", "hours_to_trending_main", "best_rank_main",
           "is_trending_category", "hours_to_trending_category", "best_rank_category",
           "coverage_24h", "coverage_72h", "coverage_cat_24h", "coverage_cat_72h",
           "flag_no_duration", "flag_hidden_subs", "flag_extreme_duration",
           "flag_low_coverage", "flag_low_coverage_cat", "is_clean", "is_clean_category",
           "video_id", "channel_id")

# Danh mục giữ riêng; còn lại gộp "Khác". Tập chính đã bỏ Tin tức, Thể thao nên chỉ còn 4 nhóm;
# tập đầy đủ (kiểm tra độ vững) và nhãn danh mục giữ cả 6 danh mục lớn như EDA D3.
DANH_MUC_CHINH = ("Mọi người và Blog", "Giải trí", "Âm nhạc", "Trò chơi")
DANH_MUC_DAY_DU = DANH_MUC_CHINH + ("Tin tức và Chính trị", "Thể thao")

BO_A_LR = ["time_slot"]
BO_A_XGB = ["time_slot", "slot_detail", "publish_hour_vn", "publish_dow_vn", "is_weekend"]
BO_B_LR = ["ngay", "log10_subs", "cat_gop", "duration_group", "is_live_or_premiere", "title_length", "n_tags"]
BO_B_XGB = ["ngay", "log10_subs", "cat_gop", "log10_duration", "is_live_or_premiere", "title_length", "n_tags"]

# Trong LR, các cột sau là phân loại (one-hot, bỏ mức đầu làm mức tham chiếu); còn lại là số hoặc 0/1
COT_PHAN_LOAI = ("time_slot", "slot_detail", "khung", "ngay", "cat_gop", "duration_group")

# Nhãn khung giờ chi tiết cho LR ngày thường: đặt tên để "hanh_chinh" đứng đầu bảng chữ cái -> làm mức tham chiếu
KHUNG_NGAY_THUONG = {"gio_hanh_chinh": "hanh_chinh", "toi_ngay_thuong (17-24h)": "toi (17-24h)",
                     "dem_sang_ngay_thuong (0-8h)": "sang_som (0-8h)"}


def them_bien(df: pd.DataFrame, danh_muc_giu=DANH_MUC_CHINH) -> pd.DataFrame:
    """Thêm ngay (ngày ra mắt giờ VN), cat_gop (danh mục gộp), log10_duration.

    3 video ra mắt 23:53 ngày 24/09 gộp vào 25/09 (cùng một đêm, quá ít để thành nhóm riêng).
    """
    d = df.copy()
    d["ngay"] = d["release_at_vn"].str[:10].replace({"2026-09-24": "2026-09-25"})
    d["cat_gop"] = np.where(d["category_title"].isin(danh_muc_giu), d["category_title"], "Khác")
    d["log10_duration"] = np.log10(d["duration_s"].clip(lower=1))
    return d


def kiem_tra_cot_cam(cot) -> None:
    """Dừng ngay nếu danh sách feature chứa cột cấm."""
    dinh = sorted(set(cot) & set(COT_CAM))
    if dinh:
        raise ValueError(f"Feature chứa cột lộ nhãn / làm sạch: {dinh}")
