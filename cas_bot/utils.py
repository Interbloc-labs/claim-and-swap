import time

import httpx

from cas_bot.exceptions import HttpException
from cas_bot.query.http import get_events


def sleep_until_tx_confirmed(tx_hash):
    attempts = 0
    while attempts < 10 and attempts != -1:
        try:
            msgs = get_events(
                txhash=tx_hash
            )
            attempts = -1
            return True
        except HttpException or httpx.ReadTimeout:
            time.sleep(attempts + 4)
            attempts += 1

    return True
