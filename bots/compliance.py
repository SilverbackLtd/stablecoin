import os
import random

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
stable = project.Stablecoin.at(os.environ["STABLECOIN_ADDRESS"])


def compliance_check(log):
    if log.sender == ZERO_ADDRESS or log.receiver == ZERO_ADDRESS:
        return False  # We are always compliant

    return random.random() > 0.95  # Super secret compliance function


@bot.on_(stable.Transfer)
async def check_compliance(log, session=Depends(get_session)):
    if compliance_check(log):
        if account := session.exec(
            select(Account).where(Account.address == log.sender)
        ).one_or_none():
            account.sus = True
            session.add(account)
            session.commit()

        if account := session.exec(
            select(Account).where(Account.address == log.receiver)
        ).one_or_none():
            account.sus = True
            session.add(account)
            session.commit()

        stable.set_freeze([log.sender, log.receiver], sender=bot.signer)
