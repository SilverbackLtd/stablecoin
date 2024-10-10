from sqlmodel import Field, SQLModel


class Account(SQLModel, table=True):
    __tablename__ = "accounts"

    # NOTE: Autoincremented account ID
    id: int | None = Field(primary_key=True, default=None)
    balance: int = Field(ge=0, default=0)
    address: str | None = None

    # Compliance
    sus: bool = False
