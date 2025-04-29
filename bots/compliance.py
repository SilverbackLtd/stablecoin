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
        return True  # Minting and Redeeming are always compliant

    # Return compliance passing if risk factor is below 95% percentile
    return random.random() <= 0.95  # Super secret compliance function


@bot.on_(stable.Transfer)
async def check_compliance(log):
    if not compliance_check(log):
        # First revoke minting rights w/ web service
        response = await bank.delete(f"/access/{log.sender}")
        if response.status_code != 200:
            print(response.text)

        response = await bank.delete(f"/access/{log.receiver}")
        if response.status_code != 200:
            print(response.text)

        # Now go and remove transfer rights from every chain we are deployed on
        for network_choice, stable_address in STABLECOIN_ADDRESSES.items():
            with networks.parse_network_choice(network_choice):
                # NOTE: Freeze on every deployment we have, not just this chain
                project.Stablecoin.at(stable_address).set_freeze(
                    [log.sender, log.receiver],
                    sender=bot.signer,
                    required_confirmations=0,  # Don't wait for conf
                )
