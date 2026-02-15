from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from starlette import status
from typing import Annotated
from pydantic import BaseModel, Field, EmailStr

from app.database import SessionLocal
from app.models import Employee
from app.routers.auth import get_current_user

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(
    prefix="/employee",
    tags=["Employees"]
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]
admin_dependency = Annotated[dict, Depends(get_current_user)]

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

llm = ChatGroq(
    model="llama-3.1-8b-instant",
    groq_api_key=GROQ_API_KEY
)

welcome_prompt = ChatPromptTemplate.from_template(
    "You are a professional HR communication specialist.\n\n"
    "Write a polished, warm, and professional welcome email for a new employee joining MR Developers.\n\n"
    "Requirements:\n"
    "- The company name must be clearly mentioned as MR Developers.\n"
    "- The email must be written from Mayur, Founder & CEO of MR Developers.\n"
    "- Maintain a confident, inspiring, and leadership tone.\n"
    "- Highlight company culture, growth opportunities, professionalism, and long-term vision.\n"
    "- Start strictly with a proper greeting using the provided employee name.\n"
    "- Do NOT use placeholders like [Employee Name].\n"
    "- Format properly with greeting, body paragraphs, and professional signature.\n\n"
    "{instruction}\n\n"
    "Generate only the final email content."
)

general_prompt = ChatPromptTemplate.from_template(
    "You are a professional HR communication specialist at MR Developers.\n\n"
    "Generate a professional email body strictly aligned with the subject provided.\n"
    "Do NOT generate or modify the subject.\n\n"
    "Subject: {subject}\n\n"
    "Requirements:\n"
    "- Start strictly with a proper greeting using the provided employee name.\n"
    "- Do NOT use placeholders like [Employee Name].\n"
    "- The tone must align with the subject.\n"
    "- The email must be signed by Mayur, Founder & CEO, MR Developers.\n\n"
    "{instruction}\n\n"
    "Generate only the email body."
)

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

class EmailRequest(BaseModel):
    subject: str
    instruction: str
    employee_ids: list[int]

def send_email(to_email: str, subject: str, body: str):
    msg = MIMEMultipart()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)

def generate_welcome_email_content(employee: Employee) -> str:
    instruction = (
        f"Start the email with: Dear {employee.name},\n\n"
        f"{employee.name} has joined MR Developers as {employee.designation}. "
        f"Make the email welcoming, motivational, and encouraging. "
        f"Emphasize teamwork, excellence, innovation, and long-term growth."
    )

    response = llm.invoke(
        welcome_prompt.format_prompt(
            instruction=instruction
        ).to_messages()
    )

    return response.content

def generate_general_email_content(employee: Employee, subject: str, instruction: str) -> str:
    full_instruction = (
        f"Start the email with: Dear {employee.name},\n\n"
        f"{instruction}"
    )

    response = llm.invoke(
        general_prompt.format_prompt(
            subject=subject,
            instruction=full_instruction
        ).to_messages()
    )

    return response.content

def send_welcome_email(new_employee: Employee):
    try:
        body = generate_welcome_email_content(new_employee)

        send_email(
            new_employee.email,
            "Welcome to the Company",
            body
        )
    except Exception as e:
        print("Email failed:", e)

@router.get("/", response_model=list[EmployeeResponse])
def get_all_employees(db: db_dependency):
    return db.query(Employee).all()

@router.get("/{id}", response_model=EmployeeResponse)
def get_employee_by_id(id: int, db: db_dependency):
    employee = db.query(Employee).filter(Employee.id == id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee

@router.post("/", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
def create_employee(
    employee_request: EmployeeRequest,
    background_tasks: BackgroundTasks,
    db: db_dependency,
    admin: admin_dependency
):
    if admin is None:
        raise HTTPException(status_code=401, detail="Authentication Failed")

    existing = db.query(Employee).filter(Employee.email == employee_request.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Employee with this email already exists")

    new_employee = Employee(**employee_request.model_dump())
    db.add(new_employee)
    db.commit()
    db.refresh(new_employee)

    background_tasks.add_task(send_welcome_email, new_employee)

    return new_employee

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

@router.delete("/{id}", status_code=status.HTTP_200_OK)
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

    return {"message": "Employee deleted successfully"}

@router.post("/send-email")
def send_selected_email(
    data: EmailRequest,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None
):
    employees = db.query(Employee).filter(
        Employee.id.in_(data.employee_ids)
    ).all()

    if not employees:
        raise HTTPException(status_code=404, detail="No employees found")

    for emp in employees:
        body = generate_general_email_content(
            emp,
            data.subject,
            data.instruction
        )

        background_tasks.add_task(
            send_email,
            emp.email,
            data.subject,
            body
        )

    return {"message": "Emails are being sent"}
