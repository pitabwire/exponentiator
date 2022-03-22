import datetime
import decimal
import json
import logging
import os
import random
import smtplib
import ssl
import time
from datetime import datetime, timedelta

import web3
from eth_account import Account
from pycoingecko import CoinGeckoAPI
from web3.exceptions import ContractLogicError

log = logging.getLogger(__name__)

service_name = 'exponentiator'

ENVIRONMENT_SLEEP_DURATION_KEY = 'SLEEP_DURATION'
ENVIRONMENT_PRIVATE_KEY_MAP_KEY = 'PRIVATE_KEY_MAP'
ENVIRONMENT_EMAIL_USERNAME_KEY = 'EMAIL_USERNAME'
ENVIRONMENT_EMAIL_PASSWORD_KEY = 'EMAIL_PASSWORD'
ENVIRONMENT_EMAIL_RECEIVER_ADDRESS_KEY = 'EMAIL_RECEIVER_ADDRESS'
ENVIRONMENT_EMAIL_SMTP_SERVER_HOST_KEY = 'EMAIL_SMTP_SERVER_HOST'
ENVIRONMENT_EMAIL_SMTP_SERVER_PORT_KEY = 'EMAIL_SMTP_SERVER_PORT'

main_contract_abi = '[{"inputs":[{"internalType":"address","name":"account","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"}]'
super_human_contract_abi = '[{"inputs":[{"internalType":"address","name":"account","type":"address"}],"name":"_getNodesNames","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"}]'
tier_contract_abi = '[{"inputs": [{"internalType": "address","name": "account","type": "address"},{"internalType": "string","name": "tierName","type": "string"}],"name": "getRewardAmountOf","outputs": [{"internalType": "uint256","name": "","type": "uint256"}],"stateMutability": "view","type": "function"},{"inputs": [{"internalType": "string","name": "tierName","type": "string"},{"internalType": "string","name": "nodeName","type": "string"}],"name": "compoundInto","outputs": [],"stateMutability": "nonpayable","type": "function"},{"inputs": [{"internalType": "string","name": "tierName","type": "string"},{"internalType": "string","name": "compoundTierName","type": "string"},{"internalType": "string","name": "nodeName","type": "string"}],"name": "compoundTierInto","outputs": [],"stateMutability": "nonpayable","type": "function"},{"inputs": [{"internalType": "address","name": "account","type": "address"}],"name": "getNodeNumberOf","outputs": [{"internalType": "uint256","name": "","type": "uint256"}],"stateMutability": "view","type": "function"},{"inputs": [{"internalType": "uint256","name": "blocktime","type": "uint256"},{"internalType": "string","name": "tierName","type": "string"}],"name": "cashoutReward","outputs": [],"stateMutability": "nonpayable","type": "function"}]'


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


class EmailHandler:

    def __init__(self, server, port, sender_username, sender_password, receiver_email):
        self.smtp_server = server
        self.smtp_server_port = port
        self.sender_email = sender_username
        self.password = sender_password
        self.receiver_email = receiver_email

    def send(self, subject, content):
        message = f"""\
        Subject: {subject}

        {content}"""

        context = ssl.create_default_context()
        with smtplib.SMTP(self.smtp_server, self.smtp_server_port) as server:
            server.starttls(context=context)
            server.login(self.sender_email, self.password)
            server.sendmail(self.sender_email, self.receiver_email, message)


class NodesManager:

    def __init__(self):
        self.coin_gecko = CoinGeckoAPI()

        self.ftm_connection = None

        self.main_contract_abi = dict(address='0x131c7afb4E5f5c94A27611f7210dfEc2215E85Ae',
                                      abi=main_contract_abi)
        self.tier_contract_abi = dict(address='0x730255d50C9FE605172eE4e860ec0109dd61e867',
                                      abi=tier_contract_abi)
        self.node_contract_abi = dict(address='0xC8007751603bB3E45834A59af64190Bb618b4a83',
                                      abi=super_human_contract_abi)
        self.last_send_time = dict()

    def get_network_connection(self, connection_attempts=5):
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
        return self.get_network_connection(connection_attempts=connection_attempts - 1)

    def get_wallet_balance(self, contract, wallet_address):
        """
            Obtains the power balance of the wallet.
        :param contract:
        :param wallet_address:
        :return:
        """
        wallet_balance = contract.functions.balanceOf(wallet_address).call()
        return web3.Web3.fromWei(wallet_balance, 'ether')

    def get_node_count(self, contract, wallet_address):
        """
            Obtains the count of nodes given a wallet address
        :param contract:
        :param wallet_address:
        :return:
        """
        return contract.functions.getNodeNumberOf(wallet_address).call()

    def get_account_rewards_balance(self, contract, wallet_address, tier='SUPERHUMAN'):
        """
            Obtains the rewards tied to the wallet for all the running nodes.

        :param tier:
        :param contract:
        :param wallet_address:
        :return:
        """

        node_rewards = contract.functions.getRewardAmountOf(wallet_address, tier).call()
        account_rewards = web3.Web3.fromWei(node_rewards, 'ether')
        return account_rewards

    def perform_compounding(self, tier_contract, account, compounding_name, tier='SUPERHUMAN'):
        """
            Internal method responsible for auto compounding our rewards whenever they are ready.

        :param tier_contract:
        :param account:
        :param compounding_name:
        :param tier:
        :return:
        """
        nonce = tier_contract.web3.eth.get_transaction_count(account.address)
        gas_price = tier_contract.web3.eth.gas_price

        compound_tx = tier_contract.functions.compoundTierInto(tier, tier, compounding_name). \
            buildTransaction(
            {
                'from': account.address,
                'nonce': nonce,
                "gasPrice": gas_price,
            }
        )

        signed_compound_txn = account.sign_transaction(compound_tx)
        compound_tx_hash = tier_contract.web3.eth.send_raw_transaction(signed_compound_txn.rawTransaction)

        compound_tx_receipt = tier_contract.web3.eth.wait_for_transaction_receipt(compound_tx_hash)
        log.info(" perform_compounding -- completed successful compounding of : [%s] with receipt  %s",
                 compounding_name, compound_tx_receipt)

    def get_power_in_usd(self, ):
        """
            This function gets the cost of one POWER unit in USD
        :return:
        """
        price = self.coin_gecko.get_price(ids='power-nodes', vs_currencies='usd')
        return decimal.Decimal(price['power-nodes']['usd'])

    def notify_compounding_opportunity(self, investment):

        hours_to_renotify_investment = 3
        if investment['name'] in self.last_send_time:
            if self.last_send_time[investment['name']] > (
                    datetime.now() - timedelta(hours=hours_to_renotify_investment)):
                log.info(" No need to over notify user in %s hours", hours_to_renotify_investment)
                return

        email_subject = " Compounding Opportunity"
        email_body = (
            f"""
                    You currently have enough rewards to create a new Nuclear Node  

                        Total Node count: {investment['node_count']}
                        Total Rewards  : {investment['rewards']}
                        Wallet Balance : {investment['balance']}

                    """)

        user_name = os.getenv(ENVIRONMENT_EMAIL_USERNAME_KEY)
        password = os.getenv(ENVIRONMENT_EMAIL_PASSWORD_KEY)
        receiver_email = os.getenv(ENVIRONMENT_EMAIL_RECEIVER_ADDRESS_KEY)

        smtp_server_host = os.getenv(ENVIRONMENT_EMAIL_SMTP_SERVER_HOST_KEY, 'in-v3.mailjet.com' )
        smtp_server_port = os.getenv(ENVIRONMENT_EMAIL_SMTP_SERVER_PORT_KEY, 587)

        if not all([user_name, password, receiver_email, smtp_server_host, smtp_server_port]):
            log.warning("No email credentials exist set the environment variables %s, %s, %s",
                        ENVIRONMENT_EMAIL_USERNAME_KEY, ENVIRONMENT_EMAIL_PASSWORD_KEY,
                        ENVIRONMENT_EMAIL_RECEIVER_ADDRESS_KEY)
            return

        # yagmail.SMTP(user_name, password)\
        #     .send(receiver_email,  email_subject, email_body)

        email_handler = EmailHandler(
            server=smtp_server_host,
            port=smtp_server_port,
            sender_username=user_name,
            sender_password=password,
            receiver_email=receiver_email
        )

        email_handler.send(subject=email_subject, content=email_body)
        self.last_send_time[investment['name']] = datetime.now()

    def initiate_auto_compounding(self, tier_contract, account, investment, compound_name):

        log.info(
            "Sufficient rewards to compound for [%s] at bal: %s and rewards: %s ",
            investment['name'], investment['balance'], investment['rewards'])

        self.perform_compounding(tier_contract=tier_contract,
                                 account=account,
                                 compounding_name=compound_name)
        self.notify_compounding_opportunity(investment=investment)

    @classmethod
    def get_name_for_compounding(cls, contract, wallet_address):
        """
            Using the existing names in the pool we obtain a list of all available nodes and randomly choose
            one that has no number as a suffix (Seed name). We then obtain another list of all the node names
            with a prefix equivalent to the seed name and return the seed name concatenated with length of prefix list.

        :param contract:
        :param wallet_address:
        :return:
        """

        all_nodes = contract.functions._getNodesNames(wallet_address).call()
        nodes_list = all_nodes.split('#')
        if not nodes_list:
            return "auto_compound"

        source_names = list(filter(lambda name: not name[-1].isdigit(), nodes_list))
        random_node_name = random.choice(source_names)

        source_name_descendants = list(filter(lambda name: name.startswith(random_node_name), nodes_list))
        return f'{random_node_name}_{len(source_name_descendants)}'

    def execute_check(self):

        """
            Glue method to get all investments given a list of wallets and
            excecutes logic to trigger further actions.
            Set conditions.
        :return:
        """

        log.info(" initiating checks for investments in power ")

        investment_map = dict()
        accounts_map = get_private_key_map()

        ftm_conn = self.get_network_connection()

        main_contract = get_contract(ftm_conn, **self.main_contract_abi)
        tier_contract = get_contract(ftm_conn, **self.tier_contract_abi)

        power_price_usd = self.get_power_in_usd()

        for wallet_name, account in accounts_map.items():
            wallet_address = account.address
            try:
                wallet_balance = self.get_wallet_balance(main_contract, wallet_address)
                node_count = self.get_node_count(tier_contract, wallet_address)
                rewards_total = self.get_account_rewards_balance(tier_contract, wallet_address)
                rewards_total_in_usd = power_price_usd * rewards_total

                investment = {
                    'name': wallet_name,
                    'address': wallet_address,
                    'balance': wallet_balance,
                    'node_count': node_count,
                    'rewards': rewards_total,
                    'power_price': power_price_usd}
                investment_map[wallet_name] = investment
                log.info(" Account [%s] has %s nodes and %s rewards with a value of %s", wallet_name, node_count,
                         rewards_total, rewards_total_in_usd)

            except ContractLogicError as e:
                if 'NO NODE OWNER' in str(e):
                    log.info("Account [%s] had no nodes attached", wallet_name)
                else:
                    log.warning(" Account [%s] experienced a contract error ", wallet_name, exc_info=True)

        # Check the compounding opportunities have been crossed
        for wallet_name, investment in investment_map.items():
            rewards = investment['rewards']
            if rewards > 50 or (rewards >= 25 and (rewards + investment['balance']) >= 50):
                node_contract = get_contract(ftm_conn, **self.node_contract_abi)
                compounding_name = self.get_name_for_compounding(contract=node_contract,
                                                                 wallet_address=investment['address'])
                self.initiate_auto_compounding(
                    tier_contract=tier_contract,
                    account=accounts_map[investment['name']],
                    investment=investment,
                    compound_name=compounding_name
                )
            else:
                log.info(
                    "Insufficient rewards to compound for [%s] at bal: %s and rewards: %s ",
                    investment['name'], investment['balance'], rewards)


class DaemonApp:

    def __init__(self):
        self.node_manager = None

    def setup(self, application_name):

        logging.basicConfig(level=logging.INFO)
        log.debug("Setting up application configuration for %s", application_name)
        self.node_manager = NodesManager()

    def run(self, application_name):
        should_run = True
        error_retry_duration = 1
        log.info(" run -- Initiating application  [%s]", application_name)

        while should_run:

            try:
                self.node_manager.execute_check()

                sleep_duration = os.getenv(ENVIRONMENT_SLEEP_DURATION_KEY, 5 * 60)
                log.debug(" run -- sleeping for %s before checking again, Edit Env [%s]", sleep_duration,
                          ENVIRONMENT_SLEEP_DURATION_KEY)
                time.sleep(sleep_duration)
                error_retry_duration = 1

            except KeyboardInterrupt:
                exit(0)
            except Exception as e:
                log.error(" run -- seems there is an issue executing check ", exc_info=True)

                # when there are errors in the network we wait for a shorter period before retrying
                # Using an exponential retry mechanism until we are waiting for 10 minutes

                if error_retry_duration < 600:
                    error_retry_duration *= 2

                time.sleep(error_retry_duration)

    @classmethod
    def clean_up(cls):
        pass

    @classmethod
    def reload_configs(cls):
        pass


daemon_app = DaemonApp()
daemon_app.setup(application_name=service_name)
daemon_app.run(application_name=service_name)
