# backend/tests/test_auth.py
"""
Authentication endpoint tests
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

class TestAuthentication:
    """Test authentication endpoints"""
    
    def test_register_company(self):
        """Test company registration"""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "password": "TestPass123!",
                "name": "Test User",
                "company_name": "Test Company",
                "company_cnpj": "12345678901234",
                "company_segment": "retail"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] == "test@example.com"
    
    def test_login(self):
        """Test user login"""
        # First register
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "login@example.com",
                "password": "LoginPass123!",
                "name": "Login User",
                "company_name": "Login Company"
            }
        )
        
        # Then login
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "login@example.com",
                "password": "LoginPass123!"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "wrong@example.com",
                "password": "WrongPass123!"
            }
        )
        assert response.status_code == 401
        assert "Incorrect email or password" in response.json()["detail"]
    
    def test_refresh_token(self):
        """Test token refresh"""
        # Login first
        login_response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "login@example.com",
                "password": "LoginPass123!"
            }
        )
        refresh_token = login_response.json()["refresh_token"]
        
        # Refresh token
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        assert response.status_code == 200
        assert "access_token" in response.json()
    
    def test_verify_token(self):
        """Test token verification"""
        # Login first
        login_response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "login@example.com",
                "password": "LoginPass123!"
            }
        )
        access_token = login_response.json()["access_token"]
        
        # Verify token
        response = client.get(
            "/api/v1/auth/verify",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert response.status_code == 200
        assert response.json()["valid"] == True