from typing import Literal

ROLE_USER = "user"
ROLE_MANAGER = "manager"
ROLE_ADMIN = "admin"

RoleName = Literal["user", "manager", "admin"]
ROLE_NAMES = {ROLE_USER, ROLE_MANAGER, ROLE_ADMIN}
