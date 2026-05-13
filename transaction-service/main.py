from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List
import sqlalchemy
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
import os
from datetime import datetime
import enum

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "oracle+cx_oracle://user:password@localhost:1521/xe")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Security
security = HTTPBearer()

# Enums
class TransactionType(str, enum.Enum):
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER = "transfer"

class TransactionStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"

# Models
class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(String(36), unique=True, index=True, nullable=False)  # UUID
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    transaction_type = Column(Enum(TransactionType), nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(Enum(TransactionStatus), default=TransactionStatus.PENDING)
    description = Column(String(255))
    reference_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)  # For transfers
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    account = relationship("Account", foreign_keys=[account_id])
    reference_account = relationship("Account", foreign_keys=[reference_account_id])

# We'll define Account model here for relationship, but note: in real system, 
# this would be in account-service and we'd use API calls
class Account(Base):
    __tablename__ = "accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    account_number = Column(String(20), unique=True, index=True, nullable=False)
    customer_id = Column(Integer, nullable=False)
    balance = Column(Float, default=0.0)
    account_type = Column(String(20), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Pydantic models
class TransactionCreate(BaseModel):
    account_number: str
    transaction_type: TransactionType
    amount: float
    description: Optional[str] = None
    reference_account_number: Optional[str] = None  # For transfers

class TransactionResponse(BaseModel):
    id: int
    transaction_id: str
    account_number: str
    transaction_type: TransactionType
    amount: float
    status: TransactionStatus
    description: Optional[str]
    reference_account_number: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

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
    return {"user_id": 1, "username": "testuser"}

# App
app = FastAPI(title="Transaction Service", description="Service for managing bank transactions")

# Helper function to get account by account number
def get_account_by_number(db: Session, account_number: str):
    return db.query(Account).filter(Account.account_number == account_number).first()

# Routes
@app.post("/transactions/", response_model=TransactionResponse)
def create_transaction(transaction: TransactionCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    # For deposit/withdrawal
    if transaction.transaction_type in [TransactionType.DEPOSIT, TransactionType.WITHDRAWAL]:
        account = get_account_by_number(db, transaction.account_number)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        if transaction.transaction_type == TransactionType.WITHDRAWAL and account.balance < transaction.amount:
            raise HTTPException(status_code=400, detail="Insufficient funds")
        
        # Create transaction record
        import uuid
        db_transaction = Transaction(
            transaction_id=str(uuid.uuid4()),
            account_id=account.id,
            transaction_type=transaction.transaction_type,
            amount=transaction.amount,
            description=transaction.description,
            status=TransactionStatus.COMPLETED
        )
        
        # Update account balance
        if transaction.transaction_type == TransactionType.DEPOSIT:
            account.balance += transaction.amount
        else:  # WITHDRAWAL
            account.balance -= transaction.amount
        
        account.updated_at = datetime.utcnow()
        
        db.add(db_transaction)
        db.commit()
        db.refresh(db_transaction)
        
        return db_transaction
    
    # For transfer
    elif transaction.transaction_type == TransactionType.TRANSFER:
        if not transaction.reference_account_number:
            raise HTTPException(status_code=400, detail="Reference account number required for transfer")
        
        from_account = get_account_by_number(db, transaction.account_number)
        to_account = get_account_by_number(db, transaction.reference_account_number)
        
        if not from_account:
            raise HTTPException(status_code=404, detail="Source account not found")
        if not to_account:
            raise HTTPException(status_code=404, detail="Destination account not found")
        if from_account.id == to_account.id:
            raise HTTPException(status_code=400, detail="Cannot transfer to same account")
        if from_account.balance < transaction.amount:
            raise HTTPException(status_code=400, detail="Insufficient funds")
        
        # Create transaction records (two entries: one for withdrawal, one for deposit)
        import uuid
        transfer_id = str(uuid.uuid4())
        
        # Withdrawal transaction
        db_transaction_out = Transaction(
            transaction_id=f"{transfer_id}_OUT",
            account_id=from_account.id,
            transaction_type=TransactionType.TRANSFER,
            amount=transaction.amount,
            description=f"Transfer to {to_account.account_number}: {transaction.description or ''}",
            reference_account_id=to_account.id,
            status=TransactionStatus.COMPLETED
        )
        
        # Deposit transaction
        db_transaction_in = Transaction(
            transaction_id=f"{transfer_id}_IN",
            account_id=to_account.id,
            transaction_type=TransactionType.TRANSFER,
            amount=transaction.amount,
            description=f"Transfer from {from_account.account_number}: {transaction.description or ''}",
            reference_account_id=from_account.id,
            status=TransactionStatus.COMPLETED
        )
        
        # Update balances
        from_account.balance -= transaction.amount
        to_account.balance += transaction.amount
        from_account.updated_at = datetime.utcnow()
        to_account.updated_at = datetime.utcnow()
        
        db.add_all([db_transaction_out, db_transaction_in])
        db.commit()
        db.refresh(db_transaction_out)
        
        return db_transaction_out
    
    else:
        raise HTTPException(status_code=400, detail="Invalid transaction type")

@app.get("/transactions/{account_number}", response_model=List[TransactionResponse])
def get_account_transactions(account_number: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    account = get_account_by_number(db, account_number)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    transactions = db.query(Transaction).filter(Transaction.account_id == account.id).order_by(Transaction.created_at.desc()).all()
    return transactions

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "transaction-service"}