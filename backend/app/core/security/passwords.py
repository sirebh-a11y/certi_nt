from passlib.context import CryptContext

password_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(value: str) -> str:
    return password_context.hash(value)


def verify_password(plain_value: str, hashed_value: str) -> bool:
    return password_context.verify(plain_value, hashed_value)
