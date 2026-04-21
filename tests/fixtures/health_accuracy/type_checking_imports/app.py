from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models import User

import os

def greet(user: User) -> str:
    return f"Hello {user.name}"

print(os.getcwd())
