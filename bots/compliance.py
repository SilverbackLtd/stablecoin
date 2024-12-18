import json
import os
import random

from ape import chain, networks, project
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
    base_url=f'{os.environ.get("BANK_URI", "http://127.0.0.1:8000")}/internal',
    headers={"X-Internal-Key": os.environ.get("BANK_API_KEY", "fakesecret")},
)


bot = SilverbackBot()
stable = project.Stablecoin.at(
    STABLECOIN_ADDRESSES[f"{bot.identifier.ecosystem}:{bot.identifier.network}"]
)


def compliance_check(log):
    if log.sender == ZERO_ADDRESS or log.receiver == ZERO_ADDRESS:
        return False  # We are always compliant

    return random.random() > 0.95  # Super secret compliance function


@bot.on_(stable.Transfer)
async def check_compliance(log):
    if compliance_check(log):
        response = await bank.delete(f"/access/{log.sender}")
        assert response.status_code == 200, response.text

        response = await bank.delete(f"/access/{log.receiver}")
        assert response.status_code == 200, response.text

        for network_choice, stable_address in STABLECOIN_ADDRESSES.items():
            with networks.parse_network_choice(network_choice):
                project.Stablecoin.at(stable_address).set_freeze(
                    [log.sender, log.receiver], sender=bot.signer
                )


@bot.on_(chain.blocks)
async def restore_access(blk):
    response = await bank.get(
        "/false-alarms",
        params=dict(
            ecosystem=bot.identifier.ecosystem,
            network=bot.identifier.network,
        ),
    )
    assert response.status_code == 200, response.text

    accounts_to_unfreeze = response.json()
    while len(accounts_to_unfreeze) > 0:
        stable.set_freeze(accounts_to_unfreeze[:20], False, sender=bot.signer)
        accounts_to_unfreeze = accounts_to_unfreeze[20:]
