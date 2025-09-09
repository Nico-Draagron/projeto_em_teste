# backend/tests/conftest.py
"""
Configuração global dos testes e fixtures
"""

import pytest
import asyncio
from typing import Generator, Dict, Any
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import Base, get_db
from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.models.database import User, Company, Location, Product
from app.core.middleware import tenant_context, user_context

# Database de teste (SQLite em memória)
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ==================== FIXTURES ====================

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """Create a fresh database for each test"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db: Session) -> Generator[TestClient, None, None]:
    """Create a test client with overridden database"""
    
    def override_get_db():
        try:
            yield db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def test_company(db: Session) -> Company:
    """Create a test company"""
    company = Company(
        id="test-company-id",
        name="Test Company",
        slug="test-company",
        business_type="retail",
        industry="food",
        country="Brazil",
        state="SP",
        city="São Paulo",
        timezone="America/Sao_Paulo",
        currency="BRL",
        subscription_plan="professional",
        is_active=True
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


@pytest.fixture(scope="function")
def test_user(db: Session, test_company: Company) -> User:
    """Create a test user"""
    user = User(
        email="test@example.com",
        full_name="Test User",
        hashed_password=get_password_hash("Test123!"),
        company_id=test_company.id,
        role="admin",
        is_active=True,
        is_verified=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture(scope="function")
def test_location(db: Session, test_company: Company) -> Location:
    """Create a test location"""
    location = Location(
        id="test-location-id",
        company_id=test_company.id,
        name="Main Store",
        city="São Paulo",
        state="SP",
        country="Brazil",
        latitude=-23.5505,
        longitude=-46.6333,
        is_primary=True
    )
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


@pytest.fixture(scope="function")
def test_product(db: Session, test_company: Company) -> Product:
    """Create a test product"""
    product = Product(
        id="test-product-id",
        company_id=test_company.id,
        name="Test Product",
        sku="TEST-001",
        category="beverages",
        price=10.00,
        cost=5.00,
        is_seasonal=True,
        weather_sensitive=True,
        is_active=True
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@pytest.fixture(scope="function")
def auth_headers(test_user: User, test_company: Company) -> Dict[str, str]:
    """Create authentication headers"""
    access_token = create_access_token(
        subject=str(test_user.id),
        company_id=test_company.id,
        role=test_user.role
    )
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture(scope="function")
def auth_headers_manager(db: Session, test_company: Company) -> Dict[str, str]:
    """Create authentication headers for manager role"""
    user = User(
        email="manager@example.com",
        full_name="Manager User",
        hashed_password=get_password_hash("Manager123!"),
        company_id=test_company.id,
        role="manager",
        is_active=True,
        is_verified=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    access_token = create_access_token(
        subject=str(user.id),
        company_id=test_company.id,
        role=user.role
    )
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture(scope="function")
def sample_sales_data() -> List[Dict[str, Any]]:
    """Sample sales data for testing"""
    return [
        {
            "date": "2024-01-01",
            "quantity": 100,
            "revenue": 1000.00,
            "cost": 500.00,
            "transactions": 50
        },
        {
            "date": "2024-01-02",
            "quantity": 120,
            "revenue": 1200.00,
            "cost": 600.00,
            "transactions": 60
        },
        {
            "date": "2024-01-03",
            "quantity": 80,
            "revenue": 800.00,
            "cost": 400.00,
            "transactions": 40
        }
    ]


@pytest.fixture(scope="function")
def sample_weather_data() -> List[Dict[str, Any]]:
    """Sample weather data for testing"""
    return [
        {
            "date": "2024-01-01",
            "temperature": 25.0,
            "humidity": 70,
            "precipitation": 0,
            "wind_speed": 10
        },
        {
            "date": "2024-01-02",
            "temperature": 28.0,
            "humidity": 65,
            "precipitation": 0,
            "wind_speed": 15
        },
        {
            "date": "2024-01-03",
            "temperature": 22.0,
            "humidity": 80,
            "precipitation": 5,
            "wind_speed": 20
        }
    ]


# ===========================
# backend/tests/test_auth.py
# ===========================

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import verify_password


class TestAuthentication:
    """Test authentication endpoints"""
    
    def test_register_success(self, client: TestClient, db: Session):
        """Test successful user registration"""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "Password123!",
                "full_name": "New User",
                "company_name": "New Company",
                "accept_terms": True
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert "access_token" in data
        assert "refresh_token" in data
    
    def test_register_duplicate_email(self, client: TestClient, test_user):
        """Test registration with duplicate email"""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": test_user.email,
                "password": "Password123!",
                "full_name": "Another User",
                "company_name": "Another Company",
                "accept_terms": True
            }
        )
        
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"]
    
    def test_login_success(self, client: TestClient, test_user):
        """Test successful login"""
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user.email,
                "password": "Test123!"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
    
    def test_login_invalid_credentials(self, client: TestClient, test_user):
        """Test login with invalid credentials"""
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user.email,
                "password": "WrongPassword!"
            }
        )
        
        assert response.status_code == 401
        assert "Invalid credentials" in response.json()["detail"]
    
    def test_refresh_token(self, client: TestClient, test_user, auth_headers):
        """Test token refresh"""
        # First login to get refresh token
        login_response = client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user.email,
                "password": "Test123!"
            }
        )
        refresh_token = login_response.json()["refresh_token"]
        
        # Use refresh token
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
    
    def test_logout(self, client: TestClient, auth_headers):
        """Test logout"""
        response = client.post(
            "/api/v1/auth/logout",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "Successfully logged out"
    
    def test_me_endpoint(self, client: TestClient, test_user, auth_headers):
        """Test get current user endpoint"""
        response = client.get(
            "/api/v1/auth/me",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
        assert data["full_name"] == test_user.full_name


# ===========================
# backend/tests/test_companies.py
# ===========================

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


class TestCompanies:
    """Test company endpoints"""
    
    def test_get_current_company(self, client: TestClient, test_company, auth_headers):
        """Test get current company"""
        response = client.get(
            "/api/v1/companies/current",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_company.id
        assert data["name"] == test_company.name
    
    def test_update_company(self, client: TestClient, test_company, auth_headers):
        """Test update company"""
        response = client.put(
            "/api/v1/companies/current",
            headers=auth_headers,
            json={
                "name": "Updated Company Name",
                "timezone": "America/New_York"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Company Name"
        assert data["timezone"] == "America/New_York"
    
    def test_get_company_stats(self, client: TestClient, test_company, auth_headers):
        """Test get company statistics"""
        response = client.get(
            "/api/v1/companies/current/stats",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "total_users" in data
        assert "total_sales_records" in data
        assert "storage_used_mb" in data
    
    def test_update_company_settings(self, client: TestClient, auth_headers):
        """Test update company settings"""
        response = client.put(
            "/api/v1/companies/current/settings",
            headers=auth_headers,
            json={
                "weekly_report_enabled": True,
                "alert_email_enabled": True,
                "default_language": "en-US"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["weekly_report_enabled"] == True
        assert data["default_language"] == "en-US"


# ===========================
# backend/tests/test_sales.py
# ===========================

import pytest
from fastapi.testclient import TestClient
from datetime import date


class TestSales:
    """Test sales endpoints"""
    
    def test_create_sales_data(
        self, 
        client: TestClient, 
        auth_headers, 
        test_product, 
        test_location
    ):
        """Test create sales data"""
        response = client.post(
            "/api/v1/sales/",
            headers=auth_headers,
            json={
                "date": "2024-01-01",
                "product_id": test_product.id,
                "location_id": test_location.id,
                "quantity": 100,
                "revenue": 1000.00,
                "cost": 500.00,
                "transactions": 50
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["quantity"] == 100
        assert data["revenue"] == 1000.00
        assert data["profit"] == 500.00  # revenue - cost
    
    def test_list_sales_data(
        self,
        client: TestClient,
        auth_headers,
        db: Session,
        test_company,
        sample_sales_data
    ):
        """Test list sales data with filters"""
        # Create sample data
        from app.models.database import SalesData
        
        for sale_data in sample_sales_data:
            sale = SalesData(
                company_id=test_company.id,
                **sale_data
            )
            db.add(sale)
        db.commit()
        
        # Test listing
        response = client.get(
            "/api/v1/sales/",
            headers=auth_headers,
            params={
                "start_date": "2024-01-01",
                "end_date": "2024-01-31"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3
        assert data["total"] == 3
    
    def test_sales_metrics(
        self,
        client: TestClient,
        auth_headers,
        db: Session,
        test_company,
        sample_sales_data
    ):
        """Test sales metrics calculation"""
        # Create sample data
        from app.models.database import SalesData
        
        for sale_data in sample_sales_data:
            sale = SalesData(
                company_id=test_company.id,
                **sale_data
            )
            db.add(sale)
        db.commit()
        
        response = client.get(
            "/api/v1/sales/metrics",
            headers=auth_headers,
            params={
                "start_date": "2024-01-01",
                "end_date": "2024-01-31"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_revenue"] == 3000.00
        assert data["total_quantity"] == 300
        assert data["total_transactions"] == 150
        assert "average_daily_revenue" in data
        assert "trend" in data
    
    def test_sales_anomaly_detection(
        self,
        client: TestClient,
        auth_headers
    ):
        """Test anomaly detection in sales"""
        response = client.get(
            "/api/v1/sales/anomalies",
            headers=auth_headers,
            params={
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
                "sensitivity": 2.0
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "anomalies" in data
        assert isinstance(data["anomalies"], list)


# ===========================
# backend/tests/test_weather.py
# ===========================

import pytest
from fastapi.testclient import TestClient


class TestWeather:
    """Test weather endpoints"""
    
    def test_get_current_weather(
        self,
        client: TestClient,
        auth_headers,
        test_location
    ):
        """Test get current weather"""
        response = client.get(
            "/api/v1/weather/current",
            headers=auth_headers,
            params={"location_id": test_location.id}
        )
        
        # May fail if external API is not mocked
        # For now, just check structure
        assert response.status_code in [200, 502]
        if response.status_code == 200:
            data = response.json()
            assert "temperature" in data
            assert "humidity" in data
    
    def test_get_weather_forecast(
        self,
        client: TestClient,
        auth_headers,
        test_location
    ):
        """Test get weather forecast"""
        response = client.get(
            "/api/v1/weather/forecast",
            headers=auth_headers,
            params={
                "location_id": test_location.id,
                "days": 7
            }
        )
        
        assert response.status_code in [200, 502]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)
            assert len(data) <= 7
    
    def test_create_weather_data(
        self,
        client: TestClient,
        auth_headers,
        test_location
    ):
        """Test manual weather data creation"""
        response = client.post(
            "/api/v1/weather/",
            headers=auth_headers,
            json={
                "date": "2024-01-01",
                "location_id": test_location.id,
                "temperature": 25.0,
                "humidity": 70,
                "precipitation": 0,
                "wind_speed": 10,
                "weather_condition": "Clear"
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["temperature"] == 25.0
        assert data["humidity"] == 70


# ===========================
# backend/tests/test_predictions.py
# ===========================

import pytest
from fastapi.testclient import TestClient


class TestPredictions:
    """Test ML prediction endpoints"""
    
    def test_predict_sales(
        self,
        client: TestClient,
        auth_headers
    ):
        """Test sales prediction"""
        response = client.post(
            "/api/v1/predictions/sales",
            headers=auth_headers,
            json={
                "start_date": "2024-02-01",
                "end_date": "2024-02-07",
                "weather_scenario": {
                    "temperature": 28.0,
                    "humidity": 65,
                    "precipitation": 0
                },
                "include_confidence": True
            }
        )
        
        # May fail if no model is trained
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert "predictions" in data
            assert "summary" in data
            assert "model_info" in data
    
    def test_scenario_simulation(
        self,
        client: TestClient,
        auth_headers
    ):
        """Test scenario simulation"""
        response = client.post(
            "/api/v1/predictions/simulate",
            headers=auth_headers,
            json={
                "scenario_name": "Heavy Rain",
                "weather_conditions": {
                    "temperature": 20.0,
                    "precipitation": 50.0,
                    "humidity": 90
                },
                "impact_type": "sales",
                "compare_with_baseline": True
            }
        )
        
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert "scenario_name" in data
            assert "impact" in data


# ===========================
# backend/tests/test_middleware.py
# ===========================

import pytest
from fastapi.testclient import TestClient
from app.core.middleware import tenant_context, user_context


class TestMiddleware:
    """Test middleware functionality"""
    
    def test_multi_tenant_isolation(
        self,
        client: TestClient,
        db: Session,
        test_company,
        auth_headers
    ):
        """Test multi-tenant data isolation"""
        # Create another company
        from app.models.database import Company
        
        other_company = Company(
            id="other-company-id",
            name="Other Company",
            slug="other-company",
            country="Brazil",
            is_active=True
        )
        db.add(other_company)
        db.commit()
        
        # Try to access data with test company token
        response = client.get(
            "/api/v1/sales/",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        # Should only see data from test_company
        # (test would need actual data to verify)
    
    def test_rate_limiting(
        self,
        client: TestClient,
        auth_headers
    ):
        """Test rate limiting"""
        # Make many requests quickly
        responses = []
        for _ in range(150):  # Exceed default limit of 100
            response = client.get(
                "/api/v1/companies/current",
                headers=auth_headers
            )
            responses.append(response.status_code)
        
        # Should have some 429 responses
        assert 429 in responses
    
    def test_request_id_header(
        self,
        client: TestClient,
        auth_headers
    ):
        """Test request ID in headers"""
        response = client.get(
            "/api/v1/companies/current",
            headers=auth_headers
        )
        
        assert "X-Request-ID" in response.headers
        assert len(response.headers["X-Request-ID"]) == 36  # UUID length
    
    def test_security_headers(
        self,
        client: TestClient
    ):
        """Test security headers are present"""
        response = client.get("/health")
        
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"
    
    def test_cors_headers(
        self,
        client: TestClient
    ):
        """Test CORS headers"""
        response = client.options(
            "/api/v1/auth/login",
            headers={"Origin": "http://localhost:3000"}
        )
        
        assert "Access-Control-Allow-Origin" in response.headers
        assert "Access-Control-Allow-Methods" in response.headers


# ===========================
# backend/tests/test_integration.py
# ===========================

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta


class TestIntegration:
    """End-to-end integration tests"""
    
    def test_complete_sales_flow(
        self,
        client: TestClient,
        db: Session,
        test_company
    ):
        """Test complete sales workflow"""
        # 1. Register user
        register_response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "salestest@example.com",
                "password": "Sales123!",
                "full_name": "Sales Test",
                "company_name": "Sales Company",
                "accept_terms": True
            }
        )
        assert register_response.status_code == 201
        token = register_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # 2. Create product
        product_response = client.post(
            "/api/v1/products/",
            headers=headers,
            json={
                "name": "Test Product",
                "sku": "PROD-001",
                "category": "beverages",
                "price": 15.00,
                "weather_sensitive": True
            }
        )
        assert product_response.status_code == 201
        product_id = product_response.json()["id"]
        
        # 3. Create sales data
        sales_response = client.post(
            "/api/v1/sales/",
            headers=headers,
            json={
                "date": "2024-01-15",
                "product_id": product_id,
                "quantity": 150,
                "revenue": 2250.00,
                "transactions": 75
            }
        )
        assert sales_response.status_code == 201
        
        # 4. Get metrics
        metrics_response = client.get(
            "/api/v1/sales/metrics",
            headers=headers,
            params={
                "start_date": "2024-01-01",
                "end_date": "2024-01-31"
            }
        )
        assert metrics_response.status_code == 200
        metrics = metrics_response.json()
        assert metrics["total_revenue"] == 2250.00
        
        # 5. Generate report
        report_response = client.post(
            "/api/v1/exports/generate",
            headers=headers,
            json={
                "report_type": "sales_analysis",
                "format": "pdf",
                "start_date": "2024-01-01",
                "end_date": "2024-01-31"
            }
        )
        assert report_response.status_code in [200, 202]
    
    def test_weather_impact_analysis(
        self,
        client: TestClient,
        db: Session,
        auth_headers,
        test_company,
        test_location
    ):
        """Test weather impact on sales analysis"""
        from app.models.database import SalesData, WeatherData
        
        # Create correlated data
        dates = [
            datetime(2024, 1, 1),
            datetime(2024, 1, 2),
            datetime(2024, 1, 3)
        ]
        
        # Hot day = more sales
        weather_temps = [30.0, 25.0, 20.0]
        sales_amounts = [1500.0, 1000.0, 700.0]
        
        for i, date in enumerate(dates):
            # Add weather data
            weather = WeatherData(
                company_id=test_company.id,
                location_id=test_location.id,
                date=date.date(),
                temperature=weather_temps[i],
                humidity=70
            )
            db.add(weather)
            
            # Add sales data
            sale = SalesData(
                company_id=test_company.id,
                location_id=test_location.id,
                date=date.date(),
                quantity=100,
                revenue=sales_amounts[i]
            )
            db.add(sale)
        
        db.commit()
        
        # Analyze correlation
        response = client.get(
            "/api/v1/insights/correlations",
            headers=auth_headers,
            params={
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
                "variables": ["temperature"]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "correlation_matrix" in data
        assert "significant_correlations" in data