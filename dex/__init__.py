import abc

from eth_account.signers.local import LocalAccount

from notification import NotifierInterface


class DexInterface(metaclass=abc.ABCMeta):

    def __init__(self, notifier: NotifierInterface):
        self.notifier = notifier

    @classmethod
    def __subclasshook__(cls, subclass):
        return (
                hasattr(subclass, 'setup') and
                callable(subclass.setup) and
                hasattr(subclass, 'can_swap_to_native') and
                callable(subclass.can_swap_to_native) and
                hasattr(subclass, 'swap') and
                callable(subclass.swap) or
                NotImplemented)

    @abc.abstractmethod
    def setup(self):
        """Initiates all the required components to run node functions"""
        raise NotImplementedError

    @abc.abstractmethod
    def can_swap_to_native(self, wallet_address: str):
        """Obtains the node reward balance in an accounts the wallet.
        :param wallet_address:
        :return:"""
        raise NotImplementedError

    @abc.abstractmethod
    def swap(self, account: LocalAccount, amount_to_swap: float):
        """Swaps the amount of native token generated to the network native token

        :param account:
        :param amount_to_swap:
        """
        raise NotImplementedError
