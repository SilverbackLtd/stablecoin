import asyncio

from eth_pydantic_types import Address
from fastapi import Cookie, Depends, FastAPI, Form, Header, Query
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from pydantic_settings import BaseSettings
from sqlmodel import Field, Session, SQLModel, create_engine, select


class AppSettings(BaseSettings):
    API_KEY: str = "fakesecret"
    DB_URI: str = "sqlite:///db.sqlite"
    STABLECOIN_ADDRESSES: dict[str, Address] = {}


settings = AppSettings()

# network_choice: queue for subscribed minter
global mint_queue
mint_queue: dict[str, asyncio.Queue[tuple[Address, int]]] = {
    network_choice: asyncio.Queue() for network_choice in settings.STABLECOIN_ADDRESSES
}


class Account(SQLModel, table=True):
    __tablename__ = "accounts"

    # NOTE: Autoincremented account ID
    id: int | None = Field(primary_key=True, default=None)
    balance: int = Field(ge=0, default=0)
    address: str | None = None

    # Compliance
    sus: bool = False


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

    global mint_queue
    if not (minter := (mint_queue.get(network))):
        return "Invalid network"

    account.balance -= amount
    session.add(account)
    session.commit()

    await minter.put((account.address, amount))

    return f"Minting ${amount}.00 on {network}"


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


def check_cookie(x_internal_key: str = Header()):
    assert x_internal_key == settings.API_KEY


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


@internal.get("/mints")
async def get_mint_requests(
    ecosystem: str = Query(),
    network: str = Query(),
) -> list[tuple[Address, int]]:
    network_choice = f"{ecosystem}:{network}"

    global mint_queue
    mints = []
    while mint_queue[network_choice].qsize() > 0:
        mints.append(mint_queue[network_choice].get_nowait())

    return mints


app.mount("/internal", internal)
