# tests/fixtures/sample_fixture.py
import pytest

@pytest.fixture
def sample_data():
    return {'value': 42, 'text': 'fixture example'}
