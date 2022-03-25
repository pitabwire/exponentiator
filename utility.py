import json
import os

from eth_account import Account
import web3

ENVIRONMENT_SERVICE_NAME_KEY = 'SERVICE_NAME'
ENVIRONMENT_PRIVATE_KEY_MAP_KEY = 'PRIVATE_KEY_MAP'


def get_service_name():
    service_name = 'exponentiator'
    service_name = os.getenv(ENVIRONMENT_SERVICE_NAME_KEY, service_name)
    return service_name


def load_abi_strings(source_file: str):
    """
        Loads abi strings from json files
    :param source_file:
    :return:
    """
    with open(source_file, 'r') as f:
        abi_string = json.load(f)
    return abi_string


def get_contract(web3_connection: web3.Web3, address: str, abi: str):
    """
        Given a web3 connection this method creates a contract connection
        for use with the address and abi given to it.

    :param web3_connection:
    :param address:
    :param abi:
    :return:
    """
    web3_address = web3.Web3.toChecksumAddress(address)
    return web3_connection.eth.contract(address=web3_address, abi=abi)


def get_private_key_map():
    """
        The private keys for your wallet to be used in this program can be specified
        by a comma separated list of addresses prefixed by
        a piped name e.g. account1|private_key1....,account2|private_keyx....
    :return:
    """
    wallet_map = {}
    wallet_map_str = os.getenv(ENVIRONMENT_PRIVATE_KEY_MAP_KEY)
    if wallet_map_str:

        wallet_list = wallet_map_str.split(',')
        for wallet_item in wallet_list:
            if '|' not in wallet_item:
                wallet_map['default'] = Account.from_key(wallet_item)
            else:
                wallet_name, wallet_address = wallet_item.split('|')
                wallet_map[wallet_name] = Account.from_key()

        return wallet_map

    raise ValueError('A private key for is missing. Try setting Environment : %s'.format(
        ENVIRONMENT_PRIVATE_KEY_MAP_KEY))


