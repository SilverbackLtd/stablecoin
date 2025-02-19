import json
import os
import random

from ape import networks, project
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


def compliance_check(log):
    if log.sender == ZERO_ADDRESS or log.receiver == ZERO_ADDRESS:
        return False  # We are always compliant

    return random.random() > 0.95  # Super secret compliance function


@bot.on_(stable.Transfer)
async def check_compliance(log):
    if compliance_check(log):
        response = await bank.post(f"/access/{log.sender}")
        assert response.status_code == 200, response.text

        response = await bank.post(f"/access/{log.receiver}")
        assert response.status_code == 200, response.text

        for network_choice, stable_address in STABLECOIN_ADDRESSES.items():
            with networks.parse_network_choice(network_choice):
                # NOTE: Also rug every other deployment we have too
                project.Stablecoin.at(stable_address).set_freeze(
                    [log.sender, log.receiver], sender=bot.signer
                )
