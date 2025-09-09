# tests/unit/test_user_service.py
from app.services.user_service import UserService

def test_user_service_create(monkeypatch):
    class DummySession:
        def add(self, obj): pass
        def commit(self): pass
    service = UserService(DummySession())
    # Exemplo: ajuste conforme seu método real
    # result = service.create_user(...)
    # assert result is not None
    assert True  # Placeholder
import pytest
from app.services.user_service import UserService

@pytest.fixture
def user_service():
    return UserService()

def test_get_user_by_id_not_found(user_service):
    user = user_service.get_user_by_id(9999)
    assert user is None
