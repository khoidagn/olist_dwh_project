import os
from google.cloud import bigquery

# 1. Cấu hình xác thực bằng file JSON vừa tải về
# Thư mục chứa script này (extract_load/)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Root project = thư mục cha của extract_load/
PROJECT_ROOT = os.path.dirname(BASE_DIR)

# Đường dẫn tuyệt đối đến key, dù chạy từ đâu cũng đúng
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(PROJECT_ROOT, "sa_key.json")

# CSV vẫn nằm trong extract_load/archive
csv_folder = os.path.join(BASE_DIR, "archive")

# 2. Khởi tạo BigQuery Client
client = bigquery.Client()

# Điền thông tin Project và Dataset của bạn
project_id = "data-warehouse-group-5"
dataset_id = "raw_layer"



# 3. Tạo danh sách (Dictionary) map giữa tên file CSV và tên Bảng trên BigQuery
# Quy tắc: Tên file CSV : Tên bảng BigQuery (snake_case)
tables_mapping = {
    "olist_orders_dataset.csv": "orders",
    "olist_order_items_dataset.csv": "order_items",
    "olist_customers_dataset.csv": "customers",
    "olist_products_dataset.csv": "products",
    "olist_order_payments_dataset.csv": "order_payments",
    "olist_sellers_dataset.csv": "sellers",
    "olist_order_reviews_dataset.csv": "order_reviews",
    "olist_geolocation_dataset.csv": "geolocation",
    "product_category_name_translation.csv": "category_translations"
}

# 4. Cấu hình Job chạy (Giống hệt các tùy chọn Advanced Options trên UI)
job_config = bigquery.LoadJobConfig(
    source_format=bigquery.SourceFormat.CSV,
    skip_leading_rows=1, # Bỏ qua dòng tiêu đề
    autodetect=True,     # Tự động nhận diện kiểu dữ liệu (Auto detect)
    allow_quoted_newlines=True, # Cho phép xuống dòng trong bảng order_reviews
    max_bad_records=50,         # Bỏ qua tối đa 50 dòng lỗi
    # Ghi đè nếu bảng đã tồn tại (WRITE_TRUNCATE) 
    write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
)

# 5. Vòng lặp đọc và đẩy từng file lên BigQuery
print("Bắt đầu tiến trình Extract & Load lên BigQuery...")

dataset_ref = bigquery.DatasetReference(project_id, dataset_id)
dataset = bigquery.Dataset(dataset_ref)
dataset.location = "asia-southeast1"  
client.create_dataset(dataset, exists_ok=True)

for csv_file, table_name in tables_mapping.items():
    csv_file = os.path.join(csv_folder, csv_file)

    if not os.path.exists(csv_file):
        print(f"⚠️ Không tìm thấy file: {csv_file}")
        continue

    table_id = f"{project_id}.{dataset_id}.{table_name}"
    print(f"Đang tải {csv_file} vào bảng {table_name}...")

    try:
        with open(csv_file, "rb") as source_file:
            job = client.load_table_from_file(
                source_file, table_id, job_config=job_config
            )
        job.result()

        table = client.get_table(table_id)
        print(f"✅ Hoàn tất! Đã nạp {table.num_rows} dòng vào {table_id}\n")

    except Exception as e:
        print(f"❌ Lỗi khi nạp {table_name}: {e}\n")
        continue

print("🎉 Tiến trình ETL hoàn tất 100%!")