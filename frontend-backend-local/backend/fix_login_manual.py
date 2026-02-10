import re

with open('main.py', 'r') as f:
    content = f.read()

# Find the login endpoint and fix it
old_login = '''    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or not security.verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail='Invalid credentials')
    if not user.is_verified:
        raise HTTPException(status_code=403, detail='Email not verified')'''

new_login = '''    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail='Email not registered')
    if not security.verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail='Invalid password')
    if not user.is_verified:
        raise HTTPException(status_code=403, detail='Email not verified. Please check your email for the verification link.')'''

if old_login in content:
    content = content.replace(old_login, new_login)
    with open('main.py', 'w') as f:
        f.write(content)
    print("✅ Fixed login validation logic")
else:
    print("❌ Could not find login section")
