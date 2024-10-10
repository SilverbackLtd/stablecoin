import json
from pathlib import Path

import click
from ape import networks, project
from ape.cli import account_option

PROJECT_ROOT = Path(__file__).parent.parent
MINTER = json.loads((PROJECT_ROOT / "banker.json").read_text())["address"]
COMPLIANCE = json.loads((PROJECT_ROOT / "compliance.json").read_text())["address"]


@click.command()
@click.option("-n", "--network", "network_selections", multiple=True)
@account_option()
def cli(network_selections, account):
    """Deploy the Stablecoin on multiple chains"""
    for selection in network_selections:
        with networks.parse_network_choice(selection):
            project.Stablecoin.deploy(MINTER, COMPLIANCE, sender=account)
