from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List
import sqlalchemy
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import os
from datetime import datetime

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "oracle+cx_oracle://user:password@localhost:1521/xe")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Security
security = HTTPBearer()

# Models
class Account(Base):
    __tablename__ = "accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    account_number = Column(String(20), unique=True, index=True, nullable=False)
    customer_id = Column(Integer, nullable=False)
    balance = Column(Float, default=0.0)
    account_type = Column(String(20), nullable=False)  # savings, checking, etc.
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Pydantic models
class AccountCreate(BaseModel):
    customer_id: int
    account_type: str
    initial_deposit: float = 0.0

class AccountResponse(BaseModel):
    id: int
    account_number: str
    customer_id: int
    balance: float
    account_type: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class BalanceUpdate(BaseModel):
    amount: float

# Create tables
Base.metadata.create_all(bind=engine)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    # In a real app, validate the token here
    # For now, we'll just return a mock user
    return {"user_id": 1, "username": "testuser"}

# App
app = FastAPI(title="Account Service", description="Service for managing bank accounts")

# Routes
@app.post("/accounts/", response_model=AccountResponse)
def create_account(account: AccountCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    # Generate account number (simplified)
    import random
    account_number = f"ACC{random.randint(10000000, 99999999)}"
    
    db_account = Account(
        account_number=account_number,
        customer_id=account.customer_id,
        balance=account.initial_deposit,
        account_type=account.account_type
    )
    db.add(db_account)
    db.commit()
    db.refresh(db_account)
    return db_account

@app.get("/accounts/{account_number}", response_model=AccountResponse)
def get_account(account_number: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    account = db.query(Account).filter(Account.account_number == account_number).first()
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return account

@app.put("/accounts/{account_number}/deposit")
def deposit(account_number: str, balance_update: BalanceUpdate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    account = db.query(Account).filter(Account.account_number == account_number).first()
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    
    account.balance += balance_update.amount
    account.updated_at = datetime.utcnow()
    db.commit()
    return {"message": "Deposit successful", "new_balance": account.balance}

@app.put("/accounts/{account_number}/withdraw")
def withdraw(account_number: str, balance_update: BalanceUpdate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    account = db.query(Account).filter(Account.account_number == account_number).first()
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    
    if account.balance < balance_update.amount:
        raise HTTPException(status_code=400, detail="Insufficient funds")
    
    account.balance -= balance_update.amount
    account.updated_at = datetime.utcnow()
    db.commit()
    return {"message": "Withdrawal successful", "new_balance": account.balance}

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "account-service"}