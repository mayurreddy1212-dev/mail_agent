# Imports

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette import status
from typing import Annotated
from pydantic import BaseModel, Field, EmailStr

from app.database import SessionLocal
from app.models import Employee
from app.routers.auth import get_current_user

# Email + AI
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from dotenv import load_dotenv
load_dotenv()

# Router Config

router = APIRouter(
    prefix="/employee",
    tags=["Employees"]
)


# Database Dependency

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]
admin_dependency = Annotated[dict, Depends(get_current_user)]


# Environment Config

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


# Pydantic Schemas

class EmployeeRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    designation: str = Field(..., min_length=2, max_length=50)
    salary: int = Field(..., gt=10000, lt=500000)
    phone_no: str = Field(..., min_length=10, max_length=15)
    address: str = Field(..., min_length=5, max_length=255)
    email: EmailStr
    is_active: bool = True


class EmployeeResponse(EmployeeRequest):
    id: int

    class Config:
        from_attributes = True


# Email Utilities

def send_email(to_email: str, subject: str, body: str):
    msg = MIMEMultipart()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)


def generate_email_content(instruction: str) -> str:
    prompt = ChatPromptTemplate.from_template(
        "Write a professional HR welcome email for MR Developers based on the instruction below.\n\n"
        "The email must clearly mention that the company name is MR Developers and that the higher authority and sender is Mayur.\n\n"
        "{instruction}\n\n"
        "Email:"
    )

    llm = ChatGroq(
        model="llama-3.1-8b-instant",
        groq_api_key=GROQ_API_KEY
    )

    response = llm.invoke(
        prompt.format_prompt(instruction=instruction).to_messages()
    )

    return response.content


# Routes

# Get All Employees
@router.get("/", response_model=list[EmployeeResponse])
def get_all_employees(db: db_dependency):
    return db.query(Employee).all()


# Get Employee By ID
@router.get("/{id}", response_model=EmployeeResponse)
def get_employee_by_id(id: int, db: db_dependency):
    employee = db.query(Employee).filter(Employee.id == id).first()

    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    return employee


# Create Employee + Auto AI Welcome Email
@router.post("/", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
def create_employee(
    employee_request: EmployeeRequest,
    db: db_dependency,
    admin: admin_dependency
):
    if admin is None:
        raise HTTPException(status_code=401, detail="Authentication Failed")

    # Prevent duplicate email
    existing = db.query(Employee).filter(Employee.email == employee_request.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Employee with this email already exists")

    # Save employee
    new_employee = Employee(**employee_request.model_dump())
    db.add(new_employee)
    db.commit()
    db.refresh(new_employee)

    # AI Welcome Email
    try:
        instruction = (
            f"Write a warm professional welcome email to {new_employee.name}, "
            f"who has joined as a {new_employee.designation}. "
            f"Mention growth opportunities and company culture."
        )

        body = generate_email_content(instruction)

        send_email(
            new_employee.email,
            "Welcome to the Company ",
            body
        )

    except Exception as e:
        print("Email failed:", e)

    return new_employee


# Update Employee
@router.put("/{id}", response_model=EmployeeResponse)
def update_employee(
    id: int,
    employee_request: EmployeeRequest,
    db: db_dependency,
    admin: admin_dependency
):
    if admin is None:
        raise HTTPException(status_code=401, detail="Authentication Failed")

    employee = db.query(Employee).filter(Employee.id == id).first()

    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    for key, value in employee_request.model_dump().items():
        setattr(employee, key, value)

    db.commit()
    db.refresh(employee)

    return employee


# Delete Employee
@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_employee(
    id: int,
    db: db_dependency,
    admin: admin_dependency
):
    if admin is None:
        raise HTTPException(status_code=401, detail="Authentication Failed")

    employee = db.query(Employee).filter(Employee.id == id).first()

    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    db.delete(employee)
    db.commit()
