import os, secrets, hashlib, time, csv, io, logging, asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select, func, delete
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.core.database import Base, engine, get_db, SessionLocal
from app.core.security import current_user, writer, approver, admin, token, hash_password, verify_password, limit, DEMO
from app.models import *
from app.services.seed import seed
from app.services.simulation import uid, record, simulate, execute_plan
from app.agents.workflow import AGENTS

logging.basicConfig(level=logging.INFO)
@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    if DEMO:
        with SessionLocal() as db: seed(db)
    yield
app=FastAPI(title='SUPPLYTWIN AI API',version='1.0.0',lifespan=lifespan,description='Database-backed retail digital twin. Demo events and execution are simulated. Decisions use deterministic rules.')
app.add_middleware(CORSMiddleware,allow_origins=[s.strip() for s in os.getenv('CORS_ORIGINS','http://localhost:5173,http://127.0.0.1:5173').split(',')],allow_credentials=True,allow_methods=['GET','POST','PUT','DELETE','PATCH'],allow_headers=['Authorization','Content-Type'])
@app.exception_handler(IntegrityError)
async def integrity_error(request,exc):
    return __import__('fastapi').responses.JSONResponse(status_code=409,content={'detail':'This change conflicts with an existing record or referenced relationship.'})

class AuthIn(BaseModel):
    email: str = Field(min_length=5,max_length=200,pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    password: str = Field(min_length=8,max_length=72)
    name: str = Field(default='New user',min_length=2,max_length=80)
class ForgotIn(BaseModel):
    email: str = Field(min_length=5,max_length=200)
class ResetIn(BaseModel):
    token: str
    password: str = Field(min_length=8,max_length=72)
class ProfileIn(BaseModel):
    name: str = Field(min_length=2,max_length=80)
class NodeIn(BaseModel):
    name: str = Field(min_length=2,max_length=150)
    type: str = Field(pattern='^(Supplier|Warehouse|Distribution Center|Retail Store|Manufacturer)$')
    city: str = Field(min_length=2,max_length=80)
    region: str = Field(pattern='^(North|South|East|West)$')
    capacity: int = Field(default=20000,ge=0,le=100000000)
    reliability: float = Field(default=95,ge=0,le=100)
    lead_time: int = Field(default=4,ge=1,le=365)
    status: str = Field(default='Operational',pattern='^(Operational|Disrupted|Maintenance)$')
    risk: float = Field(default=15,ge=0,le=100)
class EdgeIn(BaseModel):
    source: str
    target: str
    distance: float = Field(default=100,ge=0)
class InventoryIn(BaseModel):
    product_id: str
    warehouse_id: str
    quantity: int = Field(ge=0,le=10000000)
    reserved: int = Field(default=0,ge=0)
    safety_stock: int = Field(default=100,ge=0)
    reorder_level: int = Field(default=300,ge=0)
class ProductIn(BaseModel):
    name: str = Field(min_length=2,max_length=120)
    sku: str = Field(min_length=2,max_length=80)
    category_id: str
    supplier_id: str
    unit_cost: float = Field(gt=0)
    daily_demand: float = Field(ge=0)
class OrderIn(BaseModel):
    customer: str = Field(min_length=2,max_length=150)
    warehouse_id: str
    product_id: str
    quantity: int = Field(gt=0,le=100000)
    delivery_date: str = Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
class StatusIn(BaseModel):
    status: str
class DisruptionIn(BaseModel):
    type: str = Field(min_length=2,max_length=100)
    node_id: str
    probability: float = Field(ge=0,le=1)
    impact: float = Field(ge=0,le=100)
    root_cause: str = Field(min_length=5,max_length=2000)
class SimIn(BaseModel):
    scenario: str = Field(pattern='^(Supplier Failure|Warehouse Shutdown|Transportation Delay|Natural Disaster|Sudden Demand Surge|Inventory Shortage|Port Congestion|Fuel Price Increase)$')
    node_id: str
    duration: int = Field(default=3,ge=1,le=90)
    severity: int = Field(default=65,ge=1,le=100)
class PlanIn(BaseModel):
    strategy: str = Field(min_length=3,max_length=100)
    cost: float = Field(ge=0)
    recovery_hours: int = Field(ge=1,le=8760)

def audit(db,user,action,data=None):
    db.add(AuditLog(id=uid('AUD'),user_id=user.id,action=action,data=data or {}))
def get_or_404(db,model,id):
    obj=db.get(model,id)
    if not obj: raise HTTPException(404,'Record not found')
    return obj
def user_info(user): return {'id':user.id,'name':user.name,'email':user.email,'role':user.role_id}
def network_stats(db):
    stats={}
    for label,model,column,amount,conditions in [
        ('occupancy',Inventory,Inventory.warehouse_id,func.sum(Inventory.quantity),[]),
        ('active_orders',Order,Order.warehouse_id,func.count(),[Order.status.notin_(['Delivered','Cancelled'])]),
        ('incoming_shipments',Shipment,Shipment.destination,func.count(),[Shipment.status!='Delivered']),
        ('outgoing_shipments',Shipment,Shipment.origin,func.count(),[Shipment.status!='Delivered'])
    ]:
        stats[label]=dict(db.execute(select(column,amount).where(*conditions).group_by(column)).all())
    connections={}
    for edge in db.scalars(select(Edge)):
        for key in (edge.source,edge.target): connections.setdefault(key,[]).append(record(edge))
    stats['connections']=connections
    return stats
def node_data(db,node,stats=None):
    data=record(node)
    stats=stats if stats is not None else network_stats(db)
    data['occupancy']=stats['occupancy'].get(node.id,0)
    data['available_capacity']=max(0,node.capacity-data['occupancy'])
    for label in ['active_orders','incoming_shipments','outgoing_shipments']:
        data[label]=stats[label].get(node.id,0)
    data['connections']=stats['connections'].get(node.id,[])
    data['risk_level']='High' if node.risk>=60 else 'Medium' if node.risk>=30 else 'Low'
    d=node.data or {}
    data['calculated_reliability']=round(.6*d.get('delivery_success',node.reliability)+.25*max(0,100-d.get('lead_time_variation',1)*10)+.15*(100-node.risk),1)
    return data
def inventory_rows(db):
    rows=[]
    supplier_leads=dict(db.execute(select(Node.id,Node.lead_time).where(Node.type=='Supplier')).all())
    for i,p,n,c in db.execute(select(Inventory,Product,Node,Category).join(Product,Inventory.product_id==Product.id).join(Node,Inventory.warehouse_id==Node.id).join(Category,Product.category_id==Category.id)):
        rows.append({**record(i),'name':p.name,'sku':p.sku,'category':c.name,'warehouse':n.name,'region':n.region,'unit_cost':p.unit_cost,'daily_demand':p.daily_demand,'available':i.quantity-i.reserved,'reorder_point':round(p.daily_demand*supplier_leads.get(p.supplier_id,4)+i.safety_stock),'status':'Low stock' if i.quantity-i.reserved<i.reorder_level else 'Overstock' if i.quantity>2000 else 'Healthy'})
    return rows
def page(rows,q='',status='',region='',page=1,page_size=20):
    if q: rows=[r for r in rows if q.lower() in str(r).lower()]
    if status: rows=[r for r in rows if r.get('status')==status or r.get('severity')==status or r.get('risk_level')==status]
    if region: rows=[r for r in rows if r.get('region')==region]
    return {'items':rows[(page-1)*page_size:page*page_size],'total':len(rows),'page':page,'page_size':page_size}

@app.get('/api/health')
def health(db:Session=Depends(get_db)):
    db.execute(select(1));return {'status':'ok','database':'connected','demo_mode':DEMO,'decision_mode':'Rule-based','ml_trained':False}
@app.post('/api/auth/register')
def register(data:AuthIn,request:Request,db:Session=Depends(get_db)):
    limit(request,'register',5)
    if db.scalar(select(User).where(User.email==data.email.lower())): raise HTTPException(409,'An account already exists for this email')
    user=User(id=uid('USR'),email=data.email.lower(),name=data.name,password_hash=hash_password(data.password),role_id='analyst')
    db.add(user);db.flush();audit(db,user,'register');db.commit()
    return {'access_token':token(user),'user':user_info(user)}
@app.post('/api/auth/login')
def login(data:AuthIn,request:Request,db:Session=Depends(get_db)):
    limit(request,'login')
    user=db.scalar(select(User).where(User.email==data.email.lower()))
    if not user or not verify_password(data.password,user.password_hash): raise HTTPException(401,'Email or password is incorrect')
    audit(db,user,'login');db.commit();return {'access_token':token(user),'user':user_info(user)}
@app.get('/api/auth/me')
def me(user=Depends(current_user)):return user_info(user)
@app.put('/api/auth/profile')
def profile(data:ProfileIn,user=Depends(current_user),db:Session=Depends(get_db)):
    user.name=data.name;db.commit();return user_info(user)
@app.post('/api/auth/logout')
def logout(user=Depends(current_user),db:Session=Depends(get_db)):
    user.session_version+=1;db.commit();return {'message':'All sessions signed out'}
@app.post('/api/auth/forgot-password')
def forgot(data:ForgotIn,request:Request,db:Session=Depends(get_db)):
    limit(request,'forgot',5)
    user=db.scalar(select(User).where(User.email==data.email.lower()))
    response={'message':'If the account exists, a reset request has been recorded. Email delivery requires an SMTP integration.'}
    if user:
        reset=secrets.token_urlsafe(32);user.reset_hash=hashlib.sha256(reset.encode()).hexdigest();user.reset_expires=time.time()+900;db.commit()
        # A local demo explicitly shows the token rather than claiming an email was sent.
        if DEMO and request.client and request.client.host in ['127.0.0.1','localhost','testclient']:
            response['demo_reset_token']=reset
    return response
@app.post('/api/auth/reset-password')
def reset(data:ResetIn,db:Session=Depends(get_db)):
    user=db.scalar(select(User).where(User.reset_hash==hashlib.sha256(data.token.encode()).hexdigest()))
    if not user or (user.reset_expires or 0)<time.time(): raise HTTPException(400,'Invalid or expired reset token')
    user.password_hash=hash_password(data.password);user.reset_hash=None;user.reset_expires=None;user.session_version+=1;db.commit();return {'message':'Password reset. Please sign in.'}

@app.get('/api/dashboard/overview')
def dashboard(user=Depends(current_user),db:Session=Depends(get_db)):
    orders=db.scalars(select(Order)).all();ships=db.scalars(select(Shipment)).all();dis=db.scalars(select(Disruption).where(Disruption.status=='Active')).all();inv=inventory_rows(db)
    completed=[s for s in ships if s.status=='Delivered']
    metrics={'orders':len(orders),'shipments':len([s for s in ships if s.status not in ['Delivered','Cancelled']]),'inventory':sum(i['quantity'] for i in inv),'warehouses':db.scalar(select(func.count()).select_from(Node).where(Node.type=='Warehouse')),'suppliers':db.scalar(select(func.count()).select_from(Node).where(Node.type=='Supplier')),'disruptions':len(dis),'on_time':round(100*sum(s.delay==0 for s in completed)/max(1,len(completed)),1),'risk':round(sum(d.risk for d in dis)/max(1,len(dis)),1)}
    trend=[]
    for days in range(6,-1,-1):
        from datetime import timedelta
        date=(datetime.now(timezone.utc)-timedelta(days=days)).date()
        day_orders=[o for o in orders if o.created_at.date()==date]
        trend.append({'date':date.strftime('%d %b'),'orders':len(day_orders),'value':round(sum(o.value for o in day_orders)),'fulfilled':sum(o.status=='Delivered' for o in day_orders)})
    return {'metrics':metrics,'trend':trend,'disruptions':[record(d) for d in dis],'activities':[record(n) for n in db.scalars(select(Notification).order_by(Notification.created_at.desc()).limit(8))],'inventory_health':[{'name':s,'value':sum(i['status']==s for i in inv)} for s in ['Healthy','Low stock','Overstock']],'insights':[{'title':'Replenishment opportunity','text':f'{sum(i["status"]=="Low stock" for i in inv)} stock positions are below their reorder threshold. Review inventory redistribution.'},{'title':'Network resilience','text':f'{len(dis)} active synthetic disruptions are being monitored. Run the agent workflow to generate recovery options.'}],'mode':'Rule-based','simulated':True}
@app.get('/api/digital-twin/network')
def network(user=Depends(current_user),db:Session=Depends(get_db)):
    stats=network_stats(db)
    return {'nodes':[node_data(db,n,stats) for n in db.scalars(select(Node))],'edges':[record(e) for e in db.scalars(select(Edge))]}
@app.get('/api/digital-twin/nodes/{id}')
def node_detail(id:str,user=Depends(current_user),db:Session=Depends(get_db)):
    return node_data(db,get_or_404(db,Node,id))
@app.post('/api/network/nodes')
def add_node(data:NodeIn,user=Depends(writer),db:Session=Depends(get_db)):
    node=Node(id=uid('NOD'),**data.model_dump());db.add(node);audit(db,user,'create_node',data.model_dump());db.commit();return record(node)
@app.put('/api/network/nodes/{id}')
def edit_node(id:str,data:NodeIn,user=Depends(writer),db:Session=Depends(get_db)):
    node=get_or_404(db,Node,id)
    for k,v in data.model_dump().items():setattr(node,k,v)
    audit(db,user,'edit_node',{'id':id});db.commit();return record(node)
@app.delete('/api/network/nodes/{id}')
def remove_node(id:str,user=Depends(writer),db:Session=Depends(get_db)):
    node=get_or_404(db,Node,id)
    references=[(Product,Product.supplier_id),(Inventory,Inventory.warehouse_id),(Order,Order.warehouse_id),(Shipment,Shipment.origin),(Shipment,Shipment.destination),(Disruption,Disruption.node_id)]
    if any(db.scalar(select(func.count()).select_from(m).where(c==id)) for m,c in references):raise HTTPException(409,'This node has operational records. Reassign them before deletion.')
    db.execute(delete(Edge).where((Edge.source==id)|(Edge.target==id)));db.delete(node);audit(db,user,'delete_node',{'id':id});db.commit();return {'deleted':id}
@app.post('/api/network/edges')
def add_edge(data:EdgeIn,user=Depends(writer),db:Session=Depends(get_db)):
    get_or_404(db,Node,data.source);get_or_404(db,Node,data.target)
    if data.source==data.target:raise HTTPException(422,'A node cannot connect to itself')
    if db.scalar(select(Edge).where(Edge.source==data.source,Edge.target==data.target)):raise HTTPException(409,'Route already exists')
    edge=Edge(id=uid('EDG'),**data.model_dump());db.add(edge);audit(db,user,'connect_nodes',data.model_dump());db.commit();return record(edge)
@app.delete('/api/network/edges/{id}')
def remove_edge(id:str,user=Depends(writer),db:Session=Depends(get_db)):
    db.delete(get_or_404(db,Edge,id));audit(db,user,'delete_route',{'id':id});db.commit();return {'deleted':id}
@app.get('/api/products')
def products(user=Depends(current_user),db:Session=Depends(get_db)):
    return {'items':[record(p) for p in db.scalars(select(Product))],'categories':[record(c) for c in db.scalars(select(Category))]}
@app.post('/api/products')
def add_product(data:ProductIn,user=Depends(writer),db:Session=Depends(get_db)):
    get_or_404(db,Category,data.category_id);n=get_or_404(db,Node,data.supplier_id)
    if n.type!='Supplier':raise HTTPException(422,'Product requires a supplier')
    p=Product(id=uid('PRD'),**data.model_dump());db.add(p);audit(db,user,'create_product',{'id':p.id});db.commit();return record(p)
@app.get('/api/inventory')
def inventory(q:str='',status:str='',region:str='',page_no:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=500),user=Depends(current_user),db:Session=Depends(get_db)):
    return page(inventory_rows(db),q,status,region,page_no,page_size)
def validate_inventory(db,data):
    get_or_404(db,Product,data.product_id);node=get_or_404(db,Node,data.warehouse_id)
    if node.type!='Warehouse':raise HTTPException(422,'Inventory must belong to a warehouse')
    if data.reserved>data.quantity:raise HTTPException(422,'Reserved units cannot exceed total quantity')
@app.post('/api/inventory')
def add_inventory(data:InventoryIn,user=Depends(writer),db:Session=Depends(get_db)):
    validate_inventory(db,data);i=Inventory(id=uid('INV'),**data.model_dump());db.add(i);db.flush();db.add(Transaction(id=uid('TXN'),inventory_id=i.id,quantity=i.quantity,reason='Opening stock'));audit(db,user,'create_inventory',{'id':i.id});db.commit();return record(i)
@app.put('/api/inventory/{id}')
def update_inventory(id:str,data:InventoryIn,user=Depends(writer),db:Session=Depends(get_db)):
    validate_inventory(db,data);i=get_or_404(db,Inventory,id);delta=data.quantity-i.quantity
    for k,v in data.model_dump().items():setattr(i,k,v)
    db.add(Transaction(id=uid('TXN'),inventory_id=id,quantity=delta,reason='Manual stock adjustment'));audit(db,user,'update_inventory',{'id':id,'delta':delta});db.commit();return record(i)
@app.delete('/api/inventory/{id}')
def remove_inventory(id:str,user=Depends(writer),db:Session=Depends(get_db)):
    i=get_or_404(db,Inventory,id);db.execute(delete(Transaction).where(Transaction.inventory_id==id));db.delete(i);audit(db,user,'delete_inventory',{'id':id});db.commit();return {'deleted':id}
@app.get('/api/inventory/{id}/history')
def inventory_history(id:str,user=Depends(current_user),db:Session=Depends(get_db)):
    return {'items':[record(t) for t in db.scalars(select(Transaction).where(Transaction.inventory_id==id).order_by(Transaction.created_at.desc()))]}
@app.get('/api/warehouses')
def warehouses(q:str='',status:str='',region:str='',page_no:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=500),user=Depends(current_user),db:Session=Depends(get_db)):
    stats=network_stats(db)
    return page([node_data(db,n,stats) for n in db.scalars(select(Node).where(Node.type=='Warehouse'))],q,status,region,page_no,page_size)
@app.get('/api/suppliers')
def suppliers(q:str='',status:str='',region:str='',page_no:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=500),user=Depends(current_user),db:Session=Depends(get_db)):
    stats=network_stats(db)
    return page([node_data(db,n,stats) for n in db.scalars(select(Node).where(Node.type=='Supplier'))],q,status,region,page_no,page_size)
@app.get('/api/shipments')
def shipments(q:str='',status:str='',region:str='',page_no:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=500),user=Depends(current_user),db:Session=Depends(get_db)):
    nodes={n.id:n for n in db.scalars(select(Node))}
    return page([{**record(s),'origin_name':nodes[s.origin].city,'destination_name':nodes[s.destination].city,'region':nodes[s.origin].region} for s in db.scalars(select(Shipment))],q,status,region,page_no,page_size)
@app.get('/api/shipments/{id}')
def shipment_detail(id:str,user=Depends(current_user),db:Session=Depends(get_db)):
    return {**record(get_or_404(db,Shipment,id)),'events':[record(e) for e in db.scalars(select(ShipmentEvent).where(ShipmentEvent.shipment_id==id).order_by(ShipmentEvent.created_at))]}
@app.put('/api/shipments/{id}/status')
def shipment_status(id:str,data:StatusIn,user=Depends(writer),db:Session=Depends(get_db)):
    if data.status not in ['Created','Processing','Dispatched','In Transit','Delayed','Out for Delivery','Delivered','Cancelled']:raise HTTPException(422,'Invalid shipment status')
    s=get_or_404(db,Shipment,id);s.status=data.status
    if s.status=='Delivered':s.actual_delivery=datetime.now(timezone.utc).date().isoformat()
    db.add(ShipmentEvent(id=uid('SE'),shipment_id=id,status=s.status,location=s.current_location));audit(db,user,'shipment_status',{'id':id,'status':s.status});db.commit();return record(s)
@app.get('/api/orders')
def orders(q:str='',status:str='',region:str='',page_no:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=500),user=Depends(current_user),db:Session=Depends(get_db)):
    nodes={n.id:n for n in db.scalars(select(Node))}
    return page([{**record(o),'warehouse':nodes[o.warehouse_id].city,'region':nodes[o.warehouse_id].region} for o in db.scalars(select(Order).order_by(Order.created_at.desc()))],q,status,region,page_no,page_size)
@app.post('/api/orders')
def add_order(data:OrderIn,user=Depends(writer),db:Session=Depends(get_db)):
    p=get_or_404(db,Product,data.product_id);n=get_or_404(db,Node,data.warehouse_id)
    if n.type!='Warehouse':raise HTTPException(422,'Select a warehouse')
    o=Order(id=uid('ORD'),customer=data.customer,warehouse_id=data.warehouse_id,quantity=data.quantity,value=round(p.unit_cost*data.quantity,2),status='Processing',delivery_date=data.delivery_date,risk='Low');db.add(o);db.flush();db.add(OrderItem(id=uid('OI'),order_id=o.id,product_id=p.id,quantity=data.quantity));audit(db,user,'create_order',{'id':o.id});db.commit();return record(o)
@app.put('/api/orders/{id}/status')
def order_status(id:str,data:StatusIn,user=Depends(writer),db:Session=Depends(get_db)):
    if data.status not in ['Processing','Dispatched','Delivered','At risk','Cancelled']:raise HTTPException(422,'Invalid order status')
    o=get_or_404(db,Order,id);o.status=data.status;audit(db,user,'order_status',{'id':id,'status':o.status});db.commit();return record(o)
@app.get('/api/disruptions')
def disruptions(q:str='',status:str='',region:str='',page_no:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=500),user=Depends(current_user),db:Session=Depends(get_db)):
    return page([{**record(d),'location':db.get(Node,d.node_id).city,'region':db.get(Node,d.node_id).region} for d in db.scalars(select(Disruption).order_by(Disruption.created_at.desc()))],q,status,region,page_no,page_size)
@app.post('/api/disruptions')
def add_disruption(data:DisruptionIn,user=Depends(writer),db:Session=Depends(get_db)):
    get_or_404(db,Node,data.node_id);risk=round(data.probability*data.impact,1)
    d=Disruption(id=uid('DIS'),**data.model_dump(),risk=risk,severity='Critical' if risk>=70 else 'High' if risk>=45 else 'Medium' if risk>=20 else 'Low',financial_impact=0);db.add(d);audit(db,user,'create_disruption',{'id':d.id});db.commit();return record(d)
@app.post('/api/simulations/run')
def run_simulation(data:SimIn,user=Depends(writer),db:Session=Depends(get_db)):
    try:sim=simulate(db,data.model_dump(),user)
    except ValueError as e:raise HTTPException(422,str(e))
    audit(db,user,'run_simulation',{'id':sim.id});db.commit();return record(sim)
@app.get('/api/simulations/history')
def simulations(user=Depends(current_user),db:Session=Depends(get_db)):
    return {'items':[record(s) for s in db.scalars(select(Simulation).order_by(Simulation.created_at.desc()).limit(100))]}
@app.get('/api/agents/status')
def agents(user=Depends(current_user),db:Session=Depends(get_db)):
    rows=db.scalars(select(AgentExecution).order_by(AgentExecution.created_at.desc())).all()
    result=[]
    for name,description in AGENTS:
        runs=[r for r in rows if r.agent==name]
        result.append({'name':name,'description':description,'status':runs[0].status if runs else 'Idle','last_execution':runs[0].created_at if runs else None,'execution_count':len(runs),'success_rate':round(100*sum(r.status=='Completed' for r in runs)/len(runs),1) if runs else None,'mode':'Rule-based'})
    return {'items':result,'history':[record(r) for r in rows[:30]],'orchestrator':'LangGraph','mode':'Rule-based'}
@app.post('/api/agents/run')
def run_agents(user=Depends(writer),db:Session=Depends(get_db)):
    dis=db.scalar(select(Disruption).where(Disruption.status=='Active').order_by(Disruption.risk.desc()))
    if not dis:raise HTTPException(409,'No active disruption. Create a scenario first.')
    sim=simulate(db,{'scenario':'Supplier Failure','node_id':dis.node_id,'duration':3,'severity':max(1,round(dis.risk))},user);audit(db,user,'run_agents');db.commit();return record(sim)
@app.get('/api/recovery/plans')
def plans(user=Depends(current_user),db:Session=Depends(get_db)):
    return {'items':[{**record(p),'root_cause':db.get(Disruption,p.disruption_id).root_cause} for p in db.scalars(select(RecoveryPlan).order_by(RecoveryPlan.created_at.desc()))]}
@app.put('/api/recovery/plans/{id}')
def edit_plan(id:str,data:PlanIn,user=Depends(approver),db:Session=Depends(get_db)):
    p=get_or_404(db,RecoveryPlan,id)
    if p.status!='Pending approval':raise HTTPException(409,'Only pending plans can be edited')
    for k,v in data.model_dump().items():setattr(p,k,v)
    audit(db,user,'edit_plan',{'id':id});db.commit();return record(p)
@app.post('/api/recovery/plans/{id}/{action}')
def plan_action(id:str,action:str,user=Depends(approver),db:Session=Depends(get_db)):
    p=db.scalar(select(RecoveryPlan).where(RecoveryPlan.id==id).with_for_update())
    if not p:raise HTTPException(404,'Plan not found')
    if action in ['approve','reject']:
        if p.status!='Pending approval':raise HTTPException(409,'Only pending plans can be approved or rejected')
        p.status='Approved' if action=='approve' else 'Rejected'
    elif action=='execute':
        try:execute_plan(db,p)
        except ValueError as e:raise HTTPException(409,str(e))
    else:raise HTTPException(404,'Unknown action')
    audit(db,user,f'recovery_{action}',{'id':id,'simulated':True});db.commit();return record(p)
@app.get('/api/notifications')
def notifications(user=Depends(current_user),db:Session=Depends(get_db)):
    return {'items':[record(n) for n in db.scalars(select(Notification).order_by(Notification.created_at.desc()).limit(200))]}
@app.post('/api/notifications/read-all')
def read_all(user=Depends(current_user),db:Session=Depends(get_db)):
    for n in db.scalars(select(Notification).where(Notification.read==False)):n.read=True
    db.commit();return {'message':'All notifications marked read'}
@app.post('/api/notifications/{id}/read')
def read_one(id:str,user=Depends(current_user),db:Session=Depends(get_db)):
    n=get_or_404(db,Notification,id);n.read=True;db.commit();return record(n)
@app.get('/api/analytics/overview')
def analytics(user=Depends(current_user),db:Session=Depends(get_db)):
    nodes=db.scalars(select(Node)).all();dis=db.scalars(select(Disruption)).all();plans=db.scalars(select(RecoveryPlan)).all()
    return {'regions':[{'name':r,'risk':round(sum(n.risk for n in nodes if n.region==r)/max(1,sum(n.region==r for n in nodes)),1),'nodes':sum(n.region==r for n in nodes),'impact':sum(d.financial_impact for d in dis if db.get(Node,d.node_id).region==r)} for r in ['North','South','East','West']],'suppliers':[{'name':n.name.split(' ')[0],'risk':n.risk,'reliability':n.reliability} for n in nodes if n.type=='Supplier'],'disruptions':[{'name':t,'value':sum(d.type==t for d in dis)} for t in sorted({d.type for d in dis})],'financial_impact':round(sum(d.financial_impact for d in dis),2),'recovery_cost':round(sum(p.cost for p in plans if p.status=='Executed'),2),'resolved':sum(d.status=='Resolved' for d in dis),'pending':sum(p.status=='Pending approval' for p in plans)}
@app.get('/api/reports/{kind}')
def report(kind:str,format:str='csv',start:str='',end:str='',user=Depends(current_user),db:Session=Depends(get_db)):
    models={'inventory':Inventory,'suppliers':Node,'shipments':Shipment,'disruptions':Disruption,'agents':AgentExecution,'recovery':RecoveryPlan,'orders':Order,'health':Disruption}
    if kind not in models:raise HTTPException(404,'Unknown report type')
    rows=[record(r) for r in db.scalars(select(models[kind]))]
    if kind=='suppliers':rows=[r for r in rows if r['type']=='Supplier']
    if start:rows=[r for r in rows if not r.get('created_at') or str(r['created_at'])[:10]>=start]
    if end:rows=[r for r in rows if not r.get('created_at') or str(r['created_at'])[:10]<=end]
    if format=='pdf':
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        buf=io.BytesIO();c=canvas.Canvas(buf,pagesize=A4);c.setTitle(f'SupplyTwin {kind} report');y=800
        for line in [f'SUPPLYTWIN AI | {kind.upper()} REPORT','Synthetic demonstration data · Rule-based decisions',f'Generated {datetime.now(timezone.utc).isoformat()}',f'Records: {len(rows)}','']+[f'{r.get("id","")} | '+ ' | '.join(f'{k}: {v}' for k,v in list(r.items())[1:5]) for r in rows]:
            c.setFont('Helvetica',9);c.drawString(36,y,str(line)[:115]);y-=16
            if y<40:c.showPage();y=800
        c.save();return Response(buf.getvalue(),media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="supplytwin-{kind}.pdf"'})
    if format!='csv':raise HTTPException(422,'Format must be csv or pdf')
    out=io.StringIO();keys=list(rows[0]) if rows else ['id'];w=csv.DictWriter(out,fieldnames=keys);w.writeheader()
    for row in rows:
        # Prevent spreadsheet formula injection on exported free text.
        w.writerow({k:("'"+str(v) if str(v).startswith(('=','+','-','@')) else str(v)) for k,v in row.items()})
    return Response(out.getvalue(),media_type='text/csv',headers={'Content-Disposition':f'attachment; filename="supplytwin-{kind}.csv"'})
@app.get('/api/settings')
def settings(user=Depends(current_user)):
    return {'demo_mode':DEMO,'decision_mode':'Rule-based','llm_configured':bool(os.getenv('LLM_API_KEY')),'ml_trained':False,'database':'PostgreSQL' if 'postgres' in str(engine.url) else 'SQLite (local development)','event_interval_seconds':15,'external_integrations':[]}
@app.get('/api/audit')
def audit_logs(user=Depends(admin),db:Session=Depends(get_db)):
    return {'items':[record(a) for a in db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(100))]}

@app.post('/api/events/tick')
def event_tick(user=Depends(writer),db:Session=Depends(get_db)):
    if not DEMO:raise HTTPException(403,'Event generator is available only in demo mode')
    # Explicit client-controlled ticks keep serverless runtimes free of runaway tasks.
    index=db.scalar(select(func.count()).select_from(Notification))
    ship=db.scalar(select(Shipment).where(Shipment.status=='In Transit').order_by(Shipment.id).offset(index%10))
    if ship:
        ship.status='Delayed';ship.delay+=2
        db.add(ShipmentEvent(id=uid('SE'),shipment_id=ship.id,status='Delayed',location=ship.current_location))
        node=db.get(Node,ship.origin)
        sim=simulate(db,{'scenario':'Transportation Delay','node_id':node.id,'duration':1,'severity':45},user)
        notification=Notification(id=uid('NTF'),title='Simulated shipment delay',message=f'{ship.id} delayed by 2 hours near {ship.current_location}. Recovery workflow triggered.',severity='High')
    else:notification=Notification(id=uid('NTF'),title='Simulated network heartbeat',message='All monitored network entities checked.',severity='Low')
    db.add(notification);audit(db,user,'simulated_event');db.commit();return record(notification)
@app.post('/api/demo/reset')
def demo_reset(user=Depends(admin),db:Session=Depends(get_db)):
    if not DEMO:raise HTTPException(403,'Reset is restricted to demo mode')
    # Preserve accounts and role grants while restoring synthetic operational data.
    for model in [RecoveryAction,AgentExecution,Simulation,RecoveryPlan,Notification,Disruption,ShipmentEvent,Shipment,OrderItem,Order,Transaction,Inventory,Product,Edge,Node,Category]:db.execute(delete(model))
    # seed() owns demo account setup, so retain users and avoid duplicate insertion.
    db.commit()
    from app.services.seed import seed as seed_fn
    seed_fn(db);return {'message':'Demo data restored'}
