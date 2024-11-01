import json
import os
from collections import defaultdict
from itertools import compress

from ape import chain, project
from ape.utils import ZERO_ADDRESS
from ape_ethereum import multicall
from httpx import AsyncClient
from silverback import SilverbackBot

STABLECOIN_ADDRESSES = json.loads(os.environ["STABLECOIN_ADDRESSES"])
bank = AsyncClient(
    base_url=f'{os.environ["BANK_URI"]}/internal',
    headers={"X-Internal-Key": os.environ["BANK_API_KEY"]},
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

    mints = defaultdict(lambda: 0)

    for address, amount in response.json():
        mints[address] += amount

    call = multicall.Call()
    [call.add(stable.is_frozen, address) for address in mints]

    for address in compress(mints, call()):
        print(f"{address} was frozen, not minting")
        del mints[address]  # Filter out frozen accounts

    if not mints:
        return 0

    # NOTE: Ape will treat tuples as structs
    stable.mint(
        list(
            dict(receiver=receiver, amount=amount) for receiver, amount in mints.items()
        ),
        sender=bot.signer,
        required_confirmations=0,
    )

    return sum(mints.values())


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
