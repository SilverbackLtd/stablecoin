import random
import time
from typing import TYPE_CHECKING

import click
import httpx
from ape import accounts, project
from ape.cli import ConnectedProviderCommand

if TYPE_CHECKING:
    from ape.api import AccountAPI
    from ape.contracts import ContractInstance


class BankClient(httpx.Client):
    def __init__(
        self,
        url: str,
        network: str,
        stable: "ContractInstance",
        account: "AccountAPI",
    ):
        super().__init__(base_url=url)
        self.network = network
        self.stable = stable
        self.account = account
        self.balance = 0

        response = self.post("/login")
        assert response.status_code < 400, response.text
        self.cookies = response.cookies

        self.post(
            "/address",
            data=dict(address=self.account.address),
            cookies=self.cookies,
        )

    def deposit(self, amount: int = 100):
        response = self.post(
            "/deposit",
            data=dict(amount=amount),
            cookies=self.cookies,
        )
        if response.status_code == 200:
            self.balance += amount

    def mint(self, amount: int = 100):
        response = self.post(
            "/mint",
            data=dict(network=self.network, amount=amount),
            cookies=self.cookies,
        )
        if response.status_code == 200:
            self.balance -= amount

    def transfer(self, receiver: "BankClient", amount: int = 100):
        self.stable.transfer(receiver.account, amount * int(1e6), sender=self.account)

    def redeem(self, amount: int = 100):
        self.stable.burn(amount * int(1e6), sender=self.account)

    def withdraw(self, amount: int = 100):
        response = self.post(
            "/withdraw",
            data=dict(amount=amount),
            cookies=self.cookies,
        )
        if response.status_code == 200:
            self.balance -= amount


@click.command(cls=ConnectedProviderCommand)
@click.option("-n", "--num-accounts", type=int, default=9)
@click.option("-s", "--steps", type=int, default=100)
@click.argument("bank", default="http://127.0.0.1:8000")
@click.argument(
    "stablecoin_address", default="0x5FbDB2315678afecb367f032d93F642f64180aa3"
)
def cli(num_accounts, ecosystem, network, steps, bank, stablecoin_address):
    stablecoin = project.Stablecoin.at(stablecoin_address)
    users = [
        BankClient(
            bank,
            f"{ecosystem.name}:{network.name}",
            stablecoin,
            account,
        )
        for account in accounts.test_accounts[:num_accounts]
    ]

    for step in range(1, steps + 1):
        while stablecoin.is_frozen((user := random.choice(users)).account):
            click.secho(f"""{user.account.address} is frozen""", fg="red")
            users.remove(user)
            if len(users) == 0:
                raise click.Abort("All users are frozen!")

        potential_actions = ["deposit"]
        if (token_balance := stablecoin.balanceOf(user.account) // int(1e6)) > 100:
            potential_actions.append("redeem")
            if len(users) > 1:
                potential_actions.append("transfer")

        if user.balance > 100:
            potential_actions.extend(["mint", "withdraw"])

        action = random.choice(potential_actions)

        if action == "deposit":
            args = dict(amount=random.randint(1, 25) * 100)

        elif action in ["mint", "withdraw"]:
            args = dict(amount=(random.randint(1, min(25, user.balance // 100)) * 100))

        else:
            args = dict(amount=(random.randint(1, min(25, token_balance // 100)) * 100))

        if action == "transfer":
            while stablecoin.is_frozen(
                (receiver := random.choice([u for u in users if u != user])).account
            ):
                users.remove(receiver)
                if len(users) == 1:
                    continue

            args_display = f"{receiver.account.address}, ${args['amount']:,.2f}"
            args["receiver"] = receiver
        else:
            args_display = f"${args['amount']:,.2f}"

        click.echo(
            f"""
[Step {step}] {user.account.address}
  off-chain: ${user.balance:,.2f}
   on-chain: ${token_balance:,.2f}
     action: {action}({args_display})"""
        )
        getattr(user, action)(**args)
        time.sleep(0.5)  # NOTE: Emulate blockchain w/ 500ms block time
