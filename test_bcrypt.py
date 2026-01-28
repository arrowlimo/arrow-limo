import bcrypt

stored_hash = "$2b$12$WdxhMofKy1kLwC8GDmb.A.K.vOb9dlms5UvzHyvgBNzFzMO7pPsTq"
password = "admin"

# Try with default password
result = bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
print(f"Password 'admin': {result}")

# Try some alternatives
for pwd in ["", "password", "12345", "***REMOVED***", "Arrow", "admin123"]:
    result = bcrypt.checkpw(pwd.encode('utf-8'), stored_hash.encode('utf-8'))
    print(f"Password '{pwd}': {result}")
