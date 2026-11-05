import os, secrets, hashlib, time
from collections import defaultdict, deque
from pathlib import Path
from datetime import datetime, timedelta, timezone
import bcrypt, jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models import User

DEMO = os.getenv('DEMO_MODE', 'true').lower() == 'true'
secret = os.getenv('JWT_SECRET')
if not secret:
    if os.getenv('VERCEL'):
        raise RuntimeError('JWT_SECRET must be configured for hosted deployments')
    if not DEMO:
        raise RuntimeError('JWT_SECRET must be configured outside demo mode')
    path = Path('.jwt-secret')
    if not path.exists():
        path.write_text(secrets.token_hex(48))
    secret = path.read_text().strip()
bearer = HTTPBearer(auto_error=False)
buckets = defaultdict(deque)
def limit(request: Request, scope: str, maximum=15):
    key = (request.client.host if request.client else 'local', scope)
    q = buckets[key]
    while q and q[0] < time.time() - 60:
        q.popleft()
    if len(q) >= maximum:
        raise HTTPException(429, 'Too many attempts. Try again in a minute.')
    q.append(time.time())
def hash_password(password):
    if len(password.encode()) > 72:
        raise HTTPException(422, 'Password must be at most 72 UTF-8 bytes')
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
def verify_password(password, hashed):
    if len(password.encode()) > 72:
        return False
    return bcrypt.checkpw(password.encode(), hashed.encode())
def token(user):
    return jwt.encode({'sub': user.id, 'version': user.session_version, 'exp': datetime.now(timezone.utc) + timedelta(minutes=int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', '60')))}, secret, algorithm='HS256')
def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)):
    if not credentials:
        raise HTTPException(401, 'Please sign in')
    try:
        claims = jwt.decode(credentials.credentials, secret, algorithms=['HS256'])
        user = db.get(User, claims['sub'])
        if not user or user.session_version != claims.get('version'):
            raise ValueError()
        return user
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(401, 'Session expired. Please sign in again.')
def writer(user=Depends(current_user)):
    if user.role_id == 'analyst':
        raise HTTPException(403, 'This action requires a management role')
    return user
def approver(user=Depends(current_user)):
    if user.role_id not in ['admin', 'supply-chain-manager']:
        raise HTTPException(403, 'Approval requires an administrator or supply chain manager')
    return user
def admin(user=Depends(current_user)):
    if user.role_id != 'admin':
        raise HTTPException(403, 'Administrator access required')
    return user
