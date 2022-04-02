import abc

from eth_account import Account
from eth_account.signers.local import LocalAccount

from dex import DexInterface
from notification import NotifierInterface


class NodeInterface(metaclass=abc.ABCMeta):

    def __init__(self, notifier: NotifierInterface):
        self.notifier = notifier

    @classmethod
    def __subclasshook__(cls, subclass):
        return (
                hasattr(subclass, 'setup') and
                callable(subclass.setup) and
                hasattr(subclass, 'get_dex') and
                callable(subclass.get_dex) and
                hasattr(subclass, 'get_node_count') and
                callable(subclass.get_node_count) and
                hasattr(subclass, 'get_account_rewards_balance') and
                callable(subclass.get_account_rewards_balance) and
                hasattr(subclass, 'can_compound') and
                callable(subclass.can_compound) and
                hasattr(subclass, 'compound') and
                callable(subclass.compound) and
                hasattr(subclass, 'get_compounding_name') and
                callable(subclass.get_compounding_name) and
                hasattr(subclass, 'get_reward_per_hour') and
                callable(subclass.get_reward_per_hour) and
                hasattr(subclass, 'get_reward_in_usd') and
                callable(subclass.get_reward_in_usd) and
                hasattr(subclass, 'claim_rewards') and
                callable(subclass.claim_rewards) and
                hasattr(subclass, 'get_wallet_balance') and
                callable(subclass.get_wallet_balance) or
                NotImplemented)

    @abc.abstractmethod
    def setup(self):
        """Initiates all the required components to run node functions"""
        raise NotImplementedError

    @abc.abstractmethod
    def get_dex(self) -> DexInterface:
        """Returns an instance of a dex interface"""
        raise NotImplementedError

    @abc.abstractmethod
    def get_wallet_balance(self, wallet_address: str):
        """Obtains the node reward balance in an accounts the wallet.
        :param wallet_address:
        :return:"""
        raise NotImplementedError

    @abc.abstractmethod
    def get_node_count(self, wallet_address: str):
        """Obtains the count of nodes given a wallet address

        :param wallet_address:
        :return: int """
        raise NotImplementedError

    @abc.abstractmethod
    def get_account_rewards_balance(self, wallet_address: str):
        """Extract text from the data set"""
        raise NotImplementedError

    @abc.abstractmethod
    def can_compound(self, investment: dict, compound_pct=100):
        """Checks populated investment for compounding opportunities"""
        raise NotImplementedError

    @abc.abstractmethod
    def compound(self, account: Account, compounding_name: str):
        """Internal method responsible for auto compounding our rewards whenever they are ready."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_compounding_name(self, wallet_address: str):
        """Extract text from the data set"""
        raise NotImplementedError

    @abc.abstractmethod
    def get_reward_per_hour(self, **kwargs):
        """Returns the amount of rewards a node can produce"""
        raise NotImplementedError

    @abc.abstractmethod
    def get_reward_in_usd(self):
        """ This function gets the cost of one POWER unit in USD
        :return: USD value of rewards"""
        raise NotImplementedError

    @abc.abstractmethod
    def claim_rewards(self, account: LocalAccount, compound_pct=100):
        """ This function claims rewards from a compounding node farm
        utilizing the compounding factor to determine what to leave behind
        """
        raise NotImplementedError
