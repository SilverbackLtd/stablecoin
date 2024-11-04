import json
import os
from collections import defaultdict

from ape import chain, project
from ape.utils import ZERO_ADDRESS
from ape_ethereum import multicall
from httpx import AsyncClient
from silverback import SilverbackBot

STABLECOIN_ADDRESSES = json.loads(
    os.environ.get(
        "STABLECOIN_ADDRESSES",
        '{"ethereum:local":"0x5FbDB2315678afecb367f032d93F642f64180aa3"}',
    )
)
bank = AsyncClient(
    base_url=f'{os.environ.get("BANK_URI", "http://127.0.0.1:8000")}/internal',
    headers={"X-Internal-Key": os.environ.get("BANK_API_KEY", "fakesecret")},
)


bot = SilverbackBot()
stable = project.Stablecoin.at(
    STABLECOIN_ADDRESSES[f"{bot.identifier.ecosystem}:{bot.identifier.network}"]
)

if bot.identifier.network == "local":
    # For local testing
    multicall.Call.inject()


@bot.on_(chain.blocks)
async def minted(_):
    response = await bank.get(
        "/mints",
        params=dict(
            ecosystem=bot.identifier.ecosystem,
            network=bot.identifier.network,
        ),
    )
    assert response.status_code == 200, response.text

    # NOTE: May be multiple requests by the same person
    mints = defaultdict(lambda: 0)
    for address, amount in response.json():
        mints[address] += amount

    # TODO: Could use multicall, but not every chain supports it?
    if not (
        # NOTE: Put into format for call below
        mints := list(
            dict(receiver=receiver, amount=amount)
            for receiver, amount in filter(
                # NOTE: Remove frozen accounts from minting
                lambda t: not stable.is_frozen(t[0]),
                iter(mints.items()),
            )
        )
    ):
        return 0

    stable.mint(mints, sender=bot.signer, required_confirmations=0)

    return sum(map(lambda d: d["amount"], mints))


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
