import logging
from datetime import datetime, timedelta

import web3
from eth_account.signers.local import LocalAccount

from dex import DexInterface
from notification import NotifierInterface
from utility import get_network_connection, get_contract

log = logging.getLogger(__name__)

dex_contract_abi = '[{"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint256","name":"amountOutMin","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"name":"swapExactTokensForETH","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"nonpayable","type":"function"}]'


class SpookySwap(DexInterface):
    POWER_TOKEN_CONTRACT = '0x131c7afb4E5f5c94A27611f7210dfEc2215E85Ae'
    WFTM_TOKEN_CONTRACT = '0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83'

    def __init__(self, notifier: NotifierInterface):
        super().__init__(notifier=notifier)
        self.ftm_connection = None
        self.dex_contract = None

    def setup(self):
        """
            Initiates all the required components to run node functions
        :return:
        """
        self.ftm_connection = get_network_connection(self.ftm_connection)

        self.dex_contract = get_contract(self.ftm_connection,
                                         **dict(address='0xf491e7b69e4244ad4002bc14e878a34207e38c29',
                                                abi=dex_contract_abi))

    def can_swap_to_native(self, min_rate_allowed: float):
        """Obtains the node reward balance in an accounts the wallet.
        :param min_rate_allowed:
        :return:"""

        return True

    def swap(self, account: LocalAccount, amount_to_swap: float):
        """Swaps the amount of native token generated to the network native token

        :param account:
        :param amount_to_swap:
        """
        nonce = self.dex_contract.web3.eth.get_transaction_count(account.address)
        gas_price = self.dex_contract.web3.eth.gas_price

        amount_in = web3.Web3.toWei(amount_to_swap, 'ether')
        amount_out_min = web3.Web3.toWei(amount_to_swap, 'ether')
        path_out = [self.POWER_TOKEN_CONTRACT, self.WFTM_TOKEN_CONTRACT]
        tx_deadline = datetime.now() + timedelta(hours=1)

        swap_tx = self.dex_contract.functions.swapExactTokensForETH(
            amount_in, amount_out_min, path_out, account.address, int(tx_deadline.timestamp())). \
            buildTransaction(
            {
                'from': account.address,
                'nonce': nonce,
                "gasPrice": gas_price,
            }
        )

        signed_swap_txn = account.sign_transaction(swap_tx)
        swap_tx_hash = self.dex_contract.web3.eth.send_raw_transaction(signed_swap_txn.rawTransaction)

        compound_tx_receipt = self.dex_contract.web3.eth.wait_for_transaction_receipt(swap_tx_hash)
        log.info(" swap -- successfully swaped [%s] rewards with receipt  %s", amount_to_swap, compound_tx_receipt)
