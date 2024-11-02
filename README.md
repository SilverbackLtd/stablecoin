# Welcome to Wurst Bank!

_Stablecoin Demo_

## What is this?

Wurst Bank is a (pretty crappy) bank that lets you "deposit" and "withdraw" money seemingly arbitrarily.
But Wurst Bank is nothing if not innovative!
Recently, Wurst Bank decided to create a stablecoin and is operating it on 3 different chains at the same time, thanks to [Silverback](https://silverback.apeworx.io).

In the UI, you can add your wallet address and mint some of your account balance on the chain of your choice.
This stablecoin is just a normal token in that you can transfer it around, although please transfer it safely or else our Compliance Dept may label you as a risk!
If you happen to be labeled a risk... well, lets just say that you won't be able to transfer our stablecoin anymore (thanks to Silverback).

If you ever want to bring your on-chain balance back into the bank, it's as easy as just burning the token from your registered on-chain address.
Again, thanks to Silverback, it will listen for these burns and respond by automatically updating your bank account again with your burned balance!

## Who is this for?

Well, anyone can use our demo stablecoin!
<!-- TODO: Add link to demo -->
But more importantly, this is a demo operating 2 different Silverback bots across 3 different chains at the same time, all linked to a central webapp and database.
This type of microservice architecture serves to help you scale operations across many different chains at the same time.
And it's easy! Thanks to the power of Python, Ape's plugin system, and Silverback's simplified UX for making chain monitoring and transactional capabilities easy to automate.

## How do I get in touch?
If you are interested in this demo, it's really easy to get started by visiting the repo and starting to modify with the [SDK](https://docs.apeworx.io/silverback/stable/userguides/quickstart).
No signup required, just pull the fully OSS Silverback SDK and make your own bots to test locally with.
Once you are happy and want to run things in production, please visit us at https://silverback.apeworx.io to set up an account and get started with deploying on our cloud platform.

**Try Silverback Today!**

## Local Testing

You can run this example locally. First, start an instance of anvil via:

```sh
anvil -b 1
```

Then deploy your stablecoin via:
```sh
ape run deploy --minter TEST::1 --compliance TEST::2 --account TEST::0 --network :local
...
SUCCESS:  Contract 'Stablecoin' deployed to: 0x5FbDB2315678afecb367f032d93F642f64180aa3
```

Next, you need to run the bank:
```sh
fastapi dev
```

Now you can visit the bank by going to http://127.0.0.1:8000 in the browser.

Next, you want to run the redemptions bot via:
```sh
silverback run redemptions --account TEST::1 --network :local
```

And also the compliance bot via (optional):
```sh
silverback run compliance --account TEST::2 --network :local
```

Finally, go into an ape session via:
```sh
ape console --network :local
```

You want to get an account available on the local chain via:
```py
 In [0]: me = accounts.test_accounts[3]
 In [1]: me.address
Out [1]: "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
```

Put this address in the "Your Address" form field, it should update the app

Deposit some money into your bank account, then mint some stables to your address

Now, in your console you should be able to load the token and display your balance via (from the above deployment):
```py
 In [2]: token = project.Stablecoin.at("0x5FbDB2315678afecb367f032d93F642f64180aa3")
 In [3]: token.balanceOf(me)
Out [3]: <amount you minted yourself>
```

Finally, to get balance back to your account, redeem some tokens via:
```py
 In [4]: token.burn(token.balanceOf(me), sender=me)
```

You should see the "redemptions" bot pick this balance up and push it to your account!
