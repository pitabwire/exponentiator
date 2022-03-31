import decimal
import logging
import random
import time

import web3
from eth_account.signers.local import LocalAccount
from pycoingecko import CoinGeckoAPI

from node import NodeInterface
from notification import NotifierInterface
from utility import get_contract

log = logging.getLogger(__name__)

main_contract_abi = '[{"inputs":[{"internalType":"address","name":"account","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"}]'
super_human_contract_abi = '[{"inputs":[{"internalType":"address","name":"account","type":"address"}],"name":"_getNodesNames","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"}]'
tier_contract_abi = '[{"inputs": [{"internalType": "address","name": "account","type": "address"},{"internalType": "string","name": "tierName","type": "string"}],"name": "getRewardAmountOf","outputs": [{"internalType": "uint256","name": "","type": "uint256"}],"stateMutability": "view","type": "function"},{"inputs": [{"internalType": "string","name": "tierName","type": "string"},{"internalType": "string","name": "nodeName","type": "string"}],"name": "compoundInto","outputs": [],"stateMutability": "nonpayable","type": "function"},{"inputs": [{"internalType": "string","name": "tierName","type": "string"},{"internalType": "string","name": "compoundTierName","type": "string"},{"internalType": "string","name": "nodeName","type": "string"}],"name": "compoundTierInto","outputs": [],"stateMutability": "nonpayable","type": "function"},{"inputs": [{"internalType": "address","name": "account","type": "address"}],"name": "getNodeNumberOf","outputs": [{"internalType": "uint256","name": "","type": "uint256"}],"stateMutability": "view","type": "function"},{"inputs": [{"internalType": "uint256","name": "blocktime","type": "uint256"},{"internalType": "string","name": "tierName","type": "string"}],"name": "cashoutReward","outputs": [],"stateMutability": "nonpayable","type": "function"}]'


class PowerNode(NodeInterface):
    tier_list = ['SUPERHUMAN']

    def __init__(self, notifier):
        super().__init__(notifier=notifier)
        self.ftm_connection = None
        self.main_contract = None
        self.node_contract = None
        self.tier_contract = None

        self.last_send_time = dict()

    def __get_network_connection(self, connection_attempts=5):
        """
            Obtains a new connection to the fantom network
        :param connection_attempts:
        :return:
        """
        if not self.ftm_connection:
            self.ftm_connection = web3.Web3(web3.Web3.HTTPProvider('https://rpcapi.fantom.network/'))

        if self.ftm_connection.isConnected():
            return self.ftm_connection

        if connection_attempts <= 1:
            raise ConnectionError("Unable to connect to the fantom network")

        time.sleep(1)
        self.ftm_connection = None
        return self.__get_network_connection(connection_attempts=connection_attempts - 1)

    def setup(self):
        """
            Initiates all the required components to run node functions
        :return:
        """
        ftm_conn = self.__get_network_connection()

        self.main_contract = get_contract(ftm_conn, **dict(address='0x131c7afb4E5f5c94A27611f7210dfEc2215E85Ae',
                                                           abi=main_contract_abi))
        self.tier_contract = get_contract(ftm_conn, **dict(address='0x730255d50C9FE605172eE4e860ec0109dd61e867',
                                                           abi=tier_contract_abi))
        self.node_contract = get_contract(ftm_conn, **dict(address='0xC8007751603bB3E45834A59af64190Bb618b4a83',
                                                           abi=super_human_contract_abi))

    def get_wallet_balance(self, wallet_address):
        """
            Obtains the power balance of the wallet.
        :param wallet_address:
        :return:
        """
        wallet_balance = self.main_contract.functions.balanceOf(wallet_address).call()
        return web3.Web3.fromWei(wallet_balance, 'ether')

    def get_node_count(self, wallet_address: str):
        """
            Obtains the count of nodes given a wallet address

        :param wallet_address:
        :return: int
        """
        return self.tier_contract.functions.getNodeNumberOf(wallet_address).call()

    def get_account_rewards_balance(self, wallet_address):
        """
            Obtains the rewards tied to the wallet for all the running nodes.

        :param wallet_address:
        :return:
        """

        account_rewards = 0
        for tier in self.tier_list:
            tier_rewards = self.tier_contract.functions.getRewardAmountOf(wallet_address, tier).call()
            account_rewards += web3.Web3.fromWei(tier_rewards, 'ether')
        return account_rewards

    def compound(self, account: LocalAccount, compounding_name: str):
        """
            Internal method responsible for auto compounding our rewards whenever they are ready.

        :param account:
        :param compounding_name:
        :param tier:
        :return:
        """

        compounding_done = False
        for tier in self.tier_list:
            nonce = self.tier_contract.web3.eth.get_transaction_count(account.address)
            gas_price = self.tier_contract.web3.eth.gas_price

            compound_tx = self.tier_contract.functions.compoundTierInto(tier, tier, compounding_name). \
                buildTransaction(
                {
                    'from': account.address,
                    'nonce': nonce,
                    "gasPrice": gas_price,
                }
            )

            signed_compound_txn = account.sign_transaction(compound_tx)
            compound_tx_hash = self.tier_contract.web3.eth.send_raw_transaction(signed_compound_txn.rawTransaction)

            compound_tx_receipt = self.tier_contract.web3.eth.wait_for_transaction_receipt(compound_tx_hash)
            log.info(" perform_compounding -- completed successful compounding of : [%s] with receipt  %s",
                     compounding_name, compound_tx_receipt)
            compounding_done = True
        return compounding_done

    def get_reward_in_usd(self, ):
        """
            This function gets the cost of one POWER unit in USD
        :return: USD value of rewards
        """
        coin_gecko = CoinGeckoAPI()
        price = coin_gecko.get_price(ids='power-nodes', vs_currencies='usd')
        return decimal.Decimal(price['power-nodes']['usd'])

    def get_compounding_name(self, wallet_address):
        """
            Using the existing names in the pool we obtain a list of all available nodes and randomly choose
            one that has no number as a suffix (Seed name). We then obtain another list of all the node names
            with a prefix equivalent to the seed name and return the seed name concatenated with length of prefix list.

        :param contract:
        :param wallet_address:
        :return:
        """

        all_nodes = self.node_contract.functions._getNodesNames(wallet_address).call()
        nodes_list = all_nodes.split('#')
        if not nodes_list:
            return "auto_compound"

        source_names = list(filter(lambda name: not name[-1].isdigit(), nodes_list))
        random_node_name = random.choice(source_names)

        source_name_descendants = list(filter(lambda name: name.startswith(random_node_name), nodes_list))
        return f'{random_node_name}_{len(source_name_descendants)}'

    def can_compound(self, investment: dict):
        """
            Checks populated investment for compounding opportunities
        :param investment:
        :return:
        """
        rewards = investment['rewards']
        return rewards > 75 or (rewards >= 38 and (rewards + investment['balance']) >= 75)
