from fastapi import Depends, HTTPException, Path,APIRouter
from app.models import Employee
from app.database import engine, SessionLocal
from sqlalchemy.orm import Session
from typing import Annotated
from starlette import status
from pydantic import BaseModel, Field
from app.routers.auth import get_current_user

router = APIRouter(
    tags=["Employees"]
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]
admin_dependancy=Annotated[dict,Depends(get_current_user)]

class EmployeeRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    designation: str = Field(..., min_length=2, max_length=50)
    salary: int = Field(..., gt=10000, lt=500000)
    phone_no: str = Field(..., min_length=10, max_length=15)    
    address: str = Field(..., min_length=5, max_length=255)
    is_active: bool = True

@router.get('/employees')
async def all_employees(db: db_dependency):
    return db.query(Employee).all()

@router.get("/employee/{id}", status_code=status.HTTP_200_OK)
async def search_employee_by_id(db: db_dependency, id: int):
    employee = db.query(Employee).filter(Employee.id == id).first()
    if employee is not None:
        return employee
    raise HTTPException(status_code=404, detail='Employee not found')

@router.post("/employee", status_code=status.HTTP_201_CREATED)
async def create_employee(
    db: db_dependency,
    admin: admin_dependancy,
    employee_request: EmployeeRequest
):
    if admin is None:
        raise HTTPException(status_code=401, detail="Authentication Failed")

    employee = Employee(**employee_request.model_dump())
    db.add(employee)
    db.commit()
    
    return employee



@router.put("/employee/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_employee(db: db_dependency, admin:admin_dependancy, id: int, employee_request: EmployeeRequest):
    if admin is None:
        raise HTTPException(status_code=401,detail="Authentication Failed")
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

@router.delete("/employee/{id}",status_code=status.HTTP_204_NO_CONTENT)
async def delete_employee(db:db_dependency, admin:admin_dependancy, id:int):
    if admin is None:
        raise HTTPException(status_code=401,detail="Authentication Failed")
    employee=db.query(Employee).filter(Employee.id==id).first()
    if employee is None:
        raise HTTPException(status_code=404,detail="employee not found")
    
    db.delete(employee)
    db.commit()