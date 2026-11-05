import random, os
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from app.models import *
from app.core.security import hash_password

CITIES = [('Bengaluru','South',12.97,77.59),('Hyderabad','South',17.38,78.49),('Chennai','South',13.08,80.27),('Mumbai','West',19.07,72.87),('Delhi','North',28.61,77.20),('Pune','West',18.52,73.85),('Kolkata','East',22.57,88.36),('Ahmedabad','West',23.02,72.57),('Vijayawada','South',16.50,80.64),('Visakhapatnam','South',17.68,83.21)]
def seed(db):
    if db.scalar(select(Node.id).limit(1)):
        return
    r = random.Random(42)
    for role in ['admin','supply-chain-manager','warehouse-manager','inventory-manager','logistics-manager','analyst']:
        if not db.get(Role,role): db.add(Role(id=role,name=role.replace('-',' ').title()))
    db.flush()
    if not db.get(User,'USR-DEMO'): db.add(User(id='USR-DEMO',name='Arjun Mehta',email='admin@supplytwin.demo',password_hash=hash_password(os.getenv('DEMO_PASSWORD','SupplyTwin@2026')),role_id='admin'))
    if not db.get(User,'USR-ANALYST'): db.add(User(id='USR-ANALYST',name='Priya Sharma',email='analyst@supplytwin.demo',password_hash=hash_password(os.getenv('DEMO_PASSWORD','SupplyTwin@2026')),role_id='analyst'))
    for typ,count,prefix in [('Supplier',20,'SUP'),('Warehouse',18,'WH'),('Distribution Center',10,'DC'),('Retail Store',30,'ST'),('Manufacturer',6,'MFG')]:
        for i in range(count):
            city,region,lat,lon=CITIES[i%10]
            names=['Reliance','Tata Consumer','ITC','Britannia','Hindustan','Amul','Dabur','Marico','Godrej','Nestlé']
            name=f'{names[i%10]} {city}' if typ=='Supplier' else f'{city} {"Central" if i<10 else "East"} {typ}'
            db.add(Node(id=f'{prefix}-{i+1:03}',name=name,type=typ,city=city,region=region,risk=r.randint(7,68),capacity=r.randint(20,60)*1000,reliability=round(r.uniform(82,99.5),1),lead_time=r.randint(2,7),latitude=lat,longitude=lon,data={'delivery_success':round(r.uniform(87,99),1),'lead_time_variation':round(r.uniform(.2,2.5),1)}))
    db.flush()
    edges=[]
    for i in range(20):
        edges.append(Edge(id=f'E-S{i}',source=f'SUP-{i+1:03}',target=f'WH-{i%18+1:03}',distance=150+i*27))
    for i in range(18):
        edges.append(Edge(id=f'E-W{i}',source=f'WH-{i+1:03}',target=f'DC-{i%10+1:03}',distance=90+i*19))
    for i in range(30):
        edges.append(Edge(id=f'E-D{i}',source=f'DC-{i%10+1:03}',target=f'ST-{i+1:03}',distance=25+i*7))
    for i in range(6):
        edges.append(Edge(id=f'E-M{i}',source=f'MFG-{i+1:03}',target=f'SUP-{i+1:03}',distance=60+i*25))
    db.add_all(edges)
    categories=['Staples','Dairy','Beverages','Personal Care','Household','Snacks']
    for i,c in enumerate(categories):
        db.add(Category(id=f'CAT-{i}',name=c))
    db.flush()
    products=['Basmati Rice 5kg','Full Cream Milk 1L','Premium Tea 250g','Hand Wash 500ml','Laundry Detergent 1kg','Whole Wheat Biscuits','Sunflower Oil 1L','Greek Yogurt 400g','Filter Coffee 200g','Shampoo 350ml','Surface Cleaner 1L','Roasted Almonds 200g']
    for i in range(100):
        db.add(Product(id=f'PRD-{i+1:03}',name=products[i%12]+(f' · Pack {i//12+1}' if i>=12 else ''),sku=f'STW-{10000+i}',category_id=f'CAT-{i%6}',supplier_id=f'SUP-{i%20+1:03}',unit_cost=round(r.uniform(45,1500),2),daily_demand=r.randint(8,75)))
    db.flush()
    for i in range(300):
        qty=r.randint(45,2400)
        db.add(Inventory(id=f'INV-{i+1:04}',product_id=f'PRD-{i%100+1:03}',warehouse_id=f'WH-{i%18+1:03}',quantity=qty,reserved=min(qty,r.randint(0,90)),safety_stock=100,reorder_level=r.randint(200,600)))
    db.flush()
    for i in range(300):
        db.add(Transaction(id=f'TXN-{i:04}',inventory_id=f'INV-{i+1:04}',quantity=r.randint(20,200),reason='Synthetic opening receipt'))
    today=datetime.now(timezone.utc)
    for i in range(500):
        db.add(Order(id=f'ORD-{i+10001}',customer=f'Retail Partner {i%70+1:03}',warehouse_id=f'WH-{i%18+1:03}',status=r.choices(['Delivered','Processing','Dispatched','At risk','Cancelled'],[60,18,12,8,2])[0],value=round(r.uniform(3000,85000),2),quantity=r.randint(5,80),risk=r.choice(['Low','Low','Medium','High']),created_at=today-timedelta(days=r.randint(0,89)),delivery_date=(today+timedelta(days=r.randint(1,7))).date().isoformat()))
    db.flush()
    for i in range(500):
        db.add(OrderItem(id=f'OI-{i}',order_id=f'ORD-{i+10001}',product_id=f'PRD-{i%100+1:03}',quantity=r.randint(5,80)))
    for i in range(150):
        status=r.choices(['In Transit','Delivered','Delayed','Processing','Out for Delivery'],[45,30,10,10,5])[0]
        db.add(Shipment(id=f'SHP-{i+2001}',order_id=f'ORD-{i+10001}',origin=f'WH-{i%18+1:03}',destination=f'ST-{i%30+1:03}',carrier=['Delhivery','Blue Dart','TCI Express','VRL Logistics'][i%4],status=status,current_location=CITIES[(i+1)%10][0],expected_delivery=(today+timedelta(days=i%5)).date().isoformat(),actual_delivery=today.date().isoformat() if status=='Delivered' else None,delay=r.randint(2,36) if status=='Delayed' else 0))
    db.flush()
    for i in range(150):
        db.add(ShipmentEvent(id=f'SE-{i}',shipment_id=f'SHP-{i+2001}',status='Dispatched',location=CITIES[i%10][0]))
    for i in range(12):
        prob=round(r.uniform(.4,.95),2); impact=r.randint(40,95); risk=round(prob*impact,1)
        db.add(Disruption(id=f'DIS-{i+1001}',type=['Supplier Failure','Transportation Delay','Inventory Shortage','Port Congestion'][i%4],node_id=f'SUP-{i+1:03}' if i%2==0 else f'WH-{i+1:03}',severity='Critical' if risk>=70 else 'High' if risk>=45 else 'Medium',probability=prob,impact=impact,risk=risk,financial_impact=r.randint(50,400)*1000,status='Resolved' if i>8 else 'Active',root_cause='Simulated operational disruption in the Indian retail network.',created_at=today-timedelta(hours=i*3)))
        db.add(Notification(id=f'NTF-{i+1:03}',title=['Supplier delivery exception','Transport corridor delay','Stock threshold breached','Port congestion detected'][i%4],message=f'{CITIES[i%10][0]} network requires review. Synthetic demonstration event.',severity='High' if i%3 else 'Critical',read=i>5,created_at=today-timedelta(hours=i)))
    db.flush()
    for i in range(3):
        db.add(RecoveryPlan(id=f'RCP-{1001+i}',disruption_id=f'DIS-{1001+i}',strategy=['Alternative supplier','Inventory redistribution','Shipment rerouting'][i],cost=18000+i*12500,recovery_hours=12+i*6,fulfillment=97-i,confidence=88+i,status='Pending approval',data={'affected_inventory':[],'affected_shipments':[],'affected_orders':[],'required_inventory':0,'simulated':True,'mode':'Rule-based'}))
    db.commit()

if __name__=='__main__':
    from app.core.database import Base,engine,SessionLocal
    Base.metadata.create_all(engine)
    with SessionLocal() as db: seed(db)
    print('Deterministic demo data ready.')
