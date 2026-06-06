import re

def validate_email(email: str) -> bool:
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None

def validate_password(password: str) -> bool:
    min_pass_length = 8
    pattern = rf"^[0-9A-Za-z!@#$%^&*()_+= \-]{{{min_pass_length},}}$"
    return re.match(pattern, password) is not None