# Container RStudio: phân tích khám phá (EDA) bằng R, đọc dữ liệu trực tiếp từ PostgreSQL
# Truy cập: http://localhost:8787 — user "rstudio", mật khẩu = RSTUDIO_PASSWORD trong .env
FROM rocker/tidyverse:4.4.1

# Gói cho Report 3:
#   RPostgres         kết nối PostgreSQL
#   naniar            trực quan giá trị thiếu
#   corrplot          ma trận tương quan
#   scales, patchwork định dạng trục / ghép nhiều biểu đồ
#   binom             khoảng tin cậy Wilson cho tỉ lệ trending
#   knitr, rmarkdown  knit file .Rmd ra HTML
RUN install2.r --error --skipinstalled \
    RPostgres naniar corrplot scales patchwork binom knitr rmarkdown \
    && rm -rf /tmp/downloaded_packages
