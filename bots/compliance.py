import json
import os
import random

from ape import networks, project
from ape.utils import ZERO_ADDRESS
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


def compliance_check(log):
    if log.sender == ZERO_ADDRESS or log.receiver == ZERO_ADDRESS:
        return False  # We are always compliant

    return random.random() > 0.95  # Super secret compliance function


@bot.on_(stable.Transfer)
async def check_compliance(log):
    if compliance_check(log):
        await bank.delete(f"/access/{log.sender}")
        await bank.delete(f"/access/{log.receiver}")

        for network_choice, stable_address in STABLECOIN_ADDRESSES.items():
            with networks.parse_network_choice(network_choice):
                project.Stablecoin.at(stable_address).set_freeze(
                    [log.sender, log.receiver], sender=bot.signer
                )
