import asyncio
import uuid
from collections import defaultdict
from typing import ClassVar

from ape import accounts, networks, project
from ape.api import AccountAPI
from ape.utils import ZERO_ADDRESS, cached_property
from eth_pydantic_types import Address
from fastapi import BackgroundTasks, Cookie, Depends, FastAPI, Form, Header
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from pydantic_settings import BaseSettings
from sqlmodel import Field, Session, SQLModel, create_engine, select


class AppSettings(BaseSettings):
    MINTER_ALIAS: str = "TEST::1"
    API_KEY: str = "fakesecret"
    # NOTE: Default address if you deploy `Stablecoin` with `test_accounts[0]` as first txn
    STABLECOIN_ADDRESSES: dict[str, Address] = {
        "ethereum:local": "0x5FbDB2315678afecb367f032d93F642f64180aa3"
    }
    DB_URI: str = "sqlite:///db.sqlite"

    @cached_property
    def signer(self) -> AccountAPI:
        if self.MINTER_ALIAS.startswith("TEST::"):
            return accounts.test_accounts[int(self.MINTER_ALIAS.replace("TEST::", ""))]

        return accounts.load(self.MINTER_ALIAS)


settings = AppSettings()
engine = create_engine(settings.DB_URI)


def get_session():
    with Session(engine) as session:
        yield session


class BankAccount(SQLModel, table=True):
    activity: ClassVar[dict[uuid.UUID, asyncio.Queue]] = defaultdict(asyncio.Queue)

    # NOTE: Autoincremented account ID
    id: uuid.UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    balance: int = Field(ge=0, default=0)
    address: Address | None = Field(index=True, default=None)

    # Compliance
    sus: bool = False


async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    app.state.running = True
    yield
    app.state.running = False


app = FastAPI(lifespan=lifespan)


def convert_to_option(ecosystem_network: str):
    ecosystem, network = ecosystem_network.split(":")
    return f'<option value="{ecosystem_network}">{ecosystem} {network}</option>'


def convert_to_notification(message: str) -> HTMLResponse:
    return f'<li x-data><p>{message} <button x-on:click="$root.remove()">x</button></p></li>'


async def mint_tokens(account_id: uuid.UUID, network: str, amount: int):
    with Session(engine) as session:
        if not (account := session.get(BankAccount, account_id)):
            return

        with networks.parse_network_choice(network) as provider:
            stablecoin = project.Stablecoin.at(
                settings.STABLECOIN_ADDRESSES.get(network), fetch_from_explorer=False
            )
            tx = stablecoin.mint(
                # NOTE: Don't forget to adjust for decimals
                [dict(receiver=account.address, amount=(amount * 10**6))],
                sender=settings.signer,
                required_confirmations=0,  # Don't wait for receipt
            )
            try:
                tx_url = provider.network.explorer.get_transaction_url(tx.txn_hash)
                tx_link = f"<a href='{tx_url}'>{tx.txn_hash}</a>"

            except Exception:
                tx_link = tx.txn_hash

            await BankAccount.activity[account.id].put(
                convert_to_notification(
                    f"Minted ${amount}.00 to {account.address} on '{network}': {tx_link}"
                )
            )


@app.get("/")
async def index(
    account_id: uuid.UUID | None = Cookie(default=None),
    session: Session = Depends(get_session),
):
    if not (account := session.get(BankAccount, account_id)):
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
</body>
"""
        )

    network_options = "".join(map(convert_to_option, settings.STABLECOIN_ADDRESSES))
    return HTMLResponse(
        f"""<!DOCTYPE html>
<head>
  <script src="https://unpkg.com/alpinejs@3.14" defer></script>
  <script src="https://unpkg.com/htmx.org@2.0"></script>
  <script src="https://unpkg.com/htmx-ext-sse@2.2/sse.js"></script>
</head>
<body hx-ext="sse" sse-connect="/activity" x-data>
  <h1>Welcome to Wurst Bank!</h1>
  <p>
    Your balance: <span sse-swap="balance">Loading...</span>
  </p>
  <button
    hx-post="/deposit"
    hx-target="#notifications"
    hx-swap="afterbegin"
  >
    Deposit some
  </button>
  <button
    hx-post="/withdraw"
    hx-target="#notifications"
    hx-swap="afterbegin"
  >
    Withdraw some
  </button>
  <p>
    Your Address:
    <input
      name="address"
      hx-post="/address"
      hx-target="#notifications"
      hx-swap="afterbegin"
      hx-trigger="input changed delay:500ms"
      value="{account.address or ""}"
    >
  </p>
  <form hx-post="/mint" hx-target="#notifications" hx-swap="afterbegin">
    <select name="network">{network_options}</select>
    <button>Mint some stables</button>
  </form>
  <br/>
  <h3>
    Notifications
    <button x-on:click="$refs.notifications.textContent =''">Clear</button>
  </h3>
  <ul x-ref="notifications" id="notifications" sse-swap="notification" hx-swap="afterbegin">
  </ul>
</body>"""
    )


@app.post("/login")
async def login(
    account_id: uuid.UUID | None = Cookie(default=None),
    session: Session = Depends(get_session),
):
    response = RedirectResponse("/", 303)

    if not session.get(BankAccount, account_id):
        new_account = BankAccount()
        session.add(new_account)
        session.commit()

        response.set_cookie("account_id", str(new_account.id))

    return response


@app.post("/deposit")
async def deposit(
    amount: int = Form(default=100),
    account_id: uuid.UUID = Cookie(),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    if not (account := session.get(BankAccount, account_id)):
        return HTMLResponse(convert_to_notification("Not logged in"))

    if account.sus:
        return HTMLResponse(convert_to_notification("You have failed our compliance"))

    account.balance += amount
    session.add(account)
    session.commit()

    return HTMLResponse(convert_to_notification(f"Deposited ${amount}.00"))


@app.post("/address")
async def set_address(
    address: Address = Form(),
    account_id: uuid.UUID = Cookie(),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    if not (account := session.get(BankAccount, account_id)):
        return HTMLResponse(convert_to_notification("Not logged in"))

    account.address = address
    session.add(account)
    session.commit()

    return HTMLResponse(convert_to_notification("Updated address"))


@app.post("/mint")
async def mint(
    network: str = Form(),
    amount: int = Form(default=100),
    account_id: uuid.UUID = Cookie(),
    session: Session = Depends(get_session),
    *,
    background_tasks: BackgroundTasks,
) -> HTMLResponse:
    if network not in settings.STABLECOIN_ADDRESSES:
        return HTMLResponse(convert_to_notification("Not valid network"))

    if not (account := session.get(BankAccount, account_id)):
        return HTMLResponse(convert_to_notification("Not logged in"))

    if not (address := account.address) or address == ZERO_ADDRESS:
        return HTMLResponse(convert_to_notification("No address set"))

    if amount > account.balance:
        return HTMLResponse(convert_to_notification("Insufficent balance"))

    if account.sus:
        return HTMLResponse(convert_to_notification("You have failed our compliance"))

    account.balance -= amount
    session.add(account)
    session.commit()

    background_tasks.add_task(mint_tokens, account_id, network, amount)

    return HTMLResponse(
        convert_to_notification(f"Minting ${amount}.00 on {network} to {address}")
    )


@app.post("/withdraw")
async def withdraw(
    amount: int = Form(default=100),
    account_id: uuid.UUID = Cookie(),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    if not (account := session.get(BankAccount, account_id)):
        return HTMLResponse(convert_to_notification("Not logged in"))

    if amount > account.balance:
        return HTMLResponse(convert_to_notification("Insufficent balance"))

    if account.sus:
        return HTMLResponse(convert_to_notification("You have failed our compliance"))

    account.balance -= amount
    session.add(account)
    session.commit()

    return HTMLResponse(convert_to_notification(f"Withdrew ${amount}.00"))


@app.get("/activity")
async def get_updates(
    account_id: uuid.UUID = Cookie(),
    session: Session = Depends(get_session),
) -> StreamingResponse:
    if not session.get(BankAccount, account_id):
        raise HTTPException(detail="Account not found", status_code=404)

    async def account_activity():
        last_balance = None
        while app.state.running:
            balance = session.scalar(
                select(BankAccount.balance).where(BankAccount.id == account_id)
            )

            if last_balance is None or balance != last_balance:
                yield f"event: balance\ndata: ${balance}.00\n\n"
                last_balance = balance

            if not (notifications := BankAccount.activity[account_id]).empty():
                while not notifications.empty():
                    yield f"event: notification\ndata: {await notifications.get()}\n\n"

            await asyncio.sleep(1)

    return StreamingResponse(account_activity(), media_type="text/event-stream")


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
    if not (
        account := session.exec(
            select(BankAccount).where(BankAccount.address == address)
        ).first()
    ):
        raise HTTPException(status_code=404, detail="Address not found")

    account.sus = True
    session.add(account)
    session.commit()

    await BankAccount.activity[account.id].put(
        convert_to_notification(
            "Your account has been suspended for compliance reasons"
        )
    )


@internal.patch("/redeem/{address}")
async def redeem_amount(
    address: Address,
    amount: int,
    session: Session = Depends(get_session),
):
    if not (
        account := session.exec(
            select(BankAccount).where(BankAccount.address == address)
        ).first()
    ):
        raise HTTPException(status_code=404, detail="Address not found")

    account.balance += amount
    session.add(account)
    session.commit()

    await BankAccount.activity[account.id].put(
        convert_to_notification(f"Redeemed ${amount}.00")
    )


app.mount("/internal", internal)
