from datetime import datetime

# Very small email sender for development: prints verification/reset links to console.
def send_verification_email(email: str, token: str):
    link = f"http://localhost:8000/auth/verify?token={token}"
    print(f"[Email] To: {email} — Verification link: {link} — at {datetime.utcnow().isoformat()}")

def send_password_reset_email(email: str, token: str):
    link = f"http://localhost:8000/auth/password-reset?token={token}"
    print(f"[Email] To: {email} — Password reset link: {link} — at {datetime.utcnow().isoformat()}")
