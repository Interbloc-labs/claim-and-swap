import time

import httpx
from mospy.clients import HTTPClient

from osmosis_protobuf.cosmos.distribution.v1beta1.tx_pb2 import MsgWithdrawDelegatorReward, MsgWithdrawValidatorCommission
from osmosis_protobuf.ibc.applications.transfer.v1.tx_pb2 import MsgTransfer

from osmosis_protobuf.osmosis.poolmanager.v1beta1.swap_route_pb2 import SwapAmountInSplitRoute, SwapAmountInRoute
from osmosis_protobuf.osmosis.poolmanager.v1beta1.tx_pb2 import MsgSplitRouteSwapExactAmountIn

from cas_bot.config import CONFIG

from mospy import Account, Transaction

from cas_bot.exceptions import HttpException
from cas_bot.query.http import get_delegations, get_events
from cas_bot.utils import sleep_until_tx_confirmed

client = HTTPClient(api=CONFIG.API)

account = Account(
    seed_phrase=CONFIG.SEED,
    hrp=CONFIG.HRP,
    slip44=CONFIG.SLIP44,
    protobuf="osmosis"
)

client.load_account_data(account=account)

validator_addresses = get_delegations(
    address=account.address
)

# Create transaction
transaction = Transaction(
    account=account,
    chain_id=CONFIG.CHAINID,
    gas=1000,
    protobuf="osmosis"
)

for validator_address in validator_addresses:
    transaction.add_raw_msg(
        type_url="/cosmos.distribution.v1beta1.MsgWithdrawDelegatorReward",
        unpacked_msg=MsgWithdrawDelegatorReward(
            delegator_address=account.address,
            validator_address=validator_address
        )
    )

if CONFIG.VALIDATOR_ADDRESS:
    transaction.add_raw_msg(
        type_url="/cosmos.distribution.v1beta1.MsgWithdrawValidatorCommission",
        unpacked_msg=MsgWithdrawValidatorCommission(
            validator_address=CONFIG.VALIDATOR_ADDRESS
        )
    )

transaction.set_fee(
    amount=CONFIG.FEE,
    denom=CONFIG.FEE_DENOM
)

client.estimate_gas(
    transaction=transaction
)
tx_response = client.broadcast_transaction(
    transaction=transaction
)

tx_hash = tx_response["hash"]
print(f"Claiming the staking rewards: {tx_hash}")

# Wait for transaction to be included into the block
attempts = 0

while attempts < 20 and attempts != -1:
    try:
        msgs = get_events(
            txhash=tx_hash
        )
        attempts = -1
    except HttpException or httpx.ReadTimeout:
        time.sleep(attempts + 4)
        attempts += 1

if attempts != -1:
    print("Timeout while waiting for the transaction to hit the chain")
    exit()

account.increase_sequence()

# Parse the claimed reward from the transaction logs
rewards = []
for msg in msgs:
    for event in msg["events"]:
        if event["type"] == "withdraw_rewards" or event["type"] == "withdraw_commission":
            for attribute in event["attributes"]:
                if attribute["key"] == "amount":
                    values = attribute["value"]
                    for value in values.split(","):
                        if "ibc" in value:
                            print(value)
                            amount, denom = value.split("ibc/")
                            denom = "ibc/" + denom
                        elif CONFIG.DENOM in value:
                            amount = value.replace(CONFIG.DENOM, "")
                            denom = CONFIG.DENOM
                        else:
                            print(f"Claim amount couldn't be parsed: {value}")
                            continue
                        rewards.append({
                            "amount": amount,
                            "denom": denom
                        })

# Calculate the native staking reward which will be comverted into USDC
native_reward = sum([int(reward["amount"]) for reward in rewards if reward["denom"] == CONFIG.DENOM])

# Create the Osmosis account and client
osmosis_account = Account(
    seed_phrase=CONFIG.SEED,
    hrp="osmo",
    protobuf="osmosis"
)

osmosis_client = HTTPClient(api=CONFIG.OSMOSIS_API)
osmosis_client.load_account_data(account=osmosis_account)


# Create ibc transaction to Osmosis
ibc_transaction = Transaction(
    account=account,
    chain_id=CONFIG.CHAINID,
    gas=1000,
    protobuf="osmosis"
)

ibc_transaction.set_fee(
    amount=5000,
    denom=CONFIG.DENOM
)

token = {
    "amount": str(native_reward),
    "denom": CONFIG.DENOM
}

ibc_msg = MsgTransfer(
    sender=account.address,
    receiver=osmosis_account.address,
    source_port="transfer",
    source_channel=CONFIG.CHANNEL_TO_OSMOSIS,
    timeout_timestamp=time.time_ns() + 600 * 10 ** 9,
    token=token
)

ibc_transaction.add_raw_msg(
    type_url="/ibc.applications.transfer.v1.MsgTransfer",
    unpacked_msg=ibc_msg
)

client.estimate_gas(
    transaction=ibc_transaction
)

ibc_transaction_hash = client.broadcast_transaction(
    transaction=ibc_transaction
)

print(f"Submitted IBC transfer: {ibc_transaction_hash['hash']}" + f" and log {ibc_transaction_hash['log'] if ibc_transaction_hash['log'] else ''} ")
sleep_until_tx_confirmed(tx_hash=ibc_transaction_hash["hash"])
print(f"Waiting for the IBC transfer to complete (Waiting time 30 seconds)")
time.sleep(30)

# Osmosis Trade

osmosis_swap_transaction = Transaction(
    account=osmosis_account,
    gas=CONFIG.OSMOSIS_TX_GAS,
    chain_id="osmosis-1",
    protobuf="osmosis"
)

osmosis_swap_transaction.set_fee(
    amount=9000,
    denom="uosmo"
)

route_response = httpx.get(
    url=f"https://sqs.osmosis.zone/router/quote?tokenIn={native_reward}{CONFIG.OSMOSIS_DENOM}&tokenOutDenom={CONFIG.OSMOSIS_USDC_DENOM}"
)


if route_response.status_code != 200:
    print("Error while getting route for trade")

route_data = route_response.json()


swap_msg = MsgSplitRouteSwapExactAmountIn(
    sender=osmosis_account.address,
    token_in_denom=CONFIG.OSMOSIS_DENOM,
    token_out_min_amount=str(int(int(route_data["amount_out"]) * 0.95)),
    routes=[SwapAmountInSplitRoute(
        pools=[SwapAmountInRoute(
            pool_id=route["id"],
            token_out_denom=route["token_out_denom"]
        ) for route in route_data["route"][0]["pools"]],
        token_in_amount=str(native_reward)
    )]

)

osmosis_swap_transaction.add_raw_msg(
    unpacked_msg=swap_msg,
    type_url="/osmosis.poolmanager.v1beta1.MsgSplitRouteSwapExactAmountIn"
)

#osmosis_client.estimate_gas(
#    transaction=osmosis_swap_transaction,
#    multiplier=3
#)

swap_tx_response = osmosis_client.broadcast_transaction(
    transaction=osmosis_swap_transaction
)

print(f"Swap on Osmosis: {swap_tx_response['hash']}" + f" and log {swap_tx_response['log'] if swap_tx_response['log'] else ''} ")
