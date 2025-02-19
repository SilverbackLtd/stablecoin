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
bank = AsyncClient(
    base_url=f"{os.environ.get('BANK_URI', 'http://127.0.0.1:8000')}/internal",
    headers={"X-Internal-Key": os.environ.get("BANK_API_KEY", "fakesecret")},
)


bot = SilverbackBot()
stable = project.Stablecoin.at(
    STABLECOIN_ADDRESSES[f"{bot.identifier.ecosystem}:{bot.identifier.network}"]
)


@bot.on_(stable.Transfer)
async def redeemed(log):
    # NOTE: refactor to use arg filtering when filtering available
    #       https://github.com/ApeWorX/silverback/pull/55
    if not log.receiver == ZERO_ADDRESS:
        return

    response = await bank.post(
        f"/redeem/{log.sender}",
        params=dict(amount=log.value // 10 ** stable.decimals()),
    )
    assert response.status_code == 200, response.text

    return log.value
