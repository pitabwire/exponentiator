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

    def notify_withdrawal_error(self, investment: dict, withdrawal_amount: float, error: str):

        email_subject = " Withdrawal Error"
        email_body = (
            f"""
                        %s experienced an error attempting to withdraw to native tokens
                        
                            Total Node count: {investment['node_count']}
                            Total Rewards  : {investment['rewards']}
                            Wallet Balance : {investment['balance']}
                            Withdrawal Balance : {withdrawal_amount}
                            
                            Error 
                            
                                {error}
    
                        """)

        self.notifier.send(subject=email_subject, content=email_body)

    def __get_investment_map(self, wallet_name, wallet_address):

        wallet_balance = self.node_manager.get_wallet_balance(wallet_address)
        node_count = self.node_manager.get_node_count(wallet_address)
        rewards_total = self.node_manager.get_account_rewards_balance(wallet_address)

        investment = {
            'name': wallet_name,
            'address': wallet_address,
            'balance': wallet_balance,
            'node_count': node_count,
            'rewards': rewards_total}

        log.info(" __get_investment_map -- Account [%s] has %s nodes and %s rewards",
                 wallet_name, node_count, rewards_total)

        return investment

    def execute_check(self, compound_pct=100):

        """
            Glue method to get all investments given a list of wallets and
            excecutes logic to trigger further actions.
            Set conditions.
        :return:
        """

        log.debug(" execute_check -- initiating checks for investments in ")

        self.node_manager.setup()

        accounts_map = get_private_key_map()

        for wallet_name, account in accounts_map.items():
            wallet_address = account.address
            try:

                investment = self.__get_investment_map(
                    wallet_name=wallet_name,
                    wallet_address=wallet_address
                )

                if self.node_manager.can_compound(investment, compound_pct=compound_pct):
                    compounding_name = self.node_manager.get_compounding_name(
                        wallet_address=investment['address'])

                    log.info(
                        "Sufficient rewards to compound for [%s] at bal: %s and rewards: %s ",
                        investment['name'], investment['balance'], investment['rewards'])

                    try:
                        if not self.node_manager.compound(account=accounts_map[investment['name']],
                                                          compounding_name=compounding_name):
                            self.notify_compounding_opportunity(investment=investment)
                        else:
                            self.node_manager.claim_rewards(account=accounts_map[investment['name']],
                                                            compound_pct=compound_pct)
                    except Exception as e:
                        self.notify_compounding_error(investment=investment, error=str(e))

                else:

                    log.info(
                        "Can not yet compound for [%s] at bal: %s and rewards: %s ",
                        investment['name'], investment['balance'], investment['rewards'])

            except ContractLogicError as e:
                if 'NO NODE OWNER' in str(e):
                    log.info("Account [%s] had no nodes attached", wallet_name)
                else:
                    log.warning(" Account [%s] experienced a contract error ", wallet_name, exc_info=True)

        return "Succeeded in executing check"

    def execute_withdraw(self, compound_pct=100, interval_in_hours=24):

        accounts_map = get_private_key_map()

        for wallet_name, account in accounts_map.items():
            wallet_address = account.address
            investment = self.__get_investment_map(
                wallet_name=wallet_name,
                wallet_address=wallet_address
            )

            generation_capacity = investment['node_count'] * self.node_manager.get_reward_per_hour() * interval_in_hours
            withdrawal_threshold = generation_capacity * (100 - compound_pct) / 100
            if 0 < withdrawal_threshold < investment['balance']:
                log.info(
                    " execute_withdraw -- there is enough balance [%s] to swap over threshold : %s",
                    investment['balance'], withdrawal_threshold)

                try:
                    self.node_manager.get_dex().swap(account=account, amount_to_swap=1)
                except Exception as e:
                    self.notify_withdrawal_error(
                        investment=investment,
                        withdrawal_amount=withdrawal_threshold,
                        error=str(e))
                    return "Error withdrawing to native token"
            else:
                log.info(
                    " execute_withdraw -- insufficient balance [%s] to swap over threshold : %s",
                    investment['balance'], withdrawal_threshold)

        return "Succeeded in withdrawing"
