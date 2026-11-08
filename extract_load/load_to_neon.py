import os
import pandas as pd
from sqlalchemy import create_engine

# 1. Đường dẫn thư mục và đọc cấu hình từ .env
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
csv_folder = os.path.join(BASE_DIR, "archive")


def load_env(env_path: str) -> None:
    """Đọc file .env đơn giản không cần cài thêm thư viện ngoài"""
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ.setdefault(key.strip(), val.strip().strip("'\""))


# Đọc cấu hình từ .env tại project root
load_env(os.path.join(PROJECT_ROOT, ".env"))
load_env(os.path.join(BASE_DIR, ".env"))

# 2. Khai báo chuỗi kết nối từ Neon (lấy theo DATABASE_URL hoặc NEON_DATABASE_URL từ .env)
NEON_DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("NEON_DATABASE_URL")

if not NEON_DATABASE_URL:
    raise ValueError(
        "❌ LỖI: Không tìm thấy DATABASE_URL hoặc NEON_DATABASE_URL trong file .env!\n"
        f"Vui lòng kiểm tra lại file: {os.path.join(PROJECT_ROOT, '.env')}"
    )

# 3. Ánh xạ chính xác tên file CSV sang tên bảng để khớp 100% với BigQuery raw_layer và dbt sources.yml
tables_mapping = {
    "olist_orders_dataset.csv": "orders",
    "olist_order_items_dataset.csv": "order_items",
    "olist_customers_dataset.csv": "customers",
    "olist_products_dataset.csv": "products",
    "olist_order_payments_dataset.csv": "order_payments",
    "olist_sellers_dataset.csv": "sellers",
    "olist_order_reviews_dataset.csv": "order_reviews",
    "olist_geolocation_dataset.csv": "geolocation",
    # Đổi thành category_name_translation để khớp chính xác với dbt models và sources.yml
    "product_category_name_translation.csv": "category_name_translation",
}


def main():
    print("Bắt đầu nạp dữ liệu từ thư mục archive lên Neon PostgreSQL...")
    engine = create_engine(NEON_DATABASE_URL)

    for csv_file, table_name in tables_mapping.items():
        file_path = os.path.join(csv_folder, csv_file)

        if os.path.exists(file_path):
            print(f"\nĐang xử lý và nạp {csv_file} vào bảng {table_name}...")
            df = pd.read_csv(file_path)

            # Xử lý tương thích schema đặc thù cho BigQuery và dbt
            if table_name == "category_name_translation":
                # Đổi tên cột thành string_field_0, string_field_1 để khớp 100% với schema hiện tại trên BigQuery
                # và logic trong olist_dbt/models/intermediate/int_products_enriched.sql
                df = df.rename(
                    columns={
                        "product_category_name": "string_field_0",
                        "product_category_name_english": "string_field_1",
                    }
                )

            # Nạp dữ liệu vào PostgreSQL (không lưu cột index để tránh sinh thêm cột lạ vào BigQuery)
            df.to_sql(table_name, engine, if_exists="replace", index=False, chunksize=10000)
            print(f"✅ Hoàn tất bảng {table_name} ({len(df):,} dòng, các cột: {list(df.columns)})")
        else:
            print(f"❌ LỖI: Không tìm thấy file. Đường dẫn tìm kiếm: {os.path.abspath(file_path)}")

    print("\n🎉 Toàn bộ dữ liệu OLTP đã nằm trên Neon với schema chuẩn hóa cho BigQuery!")


if __name__ == "__main__":
    main()

