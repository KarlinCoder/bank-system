from fastapi import FastAPI, HTTPException, Depends, status, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List
import sqlalchemy
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import os
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "oracle+cx_oracle://user:password@localhost:1521/xe")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Security
security = HTTPBearer()

# Models
class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)  # In a real system, this would be a foreign key to users table
    type = Column(String(50), nullable=False)  # email, sms, push
    recipient = Column(String(255), nullable=False)
    subject = Column(String(255))
    message = Column(String(1000), nullable=False)
    status = Column(String(20), default="pending")  # pending, sent, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)

# Pydantic models
class NotificationCreate(BaseModel):
    user_id: int
    type: str  # email, sms, push
    recipient: str
    subject: Optional[str] = None
    message: str

class NotificationResponse(BaseModel):
    id: int
    user_id: int
    type: str
    recipient: str
    subject: Optional[str]
    message: str
    status: str
    created_at: datetime
    sent_at: Optional[datetime]

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
app = FastAPI(title="Notification Service", description="Service for sending notifications")

# Email configuration (in production, use environment variables and a proper email service)
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "your-email@gmail.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "your-password")

def send_email(to_email: str, subject: str, body: str):
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USERNAME
        msg['To'] = to_email
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        text = msg.as_string()
        server.sendmail(SMTP_USERNAME, to_email, text)
        server.quit()
        return True
    except Exception as e:
        logging.error(f"Failed to send email: {e}")
        return False

def send_sms(to_number: str, message: str):
    # In a real system, integrate with an SMS provider like Twilio
    # For now, we'll just log and return success
    logging.info(f"SMS sent to {to_number}: {message}")
    return True

def send_push_notification(user_id: int, message: str):
    # In a real system, integrate with a push notification service (Firebase, etc.)
    logging.info(f"Push notification sent to user {user_id}: {message}")
    return True

# Background task to send notifications
def process_notification(notification_id: int, db: Session):
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notification:
        return

    success = False
    if notification.type == "email":
        success = send_email(notification.recipient, notification.subject or "Notification", notification.message)
    elif notification.type == "sms":
        success = send_sms(notification.recipient, notification.message)
    elif notification.type == "push":
        success = send_push_notification(notification.user_id, notification.message)
    else:
        logging.error(f"Unknown notification type: {notification.type}")

    if success:
        notification.status = "sent"
        notification.sent_at = datetime.utcnow()
    else:
        notification.status = "failed"

    db.commit()

# Routes
@app.post("/notifications/", response_model=NotificationResponse)
def create_notification(notification: NotificationCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    db_notification = Notification(
        user_id=notification.user_id,
        type=notification.type,
        recipient=notification.recipient,
        subject=notification.subject,
        message=notification.message
    )
    db.add(db_notification)
    db.commit()
    db.refresh(db_notification)

    # Process notification in background
    background_tasks.add_task(process_notification, db_notification.id, db)

    return db_notification

@app.get("/notifications/{notification_id}", response_model=NotificationResponse)
def get_notification(notification_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification

@app.get("/notifications/user/{user_id}", response_model=List[NotificationResponse])
def get_user_notifications(user_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    notifications = db.query(Notification).filter(Notification.user_id == user_id).order_by(Notification.created_at.desc()).all()
    return notifications

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "notification-service"}