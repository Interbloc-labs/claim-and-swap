import os

from dotenv import load_dotenv

load_dotenv()

class CONFIG:
    API = os.getenv("API")
    OSMOSIS_API = os.getenv("OSMOSIS_API")
    OSMOSIS_DENOM = os.getenv("OSMOSIS_DENOM")
    GRPC = "sentinel-mainnet-grpc.autostake.com:443"
    CHAINID = os.getenv("CHAINID")
    SEED = os.getenv("SEED")
    DENOM = os.getenv("DENOM")
    HRP = os.getenv("HRP")
    SLIP44 = int(os.getenv("SLIP44"))

    VALIDATOR_ADDRESS = os.getenv("VALIDATOR_ADDRESS")

    FEE = int(os.getenv("FEE"))
    FEE_DENOM = os.getenv("FEE_DENOM")

    CHANNEL_TO_OSMOSIS = os.getenv("CHANNEL_TO_OSMOSIS")

    OSMOSIS_USDC_DENOM = os.getenv("OSMOSIS_USDC_DENOM")