import decimal
import logging
import random

import web3
from eth_account.signers.local import LocalAccount
from pycoingecko import CoinGeckoAPI

from dex.spookyswap import SpookySwap
from node import NodeInterface
from notification import NotifierInterface
from utility import get_contract, get_network_connection

log = logging.getLogger(__name__)

main_contract_abi = '[{"inputs":[{"internalType":"address","name":"account","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"}]'
super_human_contract_abi = '[{"inputs":[{"internalType":"address","name":"account","type":"address"}],"name":"_getNodesNames","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"}]'
tier_contract_abi = '[{"inputs": [{"internalType": "address","name": "account","type": "address"},{"internalType": "string","name": "tierName","type": "string"}],"name": "getRewardAmountOf","outputs": [{"internalType": "uint256","name": "","type": "uint256"}],"stateMutability": "view","type": "function"},{"inputs": [{"internalType": "string","name": "tierName","type": "string"},{"internalType": "string","name": "nodeName","type": "string"}],"name": "compoundInto","outputs": [],"stateMutability": "nonpayable","type": "function"},{"inputs": [{"internalType": "string","name": "tierName","type": "string"},{"internalType": "string","name": "compoundTierName","type": "string"},{"internalType": "string","name": "nodeName","type": "string"}],"name": "compoundTierInto","outputs": [],"stateMutability": "nonpayable","type": "function"},{"inputs": [{"internalType": "address","name": "account","type": "address"}],"name": "getNodeNumberOf","outputs": [{"internalType": "uint256","name": "","type": "uint256"}],"stateMutability": "view","type": "function"},{"inputs": [{"internalType": "string","name": "tierName","type": "string"}],"name": "cashoutAll","outputs": [],"stateMutability":"nonpayable","type": "function" }]'


class PowerNode(NodeInterface):
    NODE_TYPE_NUCLEAR = 'SUPERHUMAN'
    NODE_TYPE_HYDRO = 'HUMAN'
    NODE_TYPE_SOLAR = 'MICROSCOPIC'
    NODE_TYPE_WIND = 'FLATVERSAL'

    tier_list = [NODE_TYPE_NUCLEAR]
    NODE_REWARD_MAP = {
        NODE_TYPE_NUCLEAR: 0.7
    }

    NODE_CREATION_COST = {
        NODE_TYPE_NUCLEAR: 75
    }

    def __init__(self, notifier: NotifierInterface):
        super().__init__(notifier=notifier)
        self.ftm_connection = None
        self.main_contract = None
        self.super_human_contract = None
        self.tier_contract = None
        self.dex = None
        self.last_send_time = dict()

    def setup(self):
        """
            Initiates all the required components to run node functions
        :return:
        """
        self.ftm_connection = get_network_connection(self.ftm_connection)

        self.main_contract = get_contract(self.ftm_connection,
                                          **dict(address='0x131c7afb4E5f5c94A27611f7210dfEc2215E85Ae',
                                                 abi=main_contract_abi))
        self.tier_contract = get_contract(self.ftm_connection,
                                          **dict(address='0x8cb77FFa9A7B82541E96db41C35e307d9d16A294',
                                                 abi=tier_contract_abi))
        self.super_human_contract = get_contract(self.ftm_connection,
                                                 **dict(address='0xC8007751603bB3E45834A59af64190Bb618b4a83',
                                                        abi=super_human_contract_abi))

    def get_dex(self):
        """
            Returns instance of spooky swap
        :return:
        """

        if not self.dex:
            self.dex = SpookySwap(notifier=self.notifier)
            self.dex.setup()
        return self.dex

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

    def get_reward_per_hour(self, **kwargs):
        """
            Obtains the amount of rewards a node can generate per hour

        :param kwargs:
        :return:
        """

        node_type = self.NODE_TYPE_NUCLEAR
        if 'node_type' in kwargs:
            node_type = kwargs['node_type']

        return self.NODE_REWARD_MAP[node_type] / 24

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

        :param wallet_address:
        :return:
        """

        all_nodes = self.super_human_contract.functions._getNodesNames(wallet_address).call()
        nodes_list = all_nodes.split('#')
        if not nodes_list:
            return "auto_compound"

        source_names = list(filter(lambda name: not name[-1].isdigit(), nodes_list))
        random_node_name = random.choice(source_names)

        source_name_descendants = list(filter(lambda name: name.startswith(random_node_name), nodes_list))
        return f'{random_node_name}_{len(source_name_descendants)}'

    def can_compound(self, investment: dict, compound_pct=100):
        """
            Checks populated investment for compounding opportunities
        :param investment:
        :param compound_pct:
        :param spend_pct:
        :return:
        """
        node_type = investment.get('node_type', self.NODE_TYPE_NUCLEAR)
        compounding_cost = self.NODE_CREATION_COST[node_type]

        if compound_pct <= 0 or compound_pct > 100:
            return False

        rewards = investment['rewards']

        true_compounding_cost = (100 / compound_pct * compounding_cost)

        if rewards >= true_compounding_cost:
            return True

        if rewards >= compounding_cost / 2:

            if rewards + investment['balance'] > true_compounding_cost:

                if compound_pct == 100:
                    return True

                if investment['balance'] > compounding_cost:
                    return True

        return False

    def claim_rewards(self, account: LocalAccount, **kwargs):
        """ This function claims rewards from a compounding node farm
        utilizing the compounding factor to determine what to leave behind
        """
        node_type = kwargs.get('node_type', self.NODE_TYPE_NUCLEAR)

        nonce = self.tier_contract.web3.eth.get_transaction_count(account.address)
        gas_price = self.tier_contract.web3.eth.gas_price

        claim_tx = self.tier_contract.functions.cashoutAll(node_type). \
            buildTransaction(
            {
                'from': account.address,
                'nonce': nonce,
                "gasPrice": gas_price,
            }
        )

        signed_compound_txn = account.sign_transaction(claim_tx)
        compound_tx_hash = self.tier_contract.web3.eth.send_raw_transaction(signed_compound_txn.rawTransaction)

        compound_tx_receipt = self.tier_contract.web3.eth.wait_for_transaction_receipt(compound_tx_hash)
        log.info(" claim_rewards -- completed successful claim of balance with receipt  %s",
                 compound_tx_receipt)
