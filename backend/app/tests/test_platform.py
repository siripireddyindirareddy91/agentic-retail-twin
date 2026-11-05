import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.core.database import SessionLocal
from app.models import Inventory,Shipment,Disruption,RecoveryAction,RecoveryPlan,AgentExecution

@pytest.fixture(scope='module')
def client():
    with TestClient(app) as c:yield c
@pytest.fixture(scope='module')
def auth(client):
    r=client.post('/api/auth/login',json={'email':'admin@supplytwin.demo','password':'SupplyTwin@2026'})
    assert r.status_code==200,r.text
    return {'Authorization':'Bearer '+r.json()['access_token']}

def test_health_and_protection(client):
    assert client.get('/api/health').json()['database']=='connected'
    assert client.get('/api/dashboard/overview').status_code==401
    assert client.get('/openapi.json').status_code==200
def test_registration_permissions_and_logout(client):
    r=client.post('/api/auth/register',json={'email':'new@example.com','password':'StrongPass123!','name':'New Analyst'})
    assert r.status_code==200
    h={'Authorization':'Bearer '+r.json()['access_token']}
    assert r.json()['user']['role']=='analyst'
    assert client.post('/api/simulations/run',headers=h,json={'scenario':'Supplier Failure','node_id':'SUP-001','duration':3,'severity':65}).status_code==403
    assert client.post('/api/auth/logout',headers=h).status_code==200
    assert client.get('/api/auth/me',headers=h).status_code==401
def test_all_read_modules(client,auth):
    for path in ['dashboard/overview','digital-twin/network','digital-twin/nodes/WH-001','inventory','warehouses','suppliers','shipments','shipments/SHP-2001','disruptions','agents/status','simulations/history','recovery/plans','orders','analytics/overview','notifications','settings','products','audit']:
        r=client.get('/api/'+path,headers=auth);assert r.status_code==200,(path,r.text)
    metrics=client.get('/api/dashboard/overview',headers=auth).json()['metrics']
    assert metrics['orders']==500 and metrics['warehouses']==18 and metrics['suppliers']==20
def test_inventory_crud_validation_and_history(client,auth):
    data={'product_id':'PRD-001','warehouse_id':'WH-001','quantity':100,'reserved':0,'safety_stock':25,'reorder_level':80}
    r=client.post('/api/inventory',headers=auth,json=data);assert r.status_code==200,r.text
    id=r.json()['id'];data['quantity']=150
    assert client.put('/api/inventory/'+id,headers=auth,json=data).status_code==200
    assert len(client.get('/api/inventory/'+id+'/history',headers=auth).json()['items'])==2
    data['reserved']=200
    assert client.put('/api/inventory/'+id,headers=auth,json=data).status_code==422
    assert client.delete('/api/inventory/'+id,headers=auth).status_code==200
@pytest.mark.parametrize('typ',['Supplier','Warehouse'])
def test_node_crud(client,auth,typ):
    data={'name':'Test '+typ,'type':typ,'city':'Pune','region':'West','capacity':10000,'reliability':94,'lead_time':4,'risk':20,'status':'Operational'}
    r=client.post('/api/network/nodes',headers=auth,json=data);assert r.status_code==200,r.text
    id=r.json()['id'];data['name']='Updated '+typ
    assert client.put('/api/network/nodes/'+id,headers=auth,json=data).status_code==200
    edge=client.post('/api/network/edges',headers=auth,json={'source':id,'target':'ST-001','distance':200});assert edge.status_code==200
    assert client.delete('/api/network/nodes/'+id,headers=auth).status_code==200
def test_order_shipment_disruption(client,auth):
    r=client.post('/api/orders',headers=auth,json={'customer':'Test Retail','warehouse_id':'WH-001','product_id':'PRD-001','quantity':10,'delivery_date':'2026-12-01'})
    assert r.status_code==200,r.text
    assert client.put('/api/orders/'+r.json()['id']+'/status',headers=auth,json={'status':'Cancelled'}).status_code==200
    assert client.put('/api/shipments/SHP-2001/status',headers=auth,json={'status':'Delivered'}).status_code==200
    r=client.post('/api/disruptions',headers=auth,json={'type':'Supplier Failure','node_id':'SUP-001','probability':.8,'impact':90,'root_cause':'Test disruption'})
    assert r.status_code==200 and r.json()['risk']==72
def test_full_simulation_approval_execution(client,auth):
    r=client.post('/api/simulations/run',headers=auth,json={'scenario':'Supplier Failure','node_id':'SUP-001','duration':8,'severity':90})
    assert r.status_code==200,r.text
    sim=r.json();assert sim['result']['affected_nodes'] and sim['result']['affected_inventory']
    assert len(sim['result']['strategies'])==4
    plans=client.get('/api/recovery/plans',headers=auth).json()['items'];plan=next(p for p in plans if p['disruption_id']==sim['disruption_id'])
    assert client.post('/api/recovery/plans/'+plan['id']+'/execute',headers=auth).status_code==409
    assert client.post('/api/recovery/plans/'+plan['id']+'/approve',headers=auth).status_code==200
    assert client.post('/api/recovery/plans/'+plan['id']+'/execute',headers=auth).status_code==200
    assert client.post('/api/recovery/plans/'+plan['id']+'/execute',headers=auth).status_code==409
    with SessionLocal() as db:
        assert db.get(Disruption,sim['disruption_id']).status=='Resolved'
        assert db.scalar(select(RecoveryAction).where(RecoveryAction.plan_id==plan['id']))
        for inv_id in sim['result']['affected_inventory']:
            inv=db.get(Inventory,inv_id);assert inv.quantity>=inv.reorder_level+inv.safety_stock
        for ship_id in sim['result']['affected_shipments']:
            ship=db.get(Shipment,ship_id);assert ship.delay==0
        assert db.scalar(select(AgentExecution).where(AgentExecution.agent=='Reporting Agent',AgentExecution.status=='Completed'))
def test_reports_notifications_filters(client,auth):
    assert client.get('/api/inventory?q=Rice&page_size=5',headers=auth).json()['total']>0
    r=client.get('/api/reports/inventory?format=csv',headers=auth);assert r.status_code==200 and 'product_id' in r.text
    r=client.get('/api/reports/recovery?format=pdf',headers=auth);assert r.status_code==200 and r.content.startswith(b'%PDF')
    assert client.post('/api/notifications/read-all',headers=auth).status_code==200
    assert all(n['read'] for n in client.get('/api/notifications',headers=auth).json()['items'])
def test_password_reset(client):
    r=client.post('/api/auth/forgot-password',json={'email':'new@example.com'});assert r.status_code==200
    reset=r.json()['demo_reset_token']
    assert client.post('/api/auth/reset-password',json={'token':reset,'password':'UpdatedPass123!'}).status_code==200
    assert client.post('/api/auth/login',json={'email':'new@example.com','password':'UpdatedPass123!'}).status_code==200
def test_reset_preserves_accounts(client,auth):
    assert client.post('/api/demo/reset',headers=auth).status_code==200
    assert client.get('/api/dashboard/overview',headers=auth).json()['metrics']['orders']==500
    assert client.get('/api/auth/me',headers=auth).status_code==200
