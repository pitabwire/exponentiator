import importlib
import logging

from web3.exceptions import ContractLogicError

from node import NodeInterface
from notification import NotifierInterface
from utility import get_private_key_map

log = logging.getLogger(__name__)


class Exponentiator:

    def __init__(self, node_module_str='node.power', node_class='PowerNode', notifier_module_str='notification.smtp',
                 notifier_class='EmailHandler'):

        logging.basicConfig(level=logging.INFO)

        notifier_module = importlib.import_module(notifier_module_str)
        self.notifier: NotifierInterface = getattr(notifier_module, notifier_class)()

        node_module = importlib.import_module(node_module_str)
        self.node_manager: NodeInterface = getattr(node_module, node_class)(notifier=self.notifier)

    def notify_compounding_opportunity(self, investment):

        email_subject = " Compounding Opportunity"
        email_body = (
            f"""
                    You currently have enough rewards to create a new Nuclear Node  

                        Total Node count: {investment['node_count']}
                        Total Rewards  : {investment['rewards']}
                        Wallet Balance : {investment['balance']}

                    """)
        self.notifier.send(subject=email_subject, content=email_body)

    def notify_compounding_error(self, investment: dict, error: str):

        email_subject = " Compounding Error"
        email_body = (
            f"""
                    %s experienced an error attempting to auto compound your nodes
                    
                        Total Node count: {investment['node_count']}
                        Total Rewards  : {investment['rewards']}
                        Wallet Balance : {investment['balance']}
                        
                        Error 
                        
                            {error}

                    """)

        self.notifier.send(subject=email_subject, content=email_body)

    def execute_check(self):

        """
            Glue method to get all investments given a list of wallets and
            excecutes logic to trigger further actions.
            Set conditions.
        :return:
        """

        log.debug(" execute_check -- initiating checks for investments in ")

        self.node_manager.setup()

        accounts_map = get_private_key_map()
        power_price_usd = self.node_manager.get_reward_in_usd()
        investment_map = dict()

        for wallet_name, account in accounts_map.items():
            wallet_address = account.address
            try:
                wallet_balance = self.node_manager.get_wallet_balance(wallet_address)
                node_count = self.node_manager.get_node_count(wallet_address)
                rewards_total = self.node_manager.get_account_rewards_balance(wallet_address)
                rewards_total_in_usd = power_price_usd * rewards_total

                investment = {
                    'name': wallet_name,
                    'address': wallet_address,
                    'balance': wallet_balance,
                    'node_count': node_count,
                    'rewards': rewards_total,
                    'power_price': power_price_usd}
                investment_map[wallet_name] = investment
                log.info(" execute_check -- Account [%s] has %s nodes and %s rewards with a value of %s", wallet_name, node_count,
                         rewards_total, rewards_total_in_usd)

            except ContractLogicError as e:
                if 'NO NODE OWNER' in str(e):
                    log.info("Account [%s] had no nodes attached", wallet_name)
                else:
                    log.warning(" Account [%s] experienced a contract error ", wallet_name, exc_info=True)

        # Check the compounding opportunities have been crossed
        for wallet_name, investment in investment_map.items():

            if self.node_manager.can_compound(investment):
                compounding_name = self.node_manager.get_compounding_name(
                    wallet_address=investment['address'])

                log.info(
                    "Sufficient rewards to compound for [%s] at bal: %s and rewards: %s ",
                    investment['name'], investment['balance'], investment['rewards'])

                try:
                    if not self.node_manager.compound(account=accounts_map[investment['name']],
                                                      compounding_name=compounding_name):
                        self.notify_compounding_opportunity(investment=investment)
                except Exception as e:
                    self.notify_compounding_error(investment=investment, error=str(e))

            else:

                log.info(
                    "Can not yet compound for [%s] at bal: %s and rewards: %s ",
                    investment['name'], investment['balance'], investment['rewards'])

        return "Succeeded in executing check"
