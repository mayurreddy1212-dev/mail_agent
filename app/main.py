from fastapi import FastAPI, Depends, HTTPException, Path
from app.models import Employee
from app.database import engine, SessionLocal
from sqlalchemy.orm import Session
from typing import Annotated
from app import models
from starlette import status
from pydantic import BaseModel, Field

app = FastAPI()

models.Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]

class EmployeeRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    designation: str = Field(..., min_length=2, max_length=50)
    salary: int = Field(..., gt=0, lt=500000)
    phone_no: str = Field(..., min_length=10, max_length=15)
    address: str = Field(..., min_length=5, max_length=255)
    is_active: bool = True

def generate_employee_id(db: Session):
    last_employee = db.query(Employee).order_by(Employee.id.desc()).first()
    if not last_employee:
        return "M00001"
    last_number = int(last_employee.id[1:])
    new_number = last_number + 1
    return f"M{new_number:05d}"

@app.get('/')
async def root():
    return {"status": "OK"}

@app.get('/employees')
async def all_employees(db: db_dependency):
    return db.query(Employee).all()

@app.get("/employee/{id}", status_code=status.HTTP_200_OK)
async def search_employee_by_id(db: db_dependency, id: str):
    employee = db.query(Employee).filter(Employee.id == id).first()
    if employee is not None:
        return employee
    raise HTTPException(status_code=404, detail='Employee not found')

@app.post("/employee", status_code=status.HTTP_201_CREATED)
async def create_employee(db: db_dependency, employee_request: EmployeeRequest):
    new_id = generate_employee_id(db)
    employee = Employee(id=new_id, **employee_request.model_dump())
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee

@app.put("/employee/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_employee(db: db_dependency, id: str, employee_request: EmployeeRequest):
    employee = db.query(Employee).filter(Employee.id == id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail=f"Employee with id {id} not found")
    employee.name = employee_request.name
    employee.designation = employee_request.designation
    employee.salary = employee_request.salary
    employee.phone_no = employee_request.phone_no
    employee.address = employee_request.address
    employee.is_active = employee_request.is_active
    db.commit()
    db.refresh(employee)
    return employee

@app.delete("/employee/{id}",status_code=status.HTTP_204_NO_CONTENT)
async def delete_employee(db:db_dependency,id:str):
    employee=db.query(Employee).filter(Employee.id==id).first()
    if employee is None:
        raise HTTPException(status_code=404,detail="employee not found")
    
    # db.query(Employee).filter(Employee.id==id).delete()
    db.delete(employee)

    db.commit()