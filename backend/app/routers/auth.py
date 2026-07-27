from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.db.session import get_db
from app.db.models import User
from app.core.security import (
    hash_password, verify_password, create_access_token, get_current_user, require_admin,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class NewUserRequest(BaseModel):
    username: str
    password: str
    role: str = "staff"  # "admin" | "staff"


@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter_by(username=form_data.username, active=True).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    token = create_access_token(user.username, user.role)
    return {"access_token": token, "token_type": "bearer", "role": user.role,
            "username": user.username}


@router.get("/me")
def whoami(current_user: User = Depends(get_current_user)):
    return {"username": current_user.username, "role": current_user.role}


@router.post("/users")
def create_user(payload: NewUserRequest, db: Session = Depends(get_db),
                 _admin: User = Depends(require_admin)):
    """Admin-only — adds a new staff/admin account. There's no public
    self-signup endpoint on purpose; accounts are created by whoever's
    already an admin."""
    existing = db.query(User).filter_by(username=payload.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    user = User(username=payload.username, hashed_password=hash_password(payload.password),
                role=payload.role, active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "username": user.username, "role": user.role}


@router.get("/users")
def list_users(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    users = db.query(User).all()
    return {"users": [{"id": u.id, "username": u.username, "role": u.role, "active": u.active}
                       for u in users]}


@router.post("/users/{user_id}/deactivate")
def deactivate_user(user_id: int, db: Session = Depends(get_db),
                     _admin: User = Depends(require_admin)):
    user = db.query(User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.active = False
    db.commit()
    return {"status": "deactivated", "username": user.username}
