from app.database import Base
from sqlalchemy import Integer, Column, String, Boolean, CheckConstraint

class Admin(Base):
    __tablename__ = "admin"

    id = Column(Integer, primary_key=True, index=True)
    emp_code = Column(String(6), unique=True, nullable=False)
    name = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(100), nullable=False)

class Employee(Base):
    __tablename__ = "employee"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    designation = Column(String(50), nullable=False)
    salary = Column(Integer, nullable=False)
    phone_no = Column(String(15), nullable=False, unique=True)
    address = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "salary >= 10000 AND salary <= 500000",
            name="salary_range"
        )
    )
