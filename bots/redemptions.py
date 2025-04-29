import json
import os

from ape import project
from ape.utils import ZERO_ADDRESS
from httpx import AsyncClient
from silverback import SilverbackBot

STABLECOIN_ADDRESSES = json.loads(
    os.environ.get(
        "STABLECOIN_ADDRESSES",
        '{"ethereum:local":"0x5FbDB2315678afecb367f032d93F642f64180aa3"}',
    )
)

BANK_URI = os.environ.get("BANK_URI", "http://127.0.0.1:8000")
BANK_API_KEY = os.environ.get("BANK_API_KEY", "fakesecret")
bank = AsyncClient(
    base_url=f"{BANK_URI}/internal",
    headers={"X-Internal-Key": BANK_API_KEY},
)


bot = SilverbackBot()
stable = project.Stablecoin.at(
    STABLECOIN_ADDRESSES[f"{bot.identifier.ecosystem}:{bot.identifier.network}"],
    fetch_from_explorer=False,
)


# NOTE: Redemptions are burning supply (Transfers to 0x0)
@bot.on_(stable.Transfer, receiver=ZERO_ADDRESS)
async def redeemed(log):
    response = await bank.patch(
        f"/redeem/{log.sender}",
        params=dict(amount=log.value // 10 ** stable.decimals()),
    )
    assert response.status_code == 200, response.text

    return log.value
