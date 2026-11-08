import os
import pandas as pd
from sqlalchemy import create_engine
from google.cloud import bigquery

# 1. Cấu hình xác thực bằng file JSON 
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(PROJECT_ROOT, "sa_key.json")


def load_env(env_path: str) -> None:
    """Đọc file .env đơn giản không cần cài thêm thư viện ngoài"""
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ.setdefault(key.strip(), val.strip().strip("'\""))


# Đọc cấu hình từ .env
load_env(os.path.join(PROJECT_ROOT, ".env"))
load_env(os.path.join(BASE_DIR, ".env"))

# 2. Khai báo chuỗi kết nối từ Neon (lấy theo DATABASE_URL hoặc NEON_DATABASE_URL từ .env)
NEON_DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("NEON_DATABASE_URL")

if not NEON_DATABASE_URL:
    raise ValueError(
        "❌ LỖI: Không tìm thấy DATABASE_URL hoặc NEON_DATABASE_URL trong file .env!\n"
        f"Vui lòng kiểm tra lại file: {os.path.join(PROJECT_ROOT, '.env')}"
    )

# 3. Danh sách các bảng cần đồng bộ từ Neon sang BigQuery (khớp 100% với dbt sources.yml)
table_names = [
    "orders",
    "order_items",
    "customers",
    "products",
    "order_payments",
    "sellers",
    "order_reviews",
    "geolocation",
    "category_name_translation",
]


def main():
    # 2. Khởi tạo BigQuery Client & Dataset
    client = bigquery.Client()
    project_id = "data-warehouse-group-5"
    dataset_id = "raw_layer"

    # Đảm bảo Dataset đã tồn tại
    dataset_ref = bigquery.DatasetReference(project_id, dataset_id)
    dataset = bigquery.Dataset(dataset_ref)
    dataset.location = "asia-southeast1"  
    client.create_dataset(dataset, exists_ok=True)

    engine = create_engine(NEON_DATABASE_URL)

    # 6. Vòng lặp Extract (từ Neon) & Load (lên BigQuery)
    print("Bắt đầu tiến trình ETL: Neon PostgreSQL -> Google BigQuery...")

    for table_name in table_names:
        table_id = f"{project_id}.{dataset_id}.{table_name}"
        print(f"\n--- Đang xử lý bảng: {table_name} ---")
        
        try:
            query = f"SELECT * FROM {table_name}"
            
            # Bảng geolocation có >1 triệu dòng nên dùng chunk lớn hơn (250.000 dòng)
            # để tránh bị BigQuery Rate Limit (quá nhiều thao tác cập nhật bảng liên tiếp)
            chunk_size = 250000 if table_name == "geolocation" else 20000
            chunks = pd.read_sql(query, engine, chunksize=chunk_size)
            
            is_first_chunk = True
            total_loaded = 0
            
            for chunk in chunks:
                chunk_rows = len(chunk)
                total_loaded += chunk_rows
                print(f"  + Đã kéo {total_loaded} dòng từ Neon, đang nạp lên BigQuery...")
                
                # CẤU HÌNH THÔNG MINH: 
                write_mode = bigquery.WriteDisposition.WRITE_TRUNCATE if is_first_chunk else bigquery.WriteDisposition.WRITE_APPEND
                job_config = bigquery.LoadJobConfig(write_disposition=write_mode)
                
                job = client.load_table_from_dataframe(chunk, table_id, job_config=job_config)
                job.result() 
                
                is_first_chunk = False # Tắt cờ first_chunk
                
            # Kiểm tra tổng số dòng sau khi nạp xong toàn bộ chunks
            table = client.get_table(table_id)
            print(f"✅ Hoàn tất bảng {table_name}! Tổng số trên BigQuery: {table.num_rows} dòng.")

        except Exception as e:
            print(f"❌ Lỗi khi xử lý bảng {table_name}: {e}")
            continue

    print("\n🎉 Tiến trình ETL hoàn tất 100%!")


if __name__ == "__main__":
    main()