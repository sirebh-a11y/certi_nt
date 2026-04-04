from pydantic import BaseModel, EmailStr


class NotificationEmail(BaseModel):
    to_email: EmailStr
    subject: str
    body: str
