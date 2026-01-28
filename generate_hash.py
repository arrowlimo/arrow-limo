import bcrypt

# Generate a fresh bcrypt hash for password "admin"
password = "admin"
hash_obj = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(12))
new_hash = hash_obj.decode('utf-8')

print(f"New bcrypt hash for 'admin': {new_hash}")

# Test it immediately
verify = bcrypt.checkpw(password.encode('utf-8'), new_hash.encode('utf-8'))
print(f"Verification: {verify}")
