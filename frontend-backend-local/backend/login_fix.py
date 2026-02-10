# Read the file
with open('main.py', 'r') as f:
    lines = f.readlines()

# Find and replace the login function logic
new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    
    # Look for the login function and fix the logic
    if 'user = db.query(models.User).filter(models.User.email == email).first()' in line:
        # Replace the next 12 lines with corrected logic
        new_lines.append(line)  # keep the user query line
        i += 1
        
        # Skip old if statements and replace with new ones
        while i < len(lines) and 'return {' not in lines[i]:
            i += 1
        
        # Insert new logic before return
        new_logic = '''    if not user:
        raise HTTPException(status_code=401, detail='Email not registered')
    if not security.verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail='Invalid password')
    if not user.is_verified:
        raise HTTPException(status_code=403, detail='Email not verified. Please check your email for verification link.')
    # update last login
    user.last_login = datetime.utcnow()
    db.commit()
    # create tokens
    access = security.create_access_token(user.email, role=user.role)
    refresh, jti, exp = security.create_refresh_token(user.email)
    rt = models.RefreshToken(jti=jti, user_id=user.id, expires_at=exp)
    db.add(rt)
    db.commit()
    '''
        new_lines.append(new_logic)
        # Now add the return statement
        while i < len(lines) and 'return {' not in lines[i]:
            i += 1
        if i < len(lines):
            new_lines.append(lines[i])  # return statement
            i += 1
    else:
        new_lines.append(line)
        i += 1

# Write back
with open('main.py', 'w') as f:
    f.writelines(new_lines)

print("✅ Fixed login logic to explicitly check: email exists → password matches → email verified")
