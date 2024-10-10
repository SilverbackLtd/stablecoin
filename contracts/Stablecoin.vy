# pragma version 0.4.0
from ethereum.ercs import IERC20
implements: IERC20

from ethereum.ercs import IERC20Detailed
implements: IERC20Detailed

from snekmate.auth import ownable as ow
initializes: ow

from snekmate.tokens import erc20
initializes: erc20[ownable := ow]

exports: erc20.__interface__


@deploy
@payable
def __init__():
    ow.__init__()
    erc20.__init__("Stablecoin", "wbUSD", 6, "Stablecoin", "1.0")


event Frozen:
    account: indexed(address)


#### Add our Freeze functions here ####
is_frozen: public(HashMap[address, bool])


@external
def set_freeze(accounts: DynArray[address, 20], is_frozen: bool = True):
    assert erc20.is_minter[msg.sender]

    for account: address in accounts:
        self.is_frozen[account] = is_frozen
        log Frozen(account)


def _before_token_transfer(sender: address, receiver: address, amount: uint256):
    assert not self.is_frozen[sender]
    assert not self.is_frozen[receiver]
