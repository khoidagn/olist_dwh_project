# Extract and Load: BigQuery

This folder contains the extract and load step for the Olist data warehouse project. The `etl_script.py` script reads the Olist CSV files from `archive/` and loads them into Google BigQuery.

## Prerequisites

- Python 3.9 or later
- A Google Cloud project with BigQuery enabled
- A service-account key with permission to create datasets and load data into BigQuery
- The Google Cloud project ID `data-warehouse-group-5`

Install the Python dependency:

```bash
pip install google-cloud-bigquery
```

Using a virtual environment is recommended:

```bash
python -m venv .venv
source .venv/bin/activate
pip install google-cloud-bigquery
```

## Project Structure

The script expects the following files:

```text
olist_dwh_project/
├── sa_key.json
└── extract_load/
	├── etl_script.py
	└── archive/
		├── olist_customers_dataset.csv
		├── olist_geolocation_dataset.csv
		├── olist_order_items_dataset.csv
		├── olist_order_payments_dataset.csv
		├── olist_order_reviews_dataset.csv
		├── olist_orders_dataset.csv
		├── olist_products_dataset.csv
		├── olist_sellers_dataset.csv
		└── product_category_name_translation.csv
```

Place the downloaded service-account key at the project root as `sa_key.json`. The script resolves this path relative to itself, so it can be run from any working directory.

Do not commit `sa_key.json` to version control. Add it to `.gitignore` if it is not already ignored.

## BigQuery Destination

The script creates the dataset when it does not already exist:

```text
Project:  data-warehouse-group-5
Dataset:  raw_layer
Location: asia-southeast1
```

Each CSV is loaded into the following table:

| CSV file | BigQuery table |
| --- | --- |
| `olist_orders_dataset.csv` | `orders` |
| `olist_order_items_dataset.csv` | `order_items` |
| `olist_customers_dataset.csv` | `customers` |
| `olist_products_dataset.csv` | `products` |
| `olist_order_payments_dataset.csv` | `order_payments` |
| `olist_sellers_dataset.csv` | `sellers` |
| `olist_order_reviews_dataset.csv` | `order_reviews` |
| `olist_geolocation_dataset.csv` | `geolocation` |
| `product_category_name_translation.csv` | `category_translations` |

The fully qualified table names use this format:

```text
data-warehouse-group-5.raw_layer.<table_name>
```

## Run the Load

From the project root, run:

```bash
python extract_load/etl_script.py
```

The script will:

1. Create the `raw_layer` dataset if necessary.
2. Check each expected CSV file.
3. Load each available file using BigQuery schema autodetection.
4. Replace the corresponding table because the load uses `WRITE_TRUNCATE`.
5. Print the number of loaded rows for each table.

Missing files are skipped. Load errors are printed and do not stop the script from attempting the remaining files.

## Load Configuration

The BigQuery load job is configured to:

- Treat the first row as a header.
- Autodetect the table schema.
- Allow quoted newlines, which supports multiline review text.
- Ignore up to 50 invalid records.
- Replace existing destination tables on every run.

Because existing tables are replaced, run the script again whenever the raw CSV data needs to be refreshed, and verify the printed row counts after loading.

## Troubleshooting

### Authentication errors

Check that `sa_key.json` exists at the project root, belongs to the intended Google Cloud project, and that its service account has the required BigQuery permissions.

### Dataset or table location errors

The dataset is created in `asia-southeast1`. BigQuery resources used by the load job must be in a compatible location.

### File not found messages

Confirm that the CSV filename matches the mapping above and that the file is located in `extract_load/archive/`.
