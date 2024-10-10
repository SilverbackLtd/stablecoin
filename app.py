import asyncio

from ape import accounts, networks, project
from ape.types import AddressType
from fastapi import Cookie, Depends, FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from pydantic_settings import BaseSettings
from sqlmodel import Session, SQLModel, create_engine, select

from database import Account


class AppSettings(BaseSettings):
    DB_URI: str = "sqlite:///db.sqlite"
    SIGNER_ALIAS: str = "banker"
    STABLECOIN_ADDRESSES: dict[str, AddressType] = {}


SETTINGS = AppSettings()
if SETTINGS.SIGNER_ALIAS.startswith("TEST::"):
    BANKER = accounts.test_accounts[int(SETTINGS.SIGNER_ALIAS.replace("TEST::", ""))]
else:
    BANKER = accounts.load(SETTINGS.SIGNER_ALIAS)
    BANKER.set_autosign(True)

app = FastAPI()
engine = create_engine(SETTINGS.DB_URI)
SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


def convert_to_option(ecosystem_network: str):
    ecosystem, network = ecosystem_network.split(":")
    return f'<option value="{ecosystem_network}">{ecosystem} {network}</option>'


NETWORK_OPTIONS = "".join(map(convert_to_option, SETTINGS.STABLECOIN_ADDRESSES))


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
    <select name="network">{NETWORK_OPTIONS}</select>
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
    address: AddressType = Form(),
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

    if not (stablecoin_address := (SETTINGS.STABLECOIN_ADDRESSES.get(network))):
        return "Invalid network"

    with networks.parse_network_choice(network):
        stablecoin = project.Stablecoin.at(stablecoin_address)

        account.balance -= amount
        session.add(account)
        session.commit()
        session.refresh(account)

        tx = stablecoin.mint(
            account.address, amount * 10 ** stablecoin.decimals(), sender=BANKER
        )

    return f"Minting ({tx.txn_hash})"


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
