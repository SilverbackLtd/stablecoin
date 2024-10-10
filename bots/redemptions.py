import os

from ape import project
from ape.utils import ZERO_ADDRESS
from database import Account
from silverback import SilverbackBot
from sqlmodel import Session, create_engine, select
from taskiq import TaskiqDepends as Depends

engine = create_engine(os.environ["DB_URI"])


def get_session():
    with Session(engine) as session:
        yield session


bot = SilverbackBot()

if address := os.environ.get("STABLECOIN_ADDRESS"):
    stable = project.Stablecoin.at(address)
else:
    stable = project.Stablecoin.deploy(sender=bot.signer)


@bot.on_(stable.Transfer)
def redeemed(log, session=Depends(get_session)):
    # NOTE: refactor to use arg filtering when filtering available
    #       https://github.com/ApeWorX/silverback/pull/55
    if not log.receiver == ZERO_ADDRESS:
        return

    account = session.scalar(select(Account).where(Account.address == log.sender))
    account.balance += log.value // 10 ** stable.decimals()
    session.add(account)
    session.commit()
    session.refresh(account)

    return log.value
