import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from dotenv import load_dotenv

load_dotenv()
url = os.getenv('DATABASE_URL', 'sqlite:///./supplytwin.db')
if os.getenv('VERCEL') and not os.getenv('DATABASE_URL'):
    raise RuntimeError('DATABASE_URL is required for durable hosted persistence')
if url.startswith('postgres://'):
    url = url.replace('postgres://', 'postgresql+psycopg://', 1)
elif url.startswith('postgresql://'):
    url = url.replace('postgresql://', 'postgresql+psycopg://', 1)
engine = create_engine(url, connect_args={'check_same_thread': False} if url.startswith('sqlite') else {}, pool_pre_ping=True)
if url.startswith('sqlite'):
    @event.listens_for(engine, 'connect')
    def sqlite_constraints(conn, _):
        conn.execute('PRAGMA foreign_keys=ON')
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
class Base(DeclarativeBase):
    pass
def get_db():
    with SessionLocal() as db:
        yield db
