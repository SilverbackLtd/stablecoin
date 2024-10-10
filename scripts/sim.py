import random

import click
import httpx
from ape import accounts, project
from ape.cli import ConnectedProviderCommand


class Client(httpx.Client):
    def __init__(self, url, stable, account):
        super().__init__(base_url=url)
        self.account = account
        self.stable = stable
        self.post("/login")
        self.post("/address", json=dict(address=self.account.address))


@click.command(cls=ConnectedProviderCommand)
@click.option("-n", "--num-accounts", type=int, default=9)
@click.option("-s", "--steps", type=int, default=100)
@click.argument("bank", default="http://127.0.0.1:8000")
@click.argument("stable", callback=lambda _c, _p, value: project.Stablecoin.at(value))
def cli(num_accounts, steps, bank, stable):
    users = [Client(bank, stable, u) for u in accounts.test_accounts[:num_accounts]]

    while steps > 0:
        user = random.choice(users)

        steps -= 1
