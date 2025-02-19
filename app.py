import asyncio
import uuid

from ape import accounts, networks, project
from ape.api import AccountAPI
from ape.utils import cached_property
from eth_pydantic_types import Address
from fastapi import BackgroundTasks, Cookie, Depends, FastAPI, Form, Header
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    MINTER_ALIAS: str = "TEST::1"
    API_KEY: str = "fakesecret"
    # NOTE: Default address if you deploy `Stablecoin` with `test_accounts[0]` as first txn
    STABLECOIN_ADDRESSES: dict[str, Address] = {
        "ethereum:local": "0x5FbDB2315678afecb367f032d93F642f64180aa3"
    }

    @cached_property
    def signer(self) -> AccountAPI:
        if self.MINTER_ALIAS.startswith("TEST::"):
            return accounts.test_accounts[int(self.MINTER_ALIAS.replace("TEST::", ""))]

        return accounts.load(self.MINTER_ALIAS)


settings = AppSettings()
bank_accounts: dict[uuid.UUID, "BankAccount"] = {}


class BankAccount(BaseModel):
    # NOTE: Autoincremented account ID
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    balance: int = Field(ge=0, default=0)
    address: Address | None = None

    # Compliance
    sus: bool = False


async def mint_tokens(network: str, address: Address, amount: int):
    with networks.parse_network_choice(network):
        stablecoin = project.Stablecoin.at(
            settings.STABLECOIN_ADDRESSES.get(network), fetch_from_explorer=False
        )
        stablecoin.mint(
            # NOTE: Don't forget to adjust for decimals
            [dict(receiver=address, amount=(amount * 10**6))],
            sender=settings.signer,
            required_confirmations=0,  # Don't wait for receipt
        )


async def lifespan(app: FastAPI):
    app.state.running = True
    yield
    app.state.running = False


app = FastAPI(lifespan=lifespan)


def convert_to_option(ecosystem_network: str):
    ecosystem, network = ecosystem_network.split(":")
    return f'<option value="{ecosystem_network}">{ecosystem} {network}</option>'


@app.get("/")
async def index(
    account_id: uuid.UUID | None = Cookie(default=None),
):
    if account_id is None or not (account := bank_accounts.get(account_id)):
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
      value="{account.address or ""}"
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
    account_id: uuid.UUID | None = Cookie(default=None),
):
    response = RedirectResponse("/", 303)
    if account_id is None or not bank_accounts.get(account_id):
        new_account = BankAccount()
        bank_accounts[new_account.id] = new_account
        response.set_cookie("account_id", str(new_account.id))

    return response


@app.post("/deposit")
async def deposit(
    amount: int = Form(default=100),
    account_id: uuid.UUID = Cookie(),
):
    if account_id not in bank_accounts:
        return "Not logged in"

    if bank_accounts[account_id].sus:
        return "You have failed our compliance"

    bank_accounts[account_id].balance += amount

    return f"Deposited ${amount}.00"


@app.post("/address")
async def set_address(
    address: Address = Form(),
    account_id: uuid.UUID = Cookie(),
):
    if account_id not in bank_accounts:
        return "Not logged in"

    bank_accounts[account_id].address = address

    return "Updated address"


@app.post("/mint")
async def mint(
    network: str = Form(),
    amount: int = Form(default=100),
    account_id: uuid.UUID = Cookie(),
    *,
    background_tasks: BackgroundTasks,
) -> str:
    if network not in settings.STABLECOIN_ADDRESSES:
        return "Not valid network"

    if account_id not in bank_accounts:
        return "Not logged in"

    if not (address := bank_accounts[account_id].address):
        return "No address set"

    if amount > bank_accounts[account_id].balance:
        return "Insufficent balance"

    if bank_accounts[account_id].sus:
        return "You have failed our compliance"

    bank_accounts[account_id].balance -= amount

    background_tasks.add_task(mint_tokens, network, address, amount)

    return f"Minting ${amount}.00 on {network} to {address}"


@app.post("/withdraw")
async def withdraw(
    amount: int = Form(default=100),
    account_id: uuid.UUID = Cookie(),
) -> str:
    if account_id not in bank_accounts:
        return "Not logged in"

    if amount > bank_accounts[account_id].balance:
        return "Insufficent balance"

    if bank_accounts[account_id].sus:
        return "You have failed our compliance"

    bank_accounts[account_id].balance -= amount

    return f"Withdrew ${amount}.00"


@app.get("/balance")
async def get_balance_updates(account_id: uuid.UUID = Cookie()) -> StreamingResponse:
    if account_id not in bank_accounts:
        raise HTTPException(detail="Account not found", status_code=404)

    async def balance_updates():
        while app.state.running:
            yield f"data: ${bank_accounts[account_id].balance}.00\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(balance_updates(), media_type="text/event-stream")


def check_cookie(x_internal_key: str = Header(default=None)):
    if x_internal_key != settings.API_KEY:
        # NOTE: Mimic 404 for non-existent routes
        raise HTTPException(detail="Not Found", status_code=404)


internal = FastAPI(dependencies=[Depends(check_cookie)])


@internal.post("/access/{address}")
async def compliance_failure(address: Address):
    account_id = next(a.id for a in bank_accounts.values() if a.address == address)
    bank_accounts[account_id].sus = True


@internal.post("/redeem/{address}")
async def redeem_amount(address: Address, amount: int):
    account_id = next(a.id for a in bank_accounts.values() if a.address == address)
    bank_accounts[account_id].balance += amount


app.mount("/internal", internal)
