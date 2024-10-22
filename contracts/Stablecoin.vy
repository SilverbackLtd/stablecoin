# pragma version 0.4.0
from ethereum.ercs import IERC20
implements: IERC20

from ethereum.ercs import IERC20Detailed
implements: IERC20Detailed

name: public(constant(String[10])) = "Stablecoin"
symbol: public(constant(String[5])) = "USDwb"
decimals: public(constant(uint8)) = 6

totalSupply: public(uint256)
balanceOf: public(HashMap[address, uint256])
allowance: public(HashMap[address, HashMap[address, uint256]])

owner: public(address)
minter: public(address)
compliance: public(address)
is_frozen: public(HashMap[address, bool])

event Frozen:
    account: indexed(address)


@deploy
def __init__(minter: address, compliance: address):
    self.owner = msg.sender
    self.minter = minter
    self.compliance = compliance


@external
def set_freeze(accounts: DynArray[address, 20], is_frozen: bool = True):
    assert msg.sender == self.compliance

    for account: address in accounts:
        self.is_frozen[account] = is_frozen
        log Frozen(account)


def _transfer(sender: address, receiver: address, amount: uint256):
    assert not self.is_frozen[sender]
    assert not self.is_frozen[receiver]
    
    self.balanceOf[sender] -= amount
    self.balanceOf[receiver] += amount

    log IERC20.Transfer(sender, receiver, amount)


@external
def transfer(receiver: address, amount: uint256) -> bool:
    self._transfer(msg.sender, receiver, amount)
    return True


@external
def approve(spender: address, amount: uint256) -> bool:
    self.allowance[msg.sender][spender] = amount
    log IERC20.Approval(msg.sender, spender, amount)
    return True


@external
def transferFrom(sender: address, receiver: address, amount: uint256) -> bool:
    self.allowance[sender][msg.sender] -= amount
    self._transfer(sender, receiver, amount)
    return True


struct Mint:
    receiver: address
    amount: uint256


@external
def mint(mints: DynArray[Mint, 100]) -> bool:
    assert msg.sender == self.minter

    for mint: Mint in mints:
        assert not self.is_frozen[mint.receiver]

        self.totalSupply += mint.amount
        self.balanceOf[mint.receiver] += mint.amount

        log IERC20.Transfer(empty(address), mint.receiver, mint.amount)

    return True


@external
def burn(amount: uint256) -> bool:
    assert not self.is_frozen[msg.sender]

    self.totalSupply -= amount
    self.balanceOf[msg.sender] -= amount
    log IERC20.Transfer(msg.sender, empty(address), amount)

    return True
