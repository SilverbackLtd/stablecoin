import asyncio

from eth_pydantic_types import Address
from fastapi import Cookie, Depends, FastAPI, Form, Header, Query
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from pydantic import field_validator
from pydantic_settings import BaseSettings
from sqlmodel import (Field, Relationship, Session, SQLModel, create_engine,
                      select)


class AppSettings(BaseSettings):
    API_KEY: str = "fakesecret"
    DB_URI: str = "sqlite:///db.sqlite"
    # NOTE: Default address if you deploy `Stablecoin` with `test_accounts[0]` as first txn
    STABLECOIN_ADDRESSES: dict[str, Address] = {
        "ethereum:local": "0x5FbDB2315678afecb367f032d93F642f64180aa3"
    }


settings = AppSettings()


class Account(SQLModel, table=True):
    __tablename__ = "accounts"

    # NOTE: Autoincremented account ID
    id: int | None = Field(primary_key=True, default=None)
    balance: int = Field(ge=0, default=0)
    address: str | None = None

    # Compliance
    sus: bool = False


class Mint(SQLModel, table=True):
    __tablename__ = "mints"

    network: str = Field(primary_key=True)
    account_id: int = Field(foreign_key="accounts.id", primary_key=True)
    account: Account = Relationship()

    amount: int = 0  # NOTE: So that `+=` works

    @field_validator("network")
    def valid_network_choice(cls, value: str):
        assert value in settings.STABLECOIN_ADDRESSES
        return value


class Unfreeze(SQLModel, table=True):
    __tablename__ = "accounts_to_unfreeze"

    network: str = Field(primary_key=True)
    account_id: int = Field(foreign_key="accounts.id", primary_key=True)
    account: Account = Relationship()


app = FastAPI()
engine = create_engine(settings.DB_URI)
SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


def convert_to_option(ecosystem_network: str):
    ecosystem, network = ecosystem_network.split(":")
    return f'<option value="{ecosystem_network}">{ecosystem} {network}</option>'


@app.get("/")
async def index(
    account_id: int | None = Cookie(default=None),
    session: Session = Depends(get_session),
):
    if not (account := session.get(Account, account_id)):
        return HTMLResponse(
            """<!DOCTYPE html>
<body>
  <h1>Welcome to Wurst Bank!</h1>
  <form action="/login" method="post">
    <button>
      Click here to login
    </button>
  </form>
</body>
"""
        )

    if account.sus:
        return HTMLResponse(
            """<!DOCTYPE html>
<body>
  <h1>WARNING: You access has been blocked for suspicious activities!</h1>
  <form action="/false-alarm" method="post">
    <button>
      Click here to restore access
    </button>
  </form>
</body>
"""
        )

    network_options = "".join(map(convert_to_option, settings.STABLECOIN_ADDRESSES))
    return HTMLResponse(
        f"""<!DOCTYPE html>
<head>
  <script src="https://unpkg.com/htmx.org@2.0.3"></script>
  <script src="https://unpkg.com/htmx-ext-sse@2.2.2/sse.js"></script>
</head>
<body>
  <h1>Welcome to Wurst Bank!</h1>
  <p hx-ext="sse" sse-connect="/balance">
    Your balance: <span sse-swap="message">Loading...</span>
  </p>
  <button hx-target="#message" hx-post="/deposit">Deposit some</button>
  <button hx-target="#message" hx-post="/withdraw">Withdraw some</button>
  <p>
    Your Address:
    <input
      name="address"
      hx-post="/address"
      hx-target="#message"
      hx-trigger="input changed delay:500ms"
      value="{account.address or ''}"
    >
  </p>
  <form hx-target="#message" hx-post="/mint">
    <select name="network">{network_options}</select>
    <button>Mint some stables</button>
  </form>
  <p id="message"></p>
  <script>
    document.body.addEventListener('htmx:sseBeforeMessage', console.log)
  </script>
</body>"""
    )


@app.post("/login")
async def login(
    account_id: int | None = Cookie(default=None),
    session: Session = Depends(get_session),
):
    response = RedirectResponse("/", 303)
    if not session.get(Account, account_id):
        new_account = Account()
        session.add(new_account)
        session.commit()
        session.refresh(new_account)
        response.set_cookie("account_id", str(new_account.id))

    return response


@app.post("/deposit")
async def deposit(
    amount: int = Form(default=100),
    account_id: int = Cookie(),
    session: Session = Depends(get_session),
):
    account = session.get(Account, account_id)
    if account.sus:
        return "You have failed our compliance"

    account.balance += amount
    session.add(account)
    session.commit()
    session.refresh(account)

    return f"Deposited ${amount}.00"


@app.post("/address")
async def set_address(
    address: Address = Form(),
    account_id: int = Cookie(),
    session: Session = Depends(get_session),
):
    account = session.get(Account, account_id)
    account.address = address
    session.add(account)
    session.commit()
    session.refresh(account)

    return "Updated address"


@app.post("/mint")
async def mint(
    network: str = Form(),
    amount: int = Form(default=100),
    account_id: int = Cookie(),
    session: Session = Depends(get_session),
) -> str:
    account = session.get(Account, account_id)
    if not account.address:
        return "No address set"

    if amount > account.balance:
        return "Insufficent balance"

    if account.sus:
        return "You have failed our compliance"

    account.balance -= amount
    session.add(account)

    if not (mint := session.get(Mint, (network, account_id))):
        mint = Mint(account_id=account_id, network=network)

    mint.amount += amount
    session.add(mint)

    session.commit()

    return f"Minting ${amount}.00 on {network}"


@app.post("/false-alarm")
async def unfreeze_me(
    account_id: int = Cookie(),
    session: Session = Depends(get_session),
) -> str:
    account = session.get(Account, account_id)

    if account.sus:
        account.sus = False
        session.add(account)
        for network_choice in settings.STABLECOIN_ADDRESSES:
            session.add(Unfreeze(account_id=account_id, network=network_choice))

        session.commit()

    return RedirectResponse("/", status_code=303)


@app.post("/withdraw")
async def withdraw(
    amount: int = Form(default=100),
    account_id: int = Cookie(),
    session: Session = Depends(get_session),
) -> str:
    account = session.get(Account, account_id)

    if amount > account.balance:
        return "Insufficent balance"

    if account.sus:
        return "You have failed our compliance"

    account.balance -= amount
    session.add(account)
    session.commit()

    return f"Withdrew ${amount}.00"


@app.get("/balance")
async def get_balance_updates(
    account_id: int = Cookie(),
    session: Session = Depends(get_session),
) -> StreamingResponse:
    async def balance_updates():
        last_balance = session.scalar(
            select(Account.balance).where(Account.id == account_id)
        )
        yield f"data: ${last_balance}.00\n\n"
        while True:
            if (
                balance := session.scalar(
                    select(Account.balance).where(Account.id == account_id)
                )
            ) != last_balance:
                yield f"data: ${balance}.00\n\n"
                last_balance = balance

            await asyncio.sleep(1)

    return StreamingResponse(balance_updates(), media_type="text/event-stream")


def check_cookie(x_internal_key: str = Header(default=None)):
    if x_internal_key != settings.API_KEY:
        # NOTE: Mimic 404 for non-existent routes
        raise HTTPException(detail="Not Found", status_code=404)


internal = FastAPI(dependencies=[Depends(check_cookie)])


@internal.delete("/access/{address}")
async def compliance_failure(
    address: Address,
    session: Session = Depends(get_session),
):
    if account := session.exec(
        select(Account).where(Account.address == address)
    ).one_or_none():
        account.sus = True
        session.add(account)
        session.commit()


@internal.get("/false-alarms")
async def get_false_alarms(
    ecosystem: str = Query(),
    network: str = Query(),
    session: Session = Depends(get_session),
) -> list[Address]:
    # First get all the cached unfreeze requests
    network_choice = f"{ecosystem}:{network}"
    accounts_to_unfreeze = session.exec(
        select(Account.address).join(Unfreeze).where(Unfreeze.network == network_choice)
    ).all()

    # Then delete all the cached unfreeze requests
    for unfreeze_request in session.exec(
        select(Unfreeze).where(Unfreeze.network == network_choice)
    ).all():
        session.delete(unfreeze_request)
    session.commit()

    return accounts_to_unfreeze


@internal.post("/redeem/{address}")
async def redeem_amount(
    address: Address,
    amount: int,
    session: Session = Depends(get_session),
):
    if account := session.exec(
        select(Account).where(Account.address == address)
    ).one_or_none():
        account.balance += amount
        session.add(account)
        session.commit()
    else:
        raise HTTPException(
            detail=f"No account w/ address '{address}'", status_code=404
        )


@internal.get("/mints")
async def get_mint_requests(
    ecosystem: str = Query(),
    network: str = Query(),
    session: Session = Depends(get_session),
) -> list[tuple[Address, int]]:
    # First get all the cached mints
    network_choice = f"{ecosystem}:{network}"
    mints = [
        # NOTE: Don't forget to account for balance adjustment (token is 6 decimal places)
        (address, amount * 10**6)
        for address, amount in session.exec(
            select(Account.address, Mint.amount)
            .join(Account)
            .where(Mint.network == network_choice)
        ).all()
    ]

    # Then delete all the cached mints
    for mint in session.exec(select(Mint).where(Mint.network == network_choice)).all():
        session.delete(mint)
    session.commit()

    return mints


app.mount("/internal", internal)
