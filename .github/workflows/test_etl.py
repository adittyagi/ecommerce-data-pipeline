"""
Unit Tests for ETL Pipeline
"""

import pytest
import pandas as pd
import os

class TestDataFiles:
    """Test data file integrity"""
    
    def test_sales_file_exists(self):
        """Check if sales_data.csv exists"""
        assert os.path.exists('data/sales_data.csv'), "sales_data.csv not found"
    
    def test_products_file_exists(self):
        """Check if products.csv exists"""
        assert os.path.exists('data/products.csv'), "products.csv not found"
    
    def test_customers_file_exists(self):
        """Check if customers.csv exists"""
        assert os.path.exists('data/customers.csv'), "customers.csv not found"


class TestDataQuality:
    """Test data quality"""
    
    def test_sales_not_empty(self):
        """Check sales data has records"""
        df = pd.read_csv('data/sales_data.csv')
        assert len(df) > 0, "Sales data is empty"
    
    def test_sales_has_required_columns(self):
        """Check sales has required columns"""
        df = pd.read_csv('data/sales_data.csv')
        required = ['order_id', 'customer_id', 'product_id']
        for col in required:
            assert col in df.columns, f"Missing column: {col}"
    
    def test_products_has_required_columns(self):
        """Check products has required columns"""
        df = pd.read_csv('data/products.csv')
        required = ['product_id', 'product_name']
        for col in required:
            assert col in df.columns, f"Missing column: {col}"
    
    def test_no_duplicate_order_ids(self):
        """Check no duplicate order IDs"""
        df = pd.read_csv('data/sales_data.csv')
        assert df['order_id'].is_unique, "Duplicate order_ids found"
    
    def test_no_null_order_ids(self):
        """Check no null order IDs"""
        df = pd.read_csv('data/sales_data.csv')
        assert df['order_id'].notna().all(), "Null order_ids found"


class TestDataRelationships:
    """Test data relationships"""
    
    def test_all_products_exist(self):
        """Check all product_ids in sales exist in products"""
        sales = pd.read_csv('data/sales_data.csv')
        products = pd.read_csv('data/products.csv')
        
        sales_products = set(sales['product_id'].unique())
        valid_products = set(products['product_id'].unique())
        
        missing = sales_products - valid_products
        assert len(missing) == 0, f"Missing products: {missing}"
    
    def test_all_customers_exist(self):
        """Check all customer_ids in sales exist in customers"""
        sales = pd.read_csv('data/sales_data.csv')
        customers = pd.read_csv('data/customers.csv')
        
        sales_customers = set(sales['customer_id'].unique())
        valid_customers = set(customers['customer_id'].unique())
        
        missing = sales_customers - valid_customers
        assert len(missing) == 0, f"Missing customers: {missing}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
EOF
