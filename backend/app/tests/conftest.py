import os,tempfile

# Configure isolation before any test module imports the application/engine.
os.environ['DATABASE_URL']='sqlite:///'+tempfile.mktemp(suffix='.db')
os.environ['JWT_SECRET']='test-only-cryptographically-long-secret-1234567890'
os.environ['DEMO_MODE']='true'
os.environ.pop('VERCEL',None)
