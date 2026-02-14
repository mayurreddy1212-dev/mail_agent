from fastapi import FastAPI
from app.database import engine
from app.routers import auth,employees
from app.models import Base

app = FastAPI()

@app.get('/')
async def root():
    return {"STATUS": "OK"}

Base.metadata.create_all(bind=engine)

app.include_router(auth.router)
app.include_router(employees.router)
