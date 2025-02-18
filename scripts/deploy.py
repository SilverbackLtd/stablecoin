import click
from ape import accounts, networks, project
from ape.cli import account_option


@click.command()
@click.option("-m", "--minter", default="TEST::1")
@click.option("-c", "--compliance", default="TEST::2")
@click.option("-n", "--network", "network_selections", multiple=True, required=True)
@account_option()
def cli(minter, compliance, network_selections, account):
    """Deploy the Stablecoin on multiple chains"""
    if minter.startswith("TEST::"):
        minter = accounts.test_accounts[int(minter[-1])]
    if compliance.startswith("TEST::"):
        compliance = accounts.test_accounts[int(compliance[-1])]

    for selection in network_selections:
        with networks.parse_network_choice(selection):
            project.Stablecoin.deploy(minter, compliance, sender=account)
