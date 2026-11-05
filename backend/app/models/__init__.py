from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, Boolean, ForeignKey, JSON, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

def now():
    return datetime.now(timezone.utc)

class Role(Base):
    __tablename__ = 'roles'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)

class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String)
    password_hash: Mapped[str] = mapped_column(String)
    role_id: Mapped[str] = mapped_column(ForeignKey('roles.id'), default='analyst')
    session_version: Mapped[int] = mapped_column(Integer, default=0)
    reset_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    reset_expires: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Node(Base):
    __tablename__ = 'supply_chain_nodes'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, index=True)
    type: Mapped[str] = mapped_column(String, index=True)
    city: Mapped[str] = mapped_column(String)
    region: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, default='Operational')
    risk: Mapped[float] = mapped_column(Float, default=15)
    latitude: Mapped[float] = mapped_column(Float, default=0)
    longitude: Mapped[float] = mapped_column(Float, default=0)
    capacity: Mapped[int] = mapped_column(Integer, default=20000)
    reliability: Mapped[float] = mapped_column(Float, default=95)
    lead_time: Mapped[int] = mapped_column(Integer, default=4)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Edge(Base):
    __tablename__ = 'supply_chain_edges'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    source: Mapped[str] = mapped_column(ForeignKey('supply_chain_nodes.id'), index=True)
    target: Mapped[str] = mapped_column(ForeignKey('supply_chain_nodes.id'), index=True)
    status: Mapped[str] = mapped_column(String, default='Active')
    distance: Mapped[float] = mapped_column(Float, default=0)

class Category(Base):
    __tablename__ = 'categories'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)

class Product(Base):
    __tablename__ = 'products'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, index=True)
    sku: Mapped[str] = mapped_column(String, unique=True)
    category_id: Mapped[str] = mapped_column(ForeignKey('categories.id'))
    supplier_id: Mapped[str] = mapped_column(ForeignKey('supply_chain_nodes.id'))
    unit_cost: Mapped[float] = mapped_column(Float)
    daily_demand: Mapped[float] = mapped_column(Float)

class Inventory(Base):
    __tablename__ = 'inventory'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey('products.id'), index=True)
    warehouse_id: Mapped[str] = mapped_column(ForeignKey('supply_chain_nodes.id'), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    reserved: Mapped[int] = mapped_column(Integer, default=0)
    safety_stock: Mapped[int] = mapped_column(Integer, default=100)
    reorder_level: Mapped[int] = mapped_column(Integer, default=300)

class Order(Base):
    __tablename__ = 'orders'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    customer: Mapped[str] = mapped_column(String)
    warehouse_id: Mapped[str] = mapped_column(ForeignKey('supply_chain_nodes.id'))
    status: Mapped[str] = mapped_column(String, index=True)
    value: Mapped[float] = mapped_column(Float)
    quantity: Mapped[int] = mapped_column(Integer)
    risk: Mapped[str] = mapped_column(String, default='Low')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    delivery_date: Mapped[str] = mapped_column(String)

class OrderItem(Base):
    __tablename__ = 'order_items'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey('orders.id'), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey('products.id'))
    quantity: Mapped[int] = mapped_column(Integer)

class Shipment(Base):
    __tablename__ = 'shipments'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey('orders.id'))
    origin: Mapped[str] = mapped_column(ForeignKey('supply_chain_nodes.id'))
    destination: Mapped[str] = mapped_column(ForeignKey('supply_chain_nodes.id'))
    carrier: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, index=True)
    current_location: Mapped[str] = mapped_column(String)
    expected_delivery: Mapped[str] = mapped_column(String)
    actual_delivery: Mapped[str | None] = mapped_column(String, nullable=True)
    delay: Mapped[int] = mapped_column(Integer, default=0)

class Disruption(Base):
    __tablename__ = 'disruptions'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    type: Mapped[str] = mapped_column(String)
    node_id: Mapped[str] = mapped_column(ForeignKey('supply_chain_nodes.id'))
    severity: Mapped[str] = mapped_column(String)
    probability: Mapped[float] = mapped_column(Float)
    impact: Mapped[float] = mapped_column(Float)
    risk: Mapped[float] = mapped_column(Float)
    financial_impact: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String, default='Active')
    root_cause: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Simulation(Base):
    __tablename__ = 'simulations'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    disruption_id: Mapped[str] = mapped_column(ForeignKey('disruptions.id'))
    config: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class RecoveryPlan(Base):
    __tablename__ = 'recovery_plans'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    disruption_id: Mapped[str] = mapped_column(ForeignKey('disruptions.id'))
    strategy: Mapped[str] = mapped_column(String)
    cost: Mapped[float] = mapped_column(Float)
    recovery_hours: Mapped[int] = mapped_column(Integer)
    fulfillment: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String, default='Pending approval')
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class AgentExecution(Base):
    __tablename__ = 'agent_executions'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    agent: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String)
    output: Mapped[dict] = mapped_column(JSON)
    mode: Mapped[str] = mapped_column(String, default='Rule-based')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Notification(Base):
    __tablename__ = 'notifications'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class AuditLog(Base):
    __tablename__ = 'audit_logs'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    action: Mapped[str] = mapped_column(String)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Transaction(Base):
    __tablename__ = 'inventory_transactions'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    inventory_id: Mapped[str] = mapped_column(ForeignKey('inventory.id'))
    quantity: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class ShipmentEvent(Base):
    __tablename__ = 'shipment_events'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    shipment_id: Mapped[str] = mapped_column(ForeignKey('shipments.id'))
    status: Mapped[str] = mapped_column(String)
    location: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class RecoveryAction(Base):
    __tablename__ = 'recovery_actions'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey('recovery_plans.id'))
    action: Mapped[str] = mapped_column(String)
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
