import time

import httpx

from cas_bot.config import CONFIG
from cas_bot.exceptions import HttpException


def get_balance(address: str):
    path = "/cosmos/bank/v1beta1/balances/" + address

    balance_response = httpx.get(CONFIG.API + path)

    if balance_response.status_code != 200:
        raise HttpException()

    balances = balance_response.json()

    if "balances" not in balances:
        return

    for balance_item in balances["balances"]:
        denom = balance_item["denom"]
        amount = balance_item["amount"]

        yield (amount, denom)

def get_delegations(address: str):
    path = "/cosmos/staking/v1beta1/delegations/" + address

    delegations_response = httpx.get(CONFIG.API + path)

    if delegations_response.status_code != 200:
        raise HttpException()

    delegations = delegations_response.json()

    for delegation_item in delegations["delegation_responses"]:
        delegation = delegation_item["delegation"]

        validator_address = delegation["validator_address"]
        yield validator_address

def get_events(txhash: str):
    path = "/cosmos/tx/v1beta1/txs/" + txhash

    attempts = 0
    while attempts < 3 and attempts != -1:
        try:
            transactions_response = httpx.get(CONFIG.API + path)
        except httpx.ReadTimeout:
            attempts += 1
            time.sleep(1)
        else:
            attempts = -1

    if attempts != -1:
        print(f"Error while getting events for {txhash}")
        raise HttpException()


    if transactions_response.status_code != 200:
        raise HttpException()

    return transactions_response.json()["tx_response"]["logs"]


def get_transaction(hash: str):
    return