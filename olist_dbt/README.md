# 🏗️ Olist dbt Transformation Layer

Thư mục này chứa toàn bộ dự án **dbt Core (với adapter `dbt-bigquery`)** dùng để thực hiện chuyển đổi, mô hình hóa dữ liệu (Transform) và kiểm thử chất lượng dữ liệu (Data Quality Tests) trên Google BigQuery cho hệ thống Olist Data Warehouse.

---

## 🏛️ Kiến trúc Mô hình hóa (Data Modeling Architecture)

Dự án tuân theo chuẩn phân tầng của dbt và mô hình **Star Schema**:

```text
Google BigQuery: raw_layer (đồng bộ từ Neon PostgreSQL)
                     │
                     ▼
       ┌───────────────────────────┐
       │      Staging Layer        │  materialized = 'view'
       │  (Làm sạch, ép kiểu chuẩn)│
       └─────────────┬─────────────┘
                     │
                     ▼
       ┌───────────────────────────┐
       │    Intermediate Layer     │  materialized = 'view'
       │  (Khử trùng, ghép nối)    │
       └─────────────┬─────────────┘
                     │
                     ▼
       ┌───────────────────────────┐
       │        Marts Layer        │  materialized = 'table' (Star Schema)
       │  (Facts & Dimensions BI)  │
       └───────────────────────────┘
```

### Chi tiết các tầng:

1. **Staging Layer (`models/staging/`)**
   - Đọc trực tiếp từ nguồn `olist_raw` (dataset `raw_layer` trên BigQuery) khai báo trong [`sources.yml`](file:///home/nhan/Documents/Semester_7/Datawarehouse/olist_dwh_project/olist_dbt/models/staging/sources.yml).
   - Chuẩn hóa kiểu dữ liệu (`timestamp`, `numeric`, `int64`, `string`), xử lý tên cột và giá trị chuỗi (`trim`, `lower`, `upper`).
   - Các bảng: `stg_orders`, `stg_order_items`, `stg_customers`, `stg_products`, `stg_order_payments`, `stg_sellers`.

2. **Intermediate Layer (`models/intermediate/`)**
   - Xử lý các phép biến đổi trung gian phức tạp trước khi đưa vào Marts:
     - `int_customers_deduplicated`: Khử trùng lặp khách hàng dựa trên `customer_unique_id`.
     - `int_order_payments_aggregated`: Tổng hợp giá trị và phương thức thanh toán chính theo từng `order_id`.
     - `int_products_enriched`: Ghép nối sản phẩm với từ điển dịch danh mục tiếng Anh từ `category_name_translation`.

3. **Marts Layer (`models/marts/`)**
   - Được lưu trữ dưới dạng **Physical Table** trên BigQuery (dataset `olist_marts`) để tối ưu tốc độ truy vấn cho Streamlit Dashboard.
   - **Fact Tables:**
     - `fct_order_items_sales`: Đo lường doanh số, số lượng, phí vận chuyển ở mức chi tiết từng mặt hàng.
     - `fct_customer_rfm`: Tính toán điểm Recency, Frequency, Monetary, phân nhóm khách hàng và phát hiện nguy cơ rời bỏ (`is_churn`).
   - **Dimension Tables:**
     - `dim_customers`, `dim_products`, `dim_sellers`, `dim_payments`, `dim_time`.

---

## ⚙️ Thiết lập Môi trường & Cấu hình Kết nối

### 1. Chuẩn bị file khóa Service Account (GCP)
Đảm bảo file khóa Service Account Google Cloud đã được đặt tại thư mục gốc của dự án:
```text
olist_dwh_project/sa_key.json
```
Service Account cần có quyền **BigQuery Admin** hoặc **BigQuery Data Editor** + **BigQuery Job User**.

### 2. Thiết lập biến môi trường
Trước khi chạy nạp dữ liệu và dbt, hãy sao chép tệp mẫu môi trường tại thư mục gốc:
```bash
# Từ thư mục gốc dự án:
cp .env.example .env
```
Cập nhật chuỗi kết nối Neon PostgreSQL trong `.env`:
```ini
DATABASE_URL=postgresql://<username>:<password>@<neon_host>.neon.tech/neondb?sslmode=require&channel_binding=require
GCP_PROJECT_ID=data-warehouse-group-5
GCP_KEYFILE=sa_key.json
```

---

## 🚀 Hướng dẫn Vận hành dbt

Di chuyển vào thư mục `olist_dbt`:
```bash
cd olist_dbt
```

### 1. Kiểm tra kết nối tới BigQuery
```bash
dbt debug --profiles-dir .
```
Nếu toàn bộ các mục báo `PASS` (Connection test, Profile validation), hệ thống đã sẵn sàng.

### 2. Chạy chuyển đổi dữ liệu (Build Models)
```bash
# Chạy toàn bộ các tầng (Staging -> Intermediate -> Marts)
dbt run --profiles-dir .

# Hoặc chạy riêng từng tầng khi cần thiết:
dbt run --profiles-dir . --select staging
dbt run --profiles-dir . --select intermediate
dbt run --profiles-dir . --select marts

# Chạy một model cụ thể (ví dụ bảng RFM):
dbt run --profiles-dir . --select fct_customer_rfm
```

### 3. Kiểm tra chất lượng dữ liệu (Data Tests)
Dự án được định nghĩa các bài kiểm tra toàn vẹn trong [`models/marts/schema.yml`](file:///home/nhan/Documents/Semester_7/Datawarehouse/olist_dwh_project/olist_dbt/models/marts/schema.yml):
```bash
dbt test --profiles-dir .
```
Các bài kiểm tra bao gồm:
- **`unique` & `not_null`**: Kiểm tra tính duy nhất và không rỗng của các khóa chính (`customer_unique_id`, `product_id`, `seller_id`, `date_key`, `order_id`...).
- **`relationships`**: Kiểm tra tính toàn vẹn tham chiếu khóa ngoại giữa Fact và Dimension.
- **`accepted_values`**: Kiểm tra các trạng thái đơn hàng hợp lệ (`delivered`, `shipped`, `canceled`...).

### 4. Sinh tài liệu và Sơ đồ quan hệ (Lineage Graph)
```bash
# Sinh metadata và catalog tài liệu
dbt docs generate --profiles-dir .

# Mở giao diện xem sơ đồ luồng dữ liệu (Lineage DAG)
dbt docs serve
```

---

## 🔄 Luồng Vận hành Chuẩn (End-to-End Run)

Khi có dữ liệu mới hoặc muốn nạp lại từ đầu:

```bash
# Bước 1: Nạp CSV lên Neon OLTP
python extract_load/load_to_neon.py

# Bước 2: Đồng bộ từ Neon sang BigQuery raw_layer
python extract_load/etl_script.py

# Bước 3: Chạy dbt để biến đổi dữ liệu sang Star Schema
cd olist_dbt
dbt run --profiles-dir .
dbt test --profiles-dir .
cd ..

# Bước 4: Khởi chạy Streamlit Dashboard
cd dashboard
streamlit run Home.py
```
