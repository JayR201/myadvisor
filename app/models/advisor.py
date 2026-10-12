from sqlmodel import Field, SQLModel


class Advisor(SQLModel, table=True):
    advisor_id: int | None = Field(default=None, primary_key=True)
    name: str
    email: str = Field(index=True, unique=True)
    department: str
