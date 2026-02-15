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

class BulkEmailRequest(BaseModel):
    subject: str
    instruction: str

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

def generate_email_content(instruction: str) -> str:
    prompt = ChatPromptTemplate.from_template(
        "You are a professional HR communication specialist.\n\n"
        "Write a polished, warm, and professional welcome email for a new employee joining MR Developers.\n\n"
        "Requirements:\n"
        "- The company name must be clearly mentioned as MR Developers.\n"
        "- The email must be written from Mayur, Founder & CEO of MR Developers.\n"
        "- Maintain a confident, inspiring, and leadership tone.\n"
        "- Highlight company culture, growth opportunities, professionalism, and long-term vision.\n"
        "- Keep it concise but impactful.\n"
        "- Format properly with greeting, body paragraphs, and professional signature.\n\n"
        "{instruction}\n\n"
        "Generate only the final email content."
    )


    llm = ChatGroq(
        model="llama-3.1-8b-instant",
        groq_api_key=GROQ_API_KEY
    )

    response = llm.invoke(
        prompt.format_prompt(instruction=instruction).to_messages()
    )

    return response.content

def send_welcome_email(new_employee: Employee):
    try:
        instruction = (
            f"The employee name is {new_employee.name}. "
            f"They have joined MR Developers as a {new_employee.designation}. "
            f"Make the email welcoming, motivational, and encouraging. "
            f"Emphasize teamwork, excellence, innovation, and future growth within the organization."
        )

        body = generate_email_content(instruction)

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

@router.post("/{id}/send-email", status_code=status.HTTP_200_OK)
def send_email_to_employee(
    id: int,
    email_request: EmailRequest,
    background_tasks: BackgroundTasks,
    db: db_dependency,
    admin: admin_dependency
):
    if admin is None:
        raise HTTPException(status_code=401, detail="Authentication Failed")

    employee = db.query(Employee).filter(Employee.id == id).first()

    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    def background_email_task():
        try:
            body = generate_email_content(email_request.instruction)
            send_email(
                employee.email,
                email_request.subject,
                body
            )
        except Exception as e:
            print("Email failed:", e)

    background_tasks.add_task(background_email_task)

    return {"message": "Email is being sent"}

@router.post("/send-bulk-email", status_code=status.HTTP_200_OK)
def send_bulk_email(
    email_request: BulkEmailRequest,
    background_tasks: BackgroundTasks,
    db: db_dependency,
    admin: admin_dependency
):
    if admin is None:
        raise HTTPException(status_code=401, detail="Authentication Failed")

    employees = db.query(Employee).filter(Employee.is_active == True).all()

    if not employees:
        raise HTTPException(status_code=404, detail="No active employees found")

    def background_bulk_task():
        try:
            body = generate_email_content(email_request.instruction)

            for employee in employees:
                try:
                    send_email(
                        employee.email,
                        email_request.subject,
                        body
                    )
                except Exception as e:
                    print(f"Failed to send to {employee.email}:", e)

        except Exception as e:
            print("Bulk email generation failed:", e)

    background_tasks.add_task(background_bulk_task)

    return {"message": f"Bulk email is being sent to {len(employees)} employees"}
