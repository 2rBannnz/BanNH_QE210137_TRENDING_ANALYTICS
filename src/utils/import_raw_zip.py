"""Đưa raw của thành viên khác (file zip tải từ Drive) lên MinIO, giữ nguyên từng byte.

Mỗi thành viên crawl một khu vực trên máy riêng (MinIO riêng), rồi nén thư mục raw/ gửi lại.
Script này chép các object raw/youtube/... trong zip vào bucket chung để cleaner nạp như dữ liệu VN.

Chạy từ thư mục gốc repo:
    python -m src.utils.import_raw_zip <file.zip> [<file.zip> ...]
    python -m src.utils.import_raw_zip <file.zip> --dry-run      # chỉ kiểm tra, không ghi

Quy tắc:
  - chỉ nhận entry khớp quy ước tên tầng raw (raw/youtube/<job>/dt=<ngày>/<crawler>_<HHMMSS>_pNN.json);
    bỏ raw/sample/ (file mẫu của repo bị nén kèm) và mọi thứ khác
  - crawler phải có trong crawler_regions (configs/db_config.json), nếu không thì dừng trước khi ghi
  - object đã có trên MinIO thì bỏ qua (không ghi đè dữ liệu đã nạp)
"""
import argparse
import io
import logging
import zipfile
from concurrent.futures import ThreadPoolExecutor

from src.processing.cleaner import CRAWLER_REGIONS, parse_key
from src.utils.minio_client import MinioStorage

logger = logging.getLogger(__name__)


def plan_entries(paths):
    """Liệt kê (zip, tên entry) hợp lệ trong các file zip; trả thêm số entry bị bỏ và crawler lạ."""
    entries, ignored, unknown = [], 0, set()
    for path in paths:
        archive = zipfile.ZipFile(path)
        for name in archive.namelist():
            meta = parse_key(name)
            if meta is None:
                ignored += 1  # thư mục, raw/sample/, file không theo quy ước
                continue
            if meta["region_code"] is None:
                unknown.add(meta["crawler_id"])
            entries.append((archive, name))
    return entries, ignored, unknown


def main():
    parser = argparse.ArgumentParser(description="Chép raw JSON trong file zip lên MinIO")
    parser.add_argument("zips", nargs="+")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ kiểm tra, không ghi lên MinIO")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    entries, ignored, unknown = plan_entries(args.zips)
    if unknown:
        raise SystemExit(f"Crawler chưa khai báo trong crawler_regions (configs/db_config.json): {sorted(unknown)}")
    regions = {}
    for _, name in entries:
        region = CRAWLER_REGIONS[parse_key(name)["crawler_id"]]
        regions[region] = regions.get(region, 0) + 1
    logger.info("%d file hợp lệ theo khu vực %s, bỏ %d entry khác", len(entries), regions, ignored)

    storage = MinioStorage()
    storage.ensure_bucket()
    existing = set(storage.list_keys("raw/youtube/"))
    todo = [(archive, name) for archive, name in entries if name not in existing]
    logger.info("Đã có trên MinIO: %d, cần chép: %d", len(entries) - len(todo), len(todo))
    if args.dry_run:
        return

    def upload(item):
        name, body = item
        storage.client.put_object(storage.bucket, name, io.BytesIO(body), length=len(body),
                                  content_type="application/json; charset=utf-8")

    # ZipFile không an toàn khi nhiều luồng cùng đọc: đọc tuần tự theo lô, chỉ phần ghi chạy song song
    with ThreadPoolExecutor(max_workers=8) as pool:
        for start in range(0, len(todo), 500):
            chunk = [(name, archive.read(name)) for archive, name in todo[start:start + 500]]  # byte nguyên văn
            list(pool.map(upload, chunk))
            logger.info("Đã chép %d/%d", start + len(chunk), len(todo))
    logger.info("Xong: chép %d file lên bucket %s", len(todo), storage.bucket)


if __name__ == "__main__":
    main()
