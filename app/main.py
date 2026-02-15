from fastapi import FastAPI
from app.database import engine
from app.routers import auth,employees
from app.models import Base
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://ems-frontend-pi-five.vercel.app"],  #deployment
    # allow_origins=["http://localhost:5173"],    #development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get('/')
async def root():
    return {"STATUS": "OK"}

Base.metadata.create_all(bind=engine)

app.include_router(auth.router)
app.include_router(employees.router)
