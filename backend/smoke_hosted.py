"""Read-only production smoke checks plus one isolated disposable QA account.

Run from repository root. Uses the ignored .env.local only to remove its own
temporary account; it never resets or modifies operational demonstration data.
"""
import os,uuid,time
import httpx
from dotenv import load_dotenv

def main():
    base=os.getenv('SMOKE_BASE_URL','https://supplytwin-ai.vercel.app')
    email=f'qa-{uuid.uuid4().hex[:12]}@example.invalid'
    password=uuid.uuid4().hex+'Aa1!'
    account_id=None
    try:
        with httpx.Client(base_url=base,timeout=60) as client:
            r=client.post('/api/auth/register',json={'email':email,'password':password,'name':'Disposable QA Account'})
            assert r.status_code==200,(r.status_code,r.text[:200])
            account_id=r.json()['user']['id'];assert r.json()['user']['role']=='analyst'
            print('PASS: registration persisted, Analyst role enforced',flush=True)
            r=client.post('/api/auth/register',json={'email':email,'password':password,'name':'Duplicate QA Account'})
            assert r.status_code==409
            print('PASS: duplicate account rejected',flush=True)
            r=client.post('/api/auth/login',json={'email':email,'password':'WrongPassword123!'})
            assert r.status_code==401
            print('PASS: incorrect password rejected',flush=True)
            r=client.post('/api/auth/login',json={'email':email,'password':password})
            assert r.status_code==200
            headers={'Authorization':'Bearer '+r.json()['access_token']}
            for path in ['auth/me','dashboard/overview','digital-twin/network','inventory','warehouses','suppliers','shipments','disruptions','agents/status','recovery/plans','orders','notifications','settings']:
                started=time.monotonic();r=client.get('/api/'+path,headers=headers)
                assert r.status_code==200,(path,r.status_code,r.text[:200])
                print(f'PASS: {path} ({time.monotonic()-started:.2f}s)',flush=True)
            r=client.post('/api/auth/logout',headers=headers);assert r.status_code==200
            assert client.get('/api/auth/me',headers=headers).status_code==401
            r=client.post('/api/auth/login',json={'email':email,'password':password});assert r.status_code==200
            assert r.json()['user']['id']==account_id
            print('PASS: logout revokes old token; fresh login retains account',flush=True)
    finally:
        if account_id:
            load_dotenv('.env.local')
            from app.core.database import SessionLocal
            from app.models import User,AuditLog
            from sqlalchemy import delete
            with SessionLocal() as db:
                user=db.get(User,account_id)
                if user and user.email==email:
                    db.execute(delete(AuditLog).where(AuditLog.user_id==account_id));db.delete(user);db.commit()
                    print('Removed disposable QA account only.',flush=True)
if __name__=='__main__':main()
