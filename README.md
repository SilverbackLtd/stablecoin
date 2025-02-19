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

Well, anyone can use our demo stablecoin! Just visit <!-- TODO: Add link to demo -->

But more importantly, this is a demo operating 2 different Silverback bots across 3 different chains at the same time, all linked to a central webapp and database.
This type of microservice architecture serves to help you scale operations across many different chains at the same time.
And it's easy! Thanks to the power of Python, Ape's plugin system, and Silverback's simplified UX for making chain monitoring and transactional response easy to automate.

## How do I get in touch?

If you are interested in this demo, it's really easy to get started by visiting the repo and starting to modify with the [SDK](https://docs.apeworx.io/silverback/stable/userguides/quickstart).
No signup required, just pull the fully OSS Silverback SDK and make your own bots to test locally with.
Once you are happy and want to run things in production, please visit us at https://silverback.apeworx.io to set up an account and get started with deploying on our cloud platform.

**Try Silverback Today!**

## Local Demo

You can run this demo locally. First, start an instance of anvil via:

```sh
ape networks run --network :local
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
silverback run redemptions --network :local
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

## Deploy this example

You can deploy this example on the [Silverback Platform](https://silverback.apeworx.io) and [Heroku](https://heroku.com) (for the webapp).

### Cloud Signer

First off, you are going to want to install and configure a supported Ape cloud signer plugin for our Silverback bots to use.
We are going to install the AWS plugin for this particular demo and set up two cloud signers, `compliance` and `redemption`.
Follow the [instructions in the plugin docs](https://github.com/ApeWorX/ape-aws?tab=readme-ov-file#using-cli-tool) for help setting up your keys.

We need to create two signer keys:

```bash
$ ape aws keys generate compliance-key
Key created '<COMPLIANCE_KEY_ID>'.
Key policies updated for compliance-key
$ ape aws keys generate mint-key
Key created '<MINT_KEY_ID>'.
Key policies updated for mint-key
$ ape aws keys list
'compliance-key' (id: <COMPLIANCE_KEY_ID>)
'mint-key' (id: <MINT_KEY_ID>)
```

Then two accounts to access those signer keys:

```bash
$ ape aws users new compliance-signer
Created compliance-signer (arn:aws:iam::<AWS_ACCOUNT_ID>:user/compliance-signer)
Policy 'ApeAwsKeyAccessV1' added to user 'compliance-signer'.
$ ape aws users new mint-signer
Created mint-signer (arn:aws:iam::<AWS_ACCOUNT_ID>:user/mint-signer)
Policy 'ApeAwsKeyAccessV1' added to user 'mint-signer'.
$ ape aws users list
...  # other users
compliance-signer (arn:aws:iam::<AWS_ACCOUNT_ID>:user/compliance-signer)
mint-signer (arn:aws:iam::<AWS_ACCOUNT_ID>:user/mint-signer)
```

Next, grant access to our newly created users to their corresponding keys:

```bash
$ ape aws keys grant compliance-key -u compliance-signer
Key policies updated for compliance-key
$ ape aws keys grant mint-key -u mint-signer
Key policies updated for mint-key
```

Finally, create access tokens for these accounts and store them for later use:

```bash
$ ape aws users tokens new compliance-signer > .env.compliance-account
SUCCESS: Access key created for 'compliance-signer'
WARNING: Access key will not be available after this command
$ ape aws users tokens new mint-signer > .env.mint-account
SUCCESS: Access key created for 'mint-signer'
WARNING: Access key will not be available after this command
```

WARNING: Keep these access tokens safe, because they give full access to the corresponding account!

### Deploy Stablecoin to a Public Network

Next we need to deploy our stablecoin! We are going to deploy to a publiclly accessible network that users can interact with,
and that our bots can monitor. Deploy via the following:

```bash
ape run deploy --minter mint-signer --compliance compliance-signer --account <YOUR_ALIAS> --network ethereum:sepolia
INFO:     Confirmed 0x123... (total fees paid = ...)
SUCCESS:  Contract 'Stablecoin' deployed to: <YOUR_DEPLOYED_STABLECOIN>
```

Keep note of that address, we're gonna need it for later.

### Deploy Web App

There are various ways to host a FastAPI app, and we are not going to cover them here.
However you deploy it, you will need a few environment variables to get your app and bots running.
Also make sure that you build your webapp with the `ape-aws` plugin so it has access to minting your tokens.

The app will need the following environment variable:

```sh
STABLECOIN_ADDRESSES='{"ethereum:sepolia":"<YOUR_DEPLOYED_STABLECOIN>"}'
AWS_ACCOUNT_ID=# Stored in your `.env.mint-account`
AWS_SECRET_KEY=# Stored in your `.env.mint-account`

```

When you deploy your app, please make sure to use a fresh, randomly generated value for `API_KEY` which you should keep track of until later.

We made use of SQLModel to manage an SQL database, you can refer to your cloud provider's docs for how to provision Postgres.

Finally, take note of the location of your deployed, hosted webapp.
The bots are going to need this url to connect to the internal api hosted by your app.

### Silverback Bot Cluster

Once we have the cloud signers set up, we are going to create a [Silverback Bot Cluster](https://silverback.apeworx.io) to run our 2 bots.
Follow the [instructions in the Silverback docs](https://docs.apeworx.io/silverback/stable/userguides/managing.html#managing-a-cluster) for help
deploying a new paid cluster. To provision a new cluster, do:

```bash
$ silverback cluster new  <WORKSPACE_NAME> --name stablecoin
$ silverback cluster pay create <WORKSPACE_NAME>/stablecoin  # payment options...
# Wait time for provisioning
$ silverback cluster list <WORKSPACE_NAME>
- stablecoin (Running)
$ silverback cluster info -c <WORKSPACE_NAME>/stablecoin
Cluster Version: ...
```

Once that is set up, we need to create a variable group in our cluster so our compliance bot can access their key.
Run the following to set that up:

```bash
$ silverback cluster vars new -c <WORKSPACE_NAME>/stablecoin \
  compliance-account -e $(sed 's/^/-e /' .env.compliance-account | xargs -r)
created: ...
name: compliance-account
variables:
- AWS_ACCOUNT_ID
- AWS_SECRET_KEY
$ silverback cluster vars list -c <WORKSPACE_NAME>/stablecoin
- compliance-account
```

Next, we need to create one variable group containing a way to connect to our webapp's internal API for both bots:

```bash
$ silverback cluster vars new -c <WORKSPACE_NAME>/stablecoin \
  webapp-internal -e $(sed 's/^/-e /' .env.app | xargs -r)
created: ...
name: webapp-internal
variables:
- BANK_API_KEY
- BANK_URI
$ silverback cluster vars list -c <WORKSPACE_NAME>/stablecoin
- compliance-account
- webapp-internal
```

After that, we need to create one more variable group containing our deployed stablecoin address:

```bash
$ silverback cluster vars new -c <WORKSPACE_NAME>/stablecoin \
  deployments -e STABLECOIN_ADDRESSES='{"ethereum:sepolia":"<YOUR_DEPLOYED_STABLECOIN>"}'
created: ...
name: deployments
variables:
- STABLECOIN_ADDRESSES
$ silverback cluster vars list -c <WORKSPACE_NAME>/stablecoin
- compliance-account
- deployments
- webapp-internal
```

We can finally deploy our bot!
To do that, we need to build Docker images of our two bots.
We are not going to cover how to build the bots here, but you can [check out the docs](https://docs.apeworx.io/silverback/stable/userguides/deploying.html#building-your-bot) to learn how to do that.
Thankfully, our images are already pre-built.
To deploy we will do the following:

```sh
$ silverback cluster bots new -c <WORKSPACE_NAME>/stablecoin \
  compliance-sepolia --network ethereum:sepolia \
  --image ghcr.io/silverbackltd/stablecoin-compliance:latest \
  --account compliance-signer --group compliance-account \
  --group deployments --group webapp-internal
Name: 'compliance-sepolia'
Image: 'ghcr.io/silverbackltd/stablecoin-compliance:latest'
Network: 'ethereum:sepolia:node'
Environment:
  compliance:
  - AWS_ACCOUNT_ID
  - AWS_SECRET_KEY
  deployments:
  - STABLECOIN_ADDRESSES
  webapp-internal:
  - BANK_API_KEY
  - BANK_URI

Do you want to create and start running this bot? [y/N]: y
Bot 'compliance-sepolia' (...) deploying...
$ silverback cluster bots new -c <WORKSPACE_NAME>/stablecoin \
  redemptions-sepolia --network ethereum:sepolia \
  --image ghcr.io/silverbackltd/stablecoin-redemptions:latest \
  --group deployments --group webapp-internal
Name: 'redemptions-sepolia'
Image: 'ghcr.io/silverbackltd/stablecoin-redemptions:latest'
Network: 'ethereum:sepolia:node'
Environment:
  deployments:
  - STABLECOIN_ADDRESSES
  webapp-internal:
  - BANK_API_KEY
  - BANK_URI

Do you want to create and start running this bot? [y/N]: y
Bot 'redemptions-sepolia' (...) deploying...
$ silverback cluster bots list -c <WORKSPACE_NAME>/stablecoin
ethereum:
    sepolia:
      - compliance-sepolia
      - redemptions-sepolia
```

### Use the App

And that's it! Visit your webapp at the deployed address to mint stablecoins to yourself, then burn them and watch your bank account balance come back.
Also, if you start transfering stablecoins to other accounts, the `compliance` bot will watch and randomly flag your account (so be careful!).
