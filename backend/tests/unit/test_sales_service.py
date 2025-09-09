# tests/unit/test_sales_service.py
import pytest
from app.services.sales_service import SalesService

@pytest.fixture
def sales_service():
    return SalesService()

def test_get_sales_empty(sales_service):
    sales = sales_service.get_sales()
    assert sales == []
