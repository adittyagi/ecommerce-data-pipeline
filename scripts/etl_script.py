import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql.functions import col, when, sum, count, avg, round, to_date, year, month, dayofweek
from pyspark.sql.types import DoubleType

# Initialize Glue context
args = getResolvedOptions(sys.argv, ['JOB_NAME', 'RAW_BUCKET', 'PROCESSED_BUCKET'])
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

# Configuration
RAW_BUCKET = args['RAW_BUCKET']
PROCESSED_BUCKET = args['PROCESSED_BUCKET']

print(f"Starting ETL Job...")
print(f"Raw Bucket: {RAW_BUCKET}")
print(f"Processed Bucket: {PROCESSED_BUCKET}")

# ============================================
# EXTRACT: Read data from S3
# ============================================

print("Extracting data from S3...")

# Read Sales Data
sales_df = spark.read \
    .option("header", "true") \
    .option("inferSchema", "true") \
    .csv(f"s3://{RAW_BUCKET}/sales/")

# Read Products Data
products_df = spark.read \
    .option("header", "true") \
    .option("inferSchema", "true") \
    .csv(f"s3://{RAW_BUCKET}/products/")

# Read Customers Data
customers_df = spark.read \
    .option("header", "true") \
    .option("inferSchema", "true") \
    .csv(f"s3://{RAW_BUCKET}/customers/")

print(f"Sales records: {sales_df.count()}")
print(f"Products records: {products_df.count()}")
print(f"Customers records: {customers_df.count()}")

# ============================================
# TRANSFORM: Data processing and enrichment
# ============================================

print("Transforming data...")

# 1. Calculate total amount for each order
sales_enriched = sales_df.withColumn(
    "total_amount",
    round(col("quantity") * col("unit_price"), 2)
)

# 2. Add date components
sales_enriched = sales_enriched \
    .withColumn("order_date", to_date(col("order_date"))) \
    .withColumn("order_year", year(col("order_date"))) \
    .withColumn("order_month", month(col("order_date"))) \
    .withColumn("day_of_week", dayofweek(col("order_date")))

# 3. Join with products to get product details and calculate profit
sales_with_products = sales_enriched.join(
    products_df,
    on="product_id",
    how="left"
)

# Calculate profit
sales_with_products = sales_with_products.withColumn(
    "profit",
    round((col("unit_price") - col("cost_price")) * col("quantity"), 2)
)

# Calculate profit margin
sales_with_products = sales_with_products.withColumn(
    "profit_margin",
    round((col("profit") / col("total_amount")) * 100, 2)
)

# 4. Join with customers to get customer details
fact_sales = sales_with_products.join(
    customers_df,
    on="customer_id",
    how="left"
)

# 5. Add customer lifetime value flag
fact_sales = fact_sales.withColumn(
    "high_value_order",
    when(col("total_amount") >= 100, "Yes").otherwise("No")
)

# Select and reorder columns for the fact table
fact_sales_final = fact_sales.select(
    "order_id",
    "order_date",
    "order_year",
    "order_month",
    "day_of_week",
    "customer_id",
    "first_name",
    "last_name",
    "customer_segment",
    "product_id",
    "product_name",
    "category",
    "brand",
    "quantity",
    "unit_price",
    "cost_price",
    "total_amount",
    "profit",
    "profit_margin",
    "shipping_city",
    "shipping_country",
    "payment_method",
    "high_value_order"
)

print("Fact table schema:")
fact_sales_final.printSchema()

# ============================================
# CREATE AGGREGATED TABLES
# ============================================

# Daily Sales Summary
daily_sales = fact_sales_final.groupBy("order_date") \
    .agg(
        count("order_id").alias("total_orders"),
        sum("quantity").alias("total_items_sold"),
        round(sum("total_amount"), 2).alias("total_revenue"),
        round(sum("profit"), 2).alias("total_profit"),
        round(avg("total_amount"), 2).alias("avg_order_value")
    ) \
    .orderBy("order_date")

# Product Performance
product_performance = fact_sales_final.groupBy("product_id", "product_name", "category", "brand") \
    .agg(
        count("order_id").alias("times_ordered"),
        sum("quantity").alias("total_quantity_sold"),
        round(sum("total_amount"), 2).alias("total_revenue"),
        round(sum("profit"), 2).alias("total_profit"),
        round(avg("profit_margin"), 2).alias("avg_profit_margin")
    ) \
    .orderBy(col("total_revenue").desc())

# Customer Summary
customer_summary = fact_sales_final.groupBy("customer_id", "first_name", "last_name", "customer_segment") \
    .agg(
        count("order_id").alias("total_orders"),
        sum("quantity").alias("total_items_purchased"),
        round(sum("total_amount"), 2).alias("total_spent"),
        round(avg("total_amount"), 2).alias("avg_order_value")
    ) \
    .orderBy(col("total_spent").desc())

# City-wise Sales
city_sales = fact_sales_final.groupBy("shipping_city", "shipping_country") \
    .agg(
        count("order_id").alias("total_orders"),
        round(sum("total_amount"), 2).alias("total_revenue"),
        round(sum("profit"), 2).alias("total_profit")
    ) \
    .orderBy(col("total_revenue").desc())

# Payment Method Analysis
payment_analysis = fact_sales_final.groupBy("payment_method") \
    .agg(
        count("order_id").alias("total_transactions"),
        round(sum("total_amount"), 2).alias("total_amount"),
        round(avg("total_amount"), 2).alias("avg_transaction_value")
    ) \
    .orderBy(col("total_amount").desc())

# ============================================
# LOAD: Write processed data to S3
# ============================================

print("Loading data to S3...")

# Write Fact Table (Parquet format for better performance)
fact_sales_final.write \
    .mode("overwrite") \
    .partitionBy("order_year", "order_month") \
    .parquet(f"s3://{PROCESSED_BUCKET}/fact_sales/")

# Write Aggregated Tables
daily_sales.write \
    .mode("overwrite") \
    .parquet(f"s3://{PROCESSED_BUCKET}/agg_daily_sales/")

product_performance.write \
    .mode("overwrite") \
    .parquet(f"s3://{PROCESSED_BUCKET}/agg_product_performance/")

customer_summary.write \
    .mode("overwrite") \
    .parquet(f"s3://{PROCESSED_BUCKET}/agg_customer_summary/")

city_sales.write \
    .mode("overwrite") \
    .parquet(f"s3://{PROCESSED_BUCKET}/agg_city_sales/")

payment_analysis.write \
    .mode("overwrite") \
    .parquet(f"s3://{PROCESSED_BUCKET}/agg_payment_analysis/")

# Also write fact table as CSV for easy viewing
fact_sales_final.coalesce(1).write \
    .mode("overwrite") \
    .option("header", "true") \
    .csv(f"s3://{PROCESSED_BUCKET}/fact_sales_csv/")

print("ETL Job completed successfully!")

# Job completion
job.commit()