# tests/unit/test_auth_service.py
import pytest
from app.services.auth_service import AuthService

@pytest.fixture
def auth_service():
    return AuthService()

def test_verify_password(auth_service):
    assert auth_service.verify_password('senha', 'senha') is True
    assert auth_service.verify_password('senha', 'outra') is False
