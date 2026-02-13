from fastapi import FastAPI
from app.database import engine
from app import models
from app.routers import auth,employees

app = FastAPI()

@app.get('/')
async def root():
    return {"STATUS": "OK"}

models.Base.metadata.create_all(bind=engine)

app.include_router(auth.router)
app.include_router(employees.router)
