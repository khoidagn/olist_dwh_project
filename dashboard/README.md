# Dashboard Olist Commerce Intelligence

Ứng dụng Streamlit đọc các bảng marts trên Google BigQuery (do dbt trong thư mục `olist_dbt` dựng) để phân tích doanh số, khách hàng và hỗ trợ quyết định chiến dịch giữ chân khách hàng cho bộ dữ liệu Olist.

## Yêu cầu

- Python 3.11 trở lên.
- File key của service account có quyền đọc dataset trên BigQuery (`BigQuery Data Viewer` và `BigQuery Job User`).
- Các bảng marts đã được tạo bằng `dbt run` trong thư mục `olist_dbt`.

## Cấu trúc thư mục

```
dashboard/
  Home.py                  Điểm vào, khai báo các trang và bảng đo hiệu năng
  requirements.txt
  .streamlit/
    config.toml            Giao diện (theme)
    secrets.toml.example   Mẫu cấu hình kết nối BigQuery
    secrets.toml           Cấu hình thật, không commit
  utils/
    bigquery.py            Kết nối, cache, chạy truy vấn song song
    queries.py             Toàn bộ câu SQL của các trang
    filters.py             Bộ lọc ở sidebar
    campaign.py            Mô hình tính của trang Chiến dịch giữ chân
    charts.py, theme.py, layout.py   Định dạng số, biểu đồ, bố cục
  views/
    overview.py            Tổng quan
    trends_geo.py          Xu hướng và địa lý
    rfm.py                 Phân khúc RFM
    churn.py               Churn và giữ chân
    decision.py            Chiến dịch giữ chân (DSS)
  tests/
    e2e_check.py           Kiểm thử từ dữ liệu gốc đến giao diện
```

## Cài đặt

Chạy trong thư mục `dashboard`.

Windows (PowerShell):

```
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS hoặc Linux:

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Cấu hình kết nối

1. Sao chép `.streamlit/secrets.toml.example` thành `.streamlit/secrets.toml`.
2. Điền các giá trị

- `dataset`: dataset chứa các bảng marts do dbt tạo.
- `location`: vùng của dataset, xem ở tab Details của dataset trên BigQuery.
- `key_path`: đường dẫn tới file key, tính từ thư mục `dashboard`. Ví dụ trên ứng với file `sa_key.json` đặt ở thư mục gốc của repo.

`secrets.toml` và `sa_key.json` đã nằm trong `.gitignore`. Không commit hai file này và không gửi file key qua kênh công khai.

## Chạy ứng dụng

```
cd dashboard
streamlit run Home.py
```

Trình duyệt mở tại `http://localhost:8501`. Luôn chạy lệnh từ thư mục `dashboard`, vì code import theo dạng `from utils...`.

## Các trang

| Nhóm | Trang | Nội dung chính | Bảng sử dụng |
|---|---|---|---|
| Kinh doanh | Tổng quan | KPI doanh thu, số đơn, AOV, phí ship, số khách so với kỳ liền trước; doanh thu theo tháng; danh mục; phương thức thanh toán; top 10 sản phẩm | `fct_order_items_sales`, `dim_time`, `dim_customers`, `dim_products`, `dim_payments` |
| Kinh doanh | Xu hướng và địa lý | Xu hướng theo tháng hoặc quý, so sánh cùng kỳ, giờ và thứ đặt hàng, xếp hạng bang theo doanh thu, AOV, phí ship, giao trễ; top thành phố | `fct_order_items_sales`, `dim_time`, `dim_customers`, `dim_products` |
| Khách hàng | Phân khúc RFM | Quy mô 7 phân khúc, tỷ trọng khách so với doanh thu, ma trận R và F, hồ sơ và hành động đề xuất, danh sách khách theo phân khúc | `fct_customer_rfm`, `dim_customers` |
| Khách hàng | Churn và giữ chân | Tỷ lệ churn, phân bố số ngày từ lần mua cuối, churn theo bang và theo danh mục mua cuối, danh sách khách sắp rời bỏ | `fct_customer_rfm`, `dim_customers`, `dim_products`, `fct_order_items_sales` |
| Ra quyết định | Chiến dịch giữ chân | Nhận diện nhóm khách sắp rời bỏ, thiết kế và so sánh 3 phương án, điểm hòa vốn, đường nhạy cảm lợi nhuận, danh sách khách mục tiêu | `fct_customer_rfm`, `dim_customers` |

Bộ lọc ngày và danh mục chỉ áp dụng cho nhóm Kinh doanh. Các trang Khách hàng và Ra quyết định tính trên toàn bộ lịch sử mua và chỉ dùng bộ lọc bang.

Định nghĩa dùng chung:

- Đơn hợp lệ: loại trạng thái `canceled` và `unavailable`.
- Doanh thu: tổng `price + freight_value`.
- Churn: khách có recency lớn hơn 180 ngày. Sắp rời bỏ: recency từ 91 đến 180 ngày.
- Ngày mốc tính recency: ngày mua cuối cùng trong dữ liệu cộng 1 ngày.

## Hiệu năng và cache

Ứng dụng có ba tầng cache:

1. `st.cache_resource` giữ một BigQuery client cho cả ứng dụng.
2. `st.cache_data` lưu kết quả truy vấn trong 12 giờ, theo câu SQL và tham số bộ lọc.
3. Cache kết quả 24 giờ của BigQuery cho các truy vấn giống hệt nhau.

Các truy vấn của một trang được gom thành một nhóm và chạy đồng thời bằng nhiều luồng, mỗi luồng gọi `client.query_and_wait()`.

Mục "Hiệu năng và cache" ở cuối sidebar có:

- Hiện bảng thông số: thời gian, số truy vấn, nguồn dữ liệu và dung lượng quét của từng nhóm truy vấn.
- Chạy truy vấn song song: tắt để so sánh với cách chạy lần lượt.
- Dùng cache của BigQuery: tắt để đo trường hợp BigQuery phải chạy lại.
- Xóa cache Streamlit: bấm khi đang ở trang cần đo, hoặc sau mỗi lần chạy lại dbt để thấy dữ liệu mới.

## Kiểm thử

```
cd dashboard
python tests/e2e_check.py
```

Script kiểm tra:

- Dữ liệu gốc sang kho: số dòng và tổng tiền của bảng fact khớp với `raw_layer`, không trùng khóa, số khách khớp.
- Kho sang dashboard: KPI doanh thu, số đơn, phí ship, số khách khớp với số tính trực tiếp từ dữ liệu gốc; tổng theo tháng, quý, danh mục, bang, phương thức thanh toán khớp với KPI.
- RFM, Churn, DSS: recency, frequency, cờ churn và phân khúc của từng khách khớp với tính lại từ dữ liệu gốc; số khách giữa các trang khớp nhau.
- Giao diện: mở lần lượt 5 trang và báo lỗi nếu có.

Kết quả đạt khi dòng cuối báo `0 lỗi`. Các dòng cảnh báo `missing ScriptRunContext` khi chạy script là bình thường.

## Quy trình khi dữ liệu thay đổi

1. Trong `olist_dbt`: `dbt run`, sau đó `dbt test`.
2. Trong `dashboard`: `python tests/e2e_check.py`.
3. Mở ứng dụng, bấm "Xóa cache Streamlit".

## Xử lý sự cố

| Hiện tượng | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| "Không truy vấn được BigQuery." | Sai `key_path`, key không có quyền, sai `location` hoặc `dataset` | Mở "Chi tiết lỗi" trên trang, kiểm tra lại `secrets.toml` |
| `ModuleNotFoundError: No module named 'utils'` hoặc `'dashboard'` | Chạy lệnh ngoài thư mục `dashboard`, hoặc IDE tự thêm import `from dashboard.utils...` | Chạy từ thư mục `dashboard`, sửa import thành `from utils...` |
| Số liệu chưa cập nhật sau khi chạy dbt | Kết quả cũ còn trong cache Streamlit | Bấm "Xóa cache Streamlit" |
| Giao diện không đổi sau khi sửa `config.toml` | Theme chỉ được nạp khi khởi động | Dừng ứng dụng (Ctrl+C) và chạy lại |
| `Port 8501 is already in use` | Một phiên Streamlit khác đang chạy | Tắt phiên cũ hoặc chạy `streamlit run Home.py --server.port 8502` |

## Giới hạn

- Khoảng 97% khách chỉ mua một lần, nên churn chủ yếu phản ánh thời điểm khách mua lần đầu.
- Trang Chiến dịch giữ chân dùng các giả định do người dùng nhập (biên lợi nhuận, tỷ lệ tiếp cận, tỷ lệ mua thêm, chi phí liên hệ) vì dữ liệu Olist không có các thông tin này.
- Ứng dụng hiện chạy cục bộ, chưa triển khai lên máy chủ.
