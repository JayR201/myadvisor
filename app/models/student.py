from sqlmodel import Field, SQLModel


class Student(SQLModel, table=True):
    student_id: int | None = Field(default=None, primary_key=True)
    name: str
    email: str = Field(unique=True, index=True)
    major: str
    year: int
