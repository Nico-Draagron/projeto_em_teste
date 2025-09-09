# backend/tests/test_sales.py
"""
Sales endpoint tests
"""

import pytest
from fastapi.testclient import TestClient
from datetime import date, datetime
from decimal import Decimal

class TestSalesEndpoints:
    """Test sales data endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self, client, auth_headers):
        self.client = client
        self.headers = auth_headers
    
    def test_create_sales_data(self):
        """Test creating sales data"""
        response = self.client.post(
            "/api/v1/sales",
            json={
                "date": str(date.today()),
                "revenue": "15000.50",
                "quantity": 100,
                "product": "Product A",
                "category": "Category 1",
                "location": "Store 1"
            },
            headers=self.headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["revenue"] == "15000.50"
        assert data["product"] == "Product A"
    
    def test_get_sales_data(self):
        """Test retrieving sales data"""
        response = self.client.get(
            "/api/v1/sales",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_get_sales_summary(self):
        """Test sales summary endpoint"""
        response = self.client.get(
            "/api/v1/sales/summary?days=30",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_revenue" in data
        assert "average_daily_revenue" in data
        assert "transaction_count" in data
    
    def test_update_sales_data(self):
        """Test updating sales data"""
        # First create
        create_response = self.client.post(
            "/api/v1/sales",
            json={
                "date": str(date.today()),
                "revenue": "10000.00",
                "quantity": 50
            },
            headers=self.headers
        )
        sales_id = create_response.json()["id"]
        
        # Then update
        response = self.client.put(
            f"/api/v1/sales/{sales_id}",
            json={
                "revenue": "12000.00",
                "quantity": 60
            },
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["revenue"] == "12000.00"
        assert data["quantity"] == 60
    
    def test_delete_sales_data(self):
        """Test deleting sales data"""
        # First create
        create_response = self.client.post(
            "/api/v1/sales",
            json={
                "date": str(date.today()),
                "revenue": "5000.00"
            },
            headers=self.headers
        )
        sales_id = create_response.json()["id"]
        
        # Then delete
        response = self.client.delete(
            f"/api/v1/sales/{sales_id}",
            headers=self.headers
        )
        assert response.status_code == 200
        
        # Verify deleted
        get_response = self.client.get(
            f"/api/v1/sales/{sales_id}",
            headers=self.headers
        )
        assert get_response.status_code == 404