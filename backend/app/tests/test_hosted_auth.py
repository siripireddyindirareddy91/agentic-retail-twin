"""Security regressions for real hosted authentication."""
import pytest
from fastapi import HTTPException
from app.core.security import hash_password,verify_password

def test_password_byte_limit():
    with pytest.raises(HTTPException) as error:
        hash_password('é'*40)
    assert error.value.status_code==422
    assert verify_password('é'*40,hash_password('SafePassword123!')) is False

def test_password_hash_is_not_plaintext():
    password='SafePassword123!'
    hashed=hash_password(password)
    assert password not in hashed
    assert verify_password(password,hashed)
    assert not verify_password('DifferentPassword123!',hashed)
