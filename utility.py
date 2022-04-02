import json
import math
import os
import time

import web3
from cryptography.fernet import Fernet
from eth_account import Account

ENVIRONMENT_SERVICE_NAME_KEY = 'SERVICE_NAME'
ENVIRONMENT_PRIVATE_KEY_MAP_KEY = 'PRIVATE_KEY_MAP'
ENVIRONMENT_ENCRYPTION_SECRET = 'ENCRYPTION_SECRET'


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
    encryption_secret_str = os.getenv(ENVIRONMENT_ENCRYPTION_SECRET)
    wallet_map_str = os.getenv(ENVIRONMENT_PRIVATE_KEY_MAP_KEY)
    if wallet_map_str:

        wallet_list = wallet_map_str.split(',')
        for wallet_item in wallet_list:
            if '|' not in wallet_item:
                acc_key = decrypt_key(key=encryption_secret_str, enc_message=wallet_item)
                wallet_map['default'] = Account.from_key(acc_key)
            else:
                wallet_name, wallet_address = wallet_item.split('|')
                acc_key = decrypt_key(key=encryption_secret_str, enc_message=wallet_address)
                wallet_map[wallet_name] = Account.from_key(acc_key)

        return wallet_map

    raise ValueError('A private key is missing. Try setting Environment : %s'.format(
        ENVIRONMENT_PRIVATE_KEY_MAP_KEY))


def get_network_connection(web3_connection, connection_attempts=5):
    """
        Obtains a new connection to the fantom network
    :param web3_connection:
    :param connection_attempts:
    :return:
    """
    if not web3_connection:
        web3_connection = web3.Web3(web3.Web3.HTTPProvider('https://rpcapi.fantom.network/'))

    if web3_connection.isConnected():
        return web3_connection

    if connection_attempts <= 1:
        raise ConnectionError("Unable to connect to the fantom network")

    time.sleep(math.pow(2, 5 - connection_attempts))
    return get_network_connection(web3_connection=web3_connection, connection_attempts=connection_attempts - 1)


def decrypt_key(key: str, enc_message: str):
    """
        All account private keys should be secret.
        To encrypt a key use : f = Fernet(key);msg = f.encrypt(message)
    :return:
    """

    fernet = Fernet(key)
    message_bytes = fernet.decrypt(enc_message.encode())
    return message_bytes.decode()
