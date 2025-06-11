from typing import TYPE_CHECKING, List, Optional
from pydantic import EmailStr
from sqlmodel import Field, Relationship, SQLModel
# from models.events import Event

if TYPE_CHECKING:
    from models.events import Event

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: EmailStr
    password: str
    username: str
    events: Optional[List["Event"]] = Relationship(back_populates="user")

class UserSignIn(SQLModel):
    email: EmailStr
    password: str   

class UserSignUp(SQLModel):
    email: EmailStr
    password: str
    username: str 