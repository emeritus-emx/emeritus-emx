from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import uuid
import os

from database import SessionLocal, init_db
import models
import schemas
import security
from email_utils import send_verification_email, send_password_reset_email

# Initialize DB
init_db()

app = FastAPI(title='NUESA Backend (DB + Auth)')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl='auth/login')

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Helper to get current user
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = security.decode_token(token)
        email = payload.get('sub')
        if not email:
            raise HTTPException(status_code=401, detail='Invalid token')
        user = db.query(models.User).filter(models.User.email == email).first()
        if not user:
            raise HTTPException(status_code=404, detail='User not found')
        return user
    except Exception as e:
        raise HTTPException(status_code=401, detail='Could not validate credentials')

# Admin check
def require_admin(user: models.User = Depends(get_current_user)):
    if user.role != 'admin':
        raise HTTPException(status_code=403, detail='Admin access required')
    return user

# --- Auth endpoints ---
@app.post('/auth/register', response_model=schemas.UserOut)
def register(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail='Email already registered')
    hashed = security.get_password_hash(payload.password)
    user = models.User(email=payload.email, name=payload.name, hashed_password=hashed)
    db.add(user)
    db.commit()
    db.refresh(user)
    # create email verification token
    token = str(uuid.uuid4())
    ev = models.EmailVerification(token=token, user_id=user.id, expires_at=datetime.utcnow() + timedelta(days=1))
    db.add(ev)
    db.commit()
    send_verification_email(user.email, token)
    return user

@app.get('/auth/verify')
def verify_email(token: str, db: Session = Depends(get_db)):
    ev = db.query(models.EmailVerification).filter(models.EmailVerification.token == token).first()
    if not ev or ev.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail='Invalid or expired verification token')
    user = db.query(models.User).get(ev.user_id)
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    user.is_verified = True
    db.delete(ev)
    db.commit()
    return {'message': 'Email verified'}

@app.post('/auth/login', response_model=schemas.Token)
async def login(form: Request, db: Session = Depends(get_db)):
    data = None
    try:
        data = await form.json()
    except Exception:
        data = await form.form()
    email = data.get('email')
    password = data.get('password')
    if not email or not password:
        raise HTTPException(status_code=400, detail='Email and password required')
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail='Email not registered')
    if not security.verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail='Invalid password')
    if not user.is_verified:
        raise HTTPException(status_code=403, detail='Email not verified. Please check your email for the verification link.')
    # update last login
    user.last_login = datetime.utcnow()
    db.commit()
    # create tokens
    access = security.create_access_token(user.email, role=user.role)
    refresh, jti, exp = security.create_refresh_token(user.email)
    rt = models.RefreshToken(jti=jti, user_id=user.id, expires_at=exp)
    db.add(rt)
    db.commit()
    return {'access_token': access, 'refresh_token': refresh, 'token_type': 'bearer'}

@app.post('/auth/refresh', response_model=schemas.Token)
async def refresh_token_endpoint(request: Request, db: Session = Depends(get_db)):
    data = None
    try:
        data = await request.json()
    except Exception:
        data = await request.form()
    token = data.get('refresh_token')
    if not token:
        raise HTTPException(status_code=400, detail='refresh_token required')
    try:
        payload = security.decode_token(token)
        jti = payload.get('jti')
        email = payload.get('sub')
    except Exception:
        raise HTTPException(status_code=401, detail='Invalid refresh token')
    rt = db.query(models.RefreshToken).filter(models.RefreshToken.jti == jti).first()
    if not rt or rt.revoked or rt.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail='Refresh token revoked or expired')
    # issue new access token
    user = db.query(models.User).get(rt.user_id)
    access = security.create_access_token(user.email, role=user.role)
    return {'access_token': access, 'refresh_token': token, 'token_type': 'bearer'}

@app.post('/auth/logout')
async def logout(request: Request, db: Session = Depends(get_db)):
    data = None
    try:
        data = await request.json()
    except Exception:
        data = await request.form()
    token = data.get('refresh_token')
    if not token:
        raise HTTPException(status_code=400, detail='refresh_token required')
    try:
        payload = security.decode_token(token)
        jti = payload.get('jti')
    except Exception:
        raise HTTPException(status_code=400, detail='Invalid token')
    rt = db.query(models.RefreshToken).filter(models.RefreshToken.jti == jti).first()
    if rt:
        rt.revoked = True
        db.commit()
    return {'message': 'Logged out'}

# Password reset
@app.post('/auth/password-reset-request')
def password_reset_request(payload: dict, db: Session = Depends(get_db)):
    email = payload.get('email')
    if not email:
        raise HTTPException(status_code=400, detail='Email required')
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        return {'message': 'If that account exists, a reset link has been sent.'}
    token = str(uuid.uuid4())
    pr = models.PasswordReset(token=token, user_id=user.id, expires_at=datetime.utcnow() + timedelta(hours=2))
    db.add(pr)
    db.commit()
    send_password_reset_email(email, token)
    return {'message': 'If that account exists, a reset link has been sent.'}

@app.post('/auth/password-reset')
def password_reset(payload: dict, db: Session = Depends(get_db)):
    token = payload.get('token')
    new_password = payload.get('password')
    if not token or not new_password:
        raise HTTPException(status_code=400, detail='token and password required')
    pr = db.query(models.PasswordReset).filter(models.PasswordReset.token == token).first()
    if not pr or pr.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail='Invalid or expired token')
    user = db.query(models.User).get(pr.user_id)
    user.hashed_password = security.get_password_hash(new_password)
    db.delete(pr)
    db.commit()
    return {'message': 'Password has been reset'}


# --- Password Helpers ---
@app.post('/auth/verify-password')
def verify_password_on_login(payload: dict, user: models.User = Depends(get_current_user)):
    """
    Verify if a plain-text password matches the logged-in user's hashed password.
    Useful for confirming password before sensitive operations (e.g., profile changes).
    """
    plain_password = payload.get('password')
    if not plain_password:
        raise HTTPException(status_code=400, detail='Password required')
    if not security.verify_password(plain_password, user.hashed_password):
        raise HTTPException(status_code=401, detail='Incorrect password')
    return {'message': 'Password verified', 'user_id': user.id}

@app.post('/auth/change-password')
def change_password(payload: dict, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Change password for authenticated user.
    Requires current password and new password.
    """
    current_password = payload.get('current_password')
    new_password = payload.get('new_password')
    
    if not current_password or not new_password:
        raise HTTPException(status_code=400, detail='current_password and new_password required')
    
    if not security.verify_password(current_password, user.hashed_password):
        raise HTTPException(status_code=401, detail='Current password is incorrect')
    
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail='New password must be at least 8 characters')
    
    user.hashed_password = security.get_password_hash(new_password)
    db.commit()
    return {'message': 'Password changed successfully'}


# --- Admin routes ---
@app.get('/admin/users', response_model=list[schemas.UserOut])
def admin_list_users(db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    users = db.query(models.User).all()
    return users

# --- Admin Dashboard ---
@app.get('/admin/dashboard/stats')
def admin_dashboard_stats(db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    """System overview stats for admin"""
    total_users = db.query(models.User).count()
    verified_users = db.query(models.User).filter(models.User.is_verified == True).count()
    total_scholarships = db.query(models.Scholarship).count()
    active_users = db.query(models.User).filter(models.User.last_login.isnot(None)).count()
    
    return {
        'total_users': total_users,
        'verified_users': verified_users,
        'unverified_users': total_users - verified_users,
        'active_users': active_users,
        'total_scholarships': total_scholarships,
        'system_health': 'ok'
    }

@app.get('/admin/users/search')
def admin_search_users(q: str, db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    """Search users by email or name"""
    users = db.query(models.User).filter(
        (models.User.email.ilike(f'%{q}%')) | (models.User.name.ilike(f'%{q}%'))
    ).all()
    return users

@app.put('/admin/users/{user_id}/role')
def admin_update_user_role(user_id: int, payload: dict, db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    """Update user role (student/sponsor/admin)"""
    user = db.query(models.User).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    new_role = payload.get('role')
    if new_role not in ('student', 'sponsor', 'admin'):
        raise HTTPException(status_code=400, detail='Invalid role')
    user.role = new_role
    db.commit()
    return {'message': f'User role updated to {new_role}'}

@app.put('/admin/users/{user_id}/toggle-active')
def admin_toggle_user_active(user_id: int, db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    """Enable/disable user account"""
    user = db.query(models.User).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    user.is_active = not user.is_active
    db.commit()
    return {'user_id': user.id, 'is_active': user.is_active}

@app.delete('/admin/users/{user_id}')
def admin_delete_user(user_id: int, db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    """Delete user (and associated data)"""
    user = db.query(models.User).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    db.delete(user)
    db.commit()
    return {'message': 'User deleted'}

@app.get('/admin/scholarships')
def admin_list_scholarships(db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    """Admin view all scholarships with creator info"""
    scholarships = db.query(models.Scholarship).all()
    return scholarships

@app.get('/admin/scholarships/by-provider/{provider}')
def admin_filter_by_provider(provider: str, db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    """Filter scholarships by provider"""
    scholarships = db.query(models.Scholarship).filter(models.Scholarship.provider.ilike(f'%{provider}%')).all()
    return scholarships

@app.post('/admin/scholarships/{scholarship_id}/approve')
def admin_approve_scholarship(scholarship_id: int, db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    """Approve/feature a scholarship"""
    s = db.query(models.Scholarship).get(scholarship_id)
    if not s:
        raise HTTPException(status_code=404, detail='Scholarship not found')
    # You could add an 'approved' or 'featured' column to track this
    return {'message': f'Scholarship {scholarship_id} approved'}

@app.delete('/admin/scholarships/{scholarship_id}')
def admin_delete_scholarship(scholarship_id: int, db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    """Admin delete scholarship"""
    s = db.query(models.Scholarship).get(scholarship_id)
    if not s:
        raise HTTPException(status_code=404, detail='Scholarship not found')
    db.delete(s)
    db.commit()
    return {'message': 'Scholarship deleted'}

@app.get('/admin/activity-log')
def admin_activity_log(limit: int = 100, db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    """Recent user activity (logins, creations)"""
    # Fetch recent users by last_login
    recent = db.query(models.User).filter(models.User.last_login.isnot(None)).order_by(models.User.last_login.desc()).limit(limit).all()
    return [{'email': u.email, 'name': u.name, 'last_login': u.last_login, 'role': u.role} for u in recent]



# --- Scholarships CRUD ---
@app.post('/scholarships', response_model=schemas.ScholarshipOut)
def create_scholarship(payload: schemas.ScholarshipCreate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    # only verified users can create; admin or sponsor
    if user.role not in ('admin', 'sponsor'):
        raise HTTPException(status_code=403, detail='Insufficient privileges')
    s = models.Scholarship(**payload.model_dump(), created_by=user.id)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s

@app.get('/scholarships', response_model=list[schemas.ScholarshipOut])
def list_scholarships(db: Session = Depends(get_db)):
    items = db.query(models.Scholarship).all()
    return items

@app.get('/scholarships/{scholarship_id}', response_model=schemas.ScholarshipOut)
def get_scholarship(scholarship_id: int, db: Session = Depends(get_db)):
    s = db.query(models.Scholarship).get(scholarship_id)
    if not s:
        raise HTTPException(status_code=404, detail='Not found')
    return s

@app.put('/scholarships/{scholarship_id}', response_model=schemas.ScholarshipOut)
def update_scholarship(scholarship_id: int, payload: schemas.ScholarshipCreate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    s = db.query(models.Scholarship).get(scholarship_id)
    if not s:
        raise HTTPException(status_code=404, detail='Not found')
    if user.role != 'admin' and s.created_by != user.id:
        raise HTTPException(status_code=403, detail='Forbidden')
    for k, v in payload.model_dump().items():
        setattr(s, k, v)
    db.commit()
    db.refresh(s)
    return s

@app.delete('/scholarships/{scholarship_id}')
def delete_scholarship(scholarship_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    s = db.query(models.Scholarship).get(scholarship_id)
    if not s:
        raise HTTPException(status_code=404, detail='Not found')
    if user.role != 'admin' and s.created_by != user.id:
        raise HTTPException(status_code=403, detail='Forbidden')
    db.delete(s)
    db.commit()
    return {'message': 'Deleted'}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run('main:app', host='0.0.0.0', port=int(os.getenv('PORT', '8000')), reload=True)
