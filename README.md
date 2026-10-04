# 🛒 Olist Commerce Intelligence — Data Warehouse & Decision Support System

Hệ thống Data Warehouse phân tích dữ liệu thương mại điện tử Olist (Brazil) theo mô hình Modern Data Stack, kết hợp giữa **Google BigQuery**, **dbt Core** và **Streamlit**. Dự án cung cấp bức tranh toàn diện về doanh thu, phân khúc khách hàng (RFM) và công cụ hỗ trợ ra quyết định (DSS) cho các chiến dịch giữ chân khách hàng.

---

## 🏛️ Kiến trúc Tổng thể (End-to-End Pipeline)

```text
[Kaggle CSV Dataset]
        │
        ▼ (Extract & Load)
[Python Pipeline: extract_load/] ──> Google BigQuery (Raw Layer)
        │
        ▼ (Transform & Modeling)
[dbt Core: olist_dbt/]
  ├── Staging Layer       : Làm sạch, chuẩn hóa kiểu dữ liệu
  ├── Intermediate Layer  : Tính toán điểm số RFM & hành vi khách hàng
  └── Marts (Star Schema) : fct_order_items_sales, fct_customer_rfm, dim_products...
        │
        ▼ (Serving / Business Intelligence)
[Streamlit Application: dashboard/]
  ├── 1. Tổng quan kinh doanh : Phân tích GMV, đơn hàng, danh mục bán chạy
  ├── 2. Xu hướng & Địa lý    : Biểu đồ đơn hàng theo bang & khung giờ
  ├── 3. Phân khúc RFM        : Ma trận Recency, Frequency, Monetary
  ├── 4. Churn & Giữ chân     : Cảnh báo khách hàng quá 90-180 ngày chưa quay lại
  └── 5. Ra quyết định (DSS)  : Ước lượng ROI và ngân sách chiến dịch
```

## 🚀 Hướng dẫn Cài đặt & Chạy Local

### 1. Chuẩn bị môi trường

Yêu cầu: **Python 3.10+** và hệ điều hành **Ubuntu/Linux** hoặc **macOS**.

```bash
# Clone repository
git clone https://github.com/khoidagn/olist_dwh_project.git
cd olist_dwh_project

# Khởi tạo và kích hoạt virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Cài đặt thư viện phụ thuộc
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Cấu hình bảo mật & Credentials

Đặt file khóa Service Account Google Cloud vào thư mục gốc:
```bash
sa_key.json
```

Đảm bảo Service Account có quyền BigQuery Admin.

Thiết lập cấu hình kết nối Streamlit:
```bash
cp dashboard/.streamlit/secrets.toml.example dashboard/.streamlit/secrets.toml
```
Cập nhật *project_id* và đường dẫn file key bên trong secrets.toml.

Lưu ý: Không commit *sa_key.json* và *secrets.toml* lên GitHub.

### 3. Vận hành Transformation với dbt
```bash
cd olist_dbt

# Kiểm tra kết nối tới BigQuery
dbt debug --profiles-dir .

# Chạy mô hình hóa dữ liệu
dbt run --profiles-dir .

# Chạy data tests
dbt test --profiles-dir .

cd ..
```

### 4. Khởi chạy Dashboard
```bash
cd dashboard
streamlit run Home.py
```
Truy cập ứng dụng tại:
```bash
http://localhost:8501
```
## 🔄 Tự động hóa Pipeline (CI/CD)

Dự án tích hợp GitHub Actions (**.github/workflows/data_pipeline.yml**) để tự động hóa Data Pipeline:

- Scheduled Run: Chạy định kỳ vào 02:00 AM (UTC+7) để tái tính toán các bảng marts.
- Data Quality Gate: Tự động kích hoạt dbt test để kiểm tra tính toàn vẹn dữ liệu (not null, unique, relationships) trước khi chấp nhận dữ liệu mới.
- Manual Trigger: Hỗ trợ kích hoạt thủ công thông qua giao diện GitHub Actions bằng workflow_dispatch.