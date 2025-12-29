from passlib.hash import argon2

def hash_password(password: str) -> str:
    # No need to truncate, argon2 supports any length
    return argon2.hash(password)

def verify_password(plain_password: str, hashed: str) -> bool:
    return argon2.verify(plain_password, hashed)
