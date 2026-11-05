import uuid, math
from sqlalchemy import select
from app.models import *

def uid(prefix): return f'{prefix}-{uuid.uuid4().hex[:10].upper()}'
def record(obj):
    return {c.name:getattr(obj,c.name) for c in obj.__table__.columns}
def simulate(db, config, user):
    node=db.get(Node,config['node_id'])
    if not node: raise ValueError('Selected node does not exist')
    # Follow directed edges to determine the downstream blast radius.
    edges=db.scalars(select(Edge)).all(); affected={node.id}; changed=True
    while changed:
        changed=False
        for e in edges:
            if e.source in affected and e.target not in affected:
                affected.add(e.target); changed=True
    products=db.scalars(select(Product).where(Product.supplier_id==node.id)).all() if node.type=='Supplier' else []
    product_ids={p.id for p in products}
    inv=[i for i in db.scalars(select(Inventory)).all() if i.warehouse_id in affected or i.product_id in product_ids]
    warehouses={i.warehouse_id for i in inv}; affected |= warehouses
    all_products={p.id:p for p in db.scalars(select(Product)).all()}
    duration=config['duration']; severity=config['severity']/100
    available=sum(max(0,i.quantity-i.reserved) for i in inv)
    demand=sum(all_products[i.product_id].daily_demand*duration for i in inv)
    exposed=round(demand*severity)
    shortage=max(0,exposed-available)
    orders=[o for o in db.scalars(select(Order)).all() if o.warehouse_id in warehouses and o.status not in ['Delivered','Cancelled']]
    shipments=[s for s in db.scalars(select(Shipment)).all() if (s.origin in affected or s.destination in affected) and s.status not in ['Delivered','Cancelled']]
    cost=sum(all_products[i.product_id].unit_cost*all_products[i.product_id].daily_demand*duration*severity for i in inv)
    financial=round(cost*.15+sum(o.value for o in orders)*severity*.1,2)
    risk=round(min(100,severity*65+min(25,len(orders)*1.5)+min(10,duration)),1)
    disruption=Disruption(id=uid('DIS'),type=config['scenario'],node_id=node.id,severity='Critical' if risk>=70 else 'High' if risk>=45 else 'Medium',probability=1,impact=risk,risk=risk,financial_impact=financial,root_cause=f'Simulated {config["scenario"].lower()} affecting {node.name} for {duration} days at {config["severity"]}% severity.')
    db.add(disruption); db.flush()
    result={'affected_nodes':sorted(affected),'affected_inventory':[i.id for i in inv],'affected_orders':[o.id for o in orders],'affected_shipments':[s.id for s in shipments],'inventory_before':available,'inventory_after':max(0,available-exposed),'shortage':shortage,'delayed_orders':len(orders),'financial_impact':financial,'risk_before':node.risk,'risk_after':risk,'recovery_days':math.ceil(duration*(.5+severity)),'fulfillment_before':100,'fulfillment_after':round(max(0,100-len(orders)/max(1,len(orders)+20)*severity*100),1),'affected_warehouses':len(warehouses),'affected_stores':len([n for n in affected if n.startswith('ST-')]),'mode':'Rule-based','simulated':True}
    strategies=[]
    for name,mult,hours,fulfillment in [('Alternative supplier',.22,24,97),('Inventory redistribution',.12,18,94),('Emergency procurement',.38,8,99),('Shipment rerouting',.08,36,91)]:
        strategies.append({'strategy':name,'cost':round(max(2500,financial*mult),2),'recovery_hours':max(4,round(hours*(.5+severity))),'fulfillment':fulfillment,'operational_risk':'Low' if fulfillment>95 else 'Medium'})
    result['strategies']=strategies
    sim=Simulation(id=uid('SIM'),user_id=user.id,disruption_id=disruption.id,config=config,result=result)
    db.add(sim)
    from app.agents.workflow import run_workflow
    run_workflow(db,result,disruption,strategies)
    db.add(Notification(id=uid('NTF'),title='Recovery approval requested',message=f'{node.name}: {len(orders)} orders exposed. Review the generated recovery plan.',severity=disruption.severity))
    return sim

def execute_plan(db,plan):
    if plan.status!='Approved': raise ValueError('Only approved plans can be executed')
    disruption=db.get(Disruption,plan.disruption_id)
    # Each execution is transactional and protected by the API row lock.
    for inv_id in plan.data.get('affected_inventory',[]):
        inv=db.get(Inventory,inv_id)
        if inv:
            amount=max(0,inv.reorder_level+inv.safety_stock-inv.quantity)
            inv.quantity+=amount
            if amount: db.add(Transaction(id=uid('TXN'),inventory_id=inv.id,quantity=amount,reason=f'Simulated recovery {plan.id}'))
    for ship_id in plan.data.get('affected_shipments',[]):
        ship=db.get(Shipment,ship_id)
        if ship and ship.status not in ['Delivered','Cancelled']:
            ship.status='In Transit';ship.delay=0
            db.add(ShipmentEvent(id=uid('SE'),shipment_id=ship.id,status='Rerouted',location=ship.current_location))
    for order_id in plan.data.get('affected_orders',[]):
        order=db.get(Order,order_id)
        if order and order.status not in ['Delivered','Cancelled']:
            order.risk='Low';order.status='Processing'
    plan.status='Executed';disruption.status='Resolved'
    db.add(RecoveryAction(id=uid('ACT'),plan_id=plan.id,action='Simulated execution',data=plan.data))
    for agent in ['Execution Agent','Reporting Agent']:
        db.add(AgentExecution(id=uid('AGT'),agent=agent,status='Completed',output={'plan_id':plan.id,'message':'Simulated recovery persisted' if agent.startswith('Execution') else 'Recovery report available in Reports','simulated':True}))
    db.add(Notification(id=uid('NTF'),title='Recovery completed',message=f'{plan.strategy} executed in simulation. Disruption {disruption.id} resolved.',severity='Low'))
