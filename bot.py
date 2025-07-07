from web3 import Web3
from web3.exceptions import TransactionNotFound
from eth_account import Account
from aiohttp import ClientSession, ClientTimeout
from datetime import datetime
from colorama import *
import asyncio, json, time, os, pytz, random

wib = pytz.timezone('Asia/Jakarta')

class Faroswap:
    def __init__(self) -> None:
        self.HEADERS = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
            "Origin": "https://faroswap.xyz",
            "Referer": "https://faroswap.xyz/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        }
        # Your provided ZAN RPC URL
        self.RPC_URL = "https://api.zan.top/node/v1/pharos/testnet/54b49326c9f44b6e8730dc5dd4348421"
        self.PHRS_CONTRACT_ADDRESS = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"
        self.USDT_CONTRACT_ADDRESS = "0xD4071393f8716661958F766DF660033b3d35fD29"
        self.MIXSWAP_ROUTER_ADDRESS = "0x3541423f25A1Ca5C98fdBCf478405d3f0aaD1164"
        self.ERC20_CONTRACT_ABI = json.loads('''[
            {"type":"function","name":"balanceOf","stateMutability":"view","inputs":[{"name":"address","type":"address"}],"outputs":[{"name":"","type":"uint256"}]},
            {"type":"function","name":"allowance","stateMutability":"view","inputs":[{"name":"owner","type":"address"},{"name":"spender","type":"address"}],"outputs":[{"name":"","type":"uint256"}]},
            {"type":"function","name":"approve","stateMutability":"nonpayable","inputs":[{"name":"spender","type":"address"},{"name":"amount","type":"uint256"}],"outputs":[{"name":"","type":"bool"}]},
            {"type":"function","name":"decimals","stateMutability":"view","inputs":[],"outputs":[{"name":"uint8"}]}
        ]''')
        self.swap_count = 5  # Perform 5 swaps
        self.phrs_swap_amount = 0.01  # Swap 0.01 PHRS per transaction
        self.min_delay = 10  # Minimum delay of 10 seconds
        self.max_delay = 30  # Maximum delay of 30 seconds
        self.slippage = 6.0  # Slippage tolerance set to 6%

    def log(self, message):
        print(
            f"{Fore.CYAN + Style.BRIGHT}[ {datetime.now().astimezone(wib).strftime('%x %X %Z')} ]{Style.RESET_ALL}"
            f"{Fore.WHITE + Style.BRIGHT} | {Style.RESET_ALL}{message}",
            flush=True
        )

    def welcome(self):
        print(
            f"{Fore.GREEN + Style.BRIGHT}Faroswap Auto BOT - PHRS to USDT"
            f"{Fore.YELLOW + Style.BRIGHT} | Written in English"
        )

    def generate_address(self, account: str):
        try:
            account = Account.from_key(account)
            return account.address
        except Exception as e:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}Status :{Style.RESET_ALL}"
                f"{Fore.RED+Style.BRIGHT} Failed to generate address {Style.RESET_ALL}"
                f"{Fore.YELLOW+Style.BRIGHT} {str(e)} {Style.RESET_ALL}"
            )
            return None

    def mask_account(self, account):
        try:
            return account[:6] + '*' * 6 + account[-6:]
        except Exception:
            return None

    async def get_web3(self, address: str):
        try:
            web3 = Web3(Web3.HTTPProvider(self.RPC_URL, request_kwargs={"timeout": 60}))
            if not web3.is_connected():
                raise Exception("Web3 connection failed")
            self.log(f"{Fore.GREEN+Style.BRIGHT}RPC connection successful: Chain ID {web3.eth.chain_id}{Style.RESET_ALL}")
            return web3
        except Exception as e:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}Status :{Style.RESET_ALL}"
                f"{Fore.RED+Style.BRIGHT} RPC connection failed: {str(e)} {Style.RESET_ALL}"
            )
            return None

    async def get_token_balance(self, address: str, contract_address: str):
        try:
            web3 = await self.get_web3(address)
            if not web3:
                return None
            if contract_address == self.PHRS_CONTRACT_ADDRESS:
                balance = web3.eth.get_balance(address)
                decimals = 18
            else:
                token_contract = web3.eth.contract(address=web3.to_checksum_address(contract_address), abi=self.ERC20_CONTRACT_ABI)
                balance = token_contract.functions.balanceOf(address).call()
                decimals = token_contract.functions.decimals().call()
            return balance / (10 ** decimals)
        except Exception as e:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}Message :{Style.RESET_ALL}"
                f"{Fore.RED+Style.BRIGHT} Failed to get balance: {str(e)} {Style.RESET_ALL}"
            )
            return None

    async def wait_for_receipt(self, web3, tx_hash):
        try:
            receipt = await asyncio.to_thread(web3.eth.wait_for_transaction_receipt, tx_hash, timeout=300)
            if receipt["status"] == 0:
                raise Exception("Transaction failed")
            return receipt
        except (Exception, TransactionNotFound) as e:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}Message :{Style.RESET_ALL}"
                f"{Fore.RED+Style.BRIGHT} Transaction receipt not found: {str(e)} {Style.RESET_ALL}"
            )
            return None

    async def approving_token(self, account: str, address: str, router_address: str, asset_address: str, amount_to_wei: int):
        try:
            web3 = await self.get_web3(address)
            if not web3:
                return False
            spender = web3.to_checksum_address(router_address)
            token_contract = web3.eth.contract(address=web3.to_checksum_address(asset_address), abi=self.ERC20_CONTRACT_ABI)
            allowance = token_contract.functions.allowance(address, spender).call()
            if allowance < amount_to_wei:
                approve_data = token_contract.functions.approve(spender, 2**256 - 1)
                estimated_gas = approve_data.estimate_gas({"from": address})
                approve_tx = approve_data.build_transaction({
                    "from": address,
                    "gas": int(estimated_gas * 1.5),  # Gas limit increased by 1.5x
                    "maxFeePerGas": web3.to_wei(3, "gwei"),  # Gas price set to 3 gwei
                    "maxPriorityFeePerGas": web3.to_wei(2, "gwei"),
                    "nonce": web3.eth.get_transaction_count(address, "pending"),
                    "chainId": web3.eth.chain_id,
                })
                signed_tx = web3.eth.account.sign_transaction(approve_tx, account)
                raw_tx = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
                tx_hash = web3.to_hex(raw_tx)
                receipt = await self.wait_for_receipt(web3, tx_hash)
                if receipt:
                    self.log(
                        f"{Fore.CYAN+Style.BRIGHT}Approval :{Style.RESET_ALL}"
                        f"{Fore.GREEN+Style.BRIGHT} Successful {Style.RESET_ALL}"
                        f"{Fore.CYAN+Style.BRIGHT} Tx Hash :{Fore.WHITE+Style.BRIGHT} {tx_hash}"
                    )
                    return True
                else:
                    return False
        except Exception as e:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}Message :{Style.RESET_ALL}"
                f"{Fore.RED+Style.BRIGHT} Token approval failed: {str(e)} {Style.RESET_ALL}"
            )
            return False

    async def perform_swap(self, account: str, address: str):
        try:
            web3 = await self.get_web3(address)
            if not web3:
                return None, None
            decimals = 18  # For PHRS
            await self.approving_token(account, address, self.MIXSWAP_ROUTER_ADDRESS, self.PHRS_CONTRACT_ADDRESS, int(self.phrs_swap_amount * (10 ** decimals)))
            amount_to_wei = int(self.phrs_swap_amount * (10 ** decimals))
            dodo_route = await self.get_dodo_route(address, self.PHRS_CONTRACT_ADDRESS, self.USDT_CONTRACT_ADDRESS, amount_to_wei)
            if not dodo_route:
                return None, None
            value = dodo_route.get("data", {}).get("value")
            calldata = dodo_route.get("data", {}).get("data")
            try:
                estimated_gas = await asyncio.to_thread(web3.eth.estimate_gas, {
                    "to": self.MIXSWAP_ROUTER_ADDRESS,
                    "from": address,
                    "data": calldata,
                    "value": int(value)
                })
                gas_limit = int(estimated_gas * 1.5)  # Gas limit increased by 1.5x
            except Exception as e:
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}Message :{Style.RESET_ALL}"
                    f"{Fore.RED+Style.BRIGHT} Gas estimation failed: {str(e)} {Style.RESET_ALL}"
                )
                return None, None
            swap_tx = {
                "to": self.MIXSWAP_ROUTER_ADDRESS,
                "from": address,
                "data": calldata,
                "value": int(value),
                "gas": gas_limit,
                "maxFeePerGas": web3.to_wei(3, "gwei"),  # Gas price set to 3 gwei
                "maxPriorityFeePerGas": web3.to_wei(2, "gwei"),
                "nonce": web3.eth.get_transaction_count(address, "pending"),
                "chainId": web3.eth.chain_id,
            }
            signed_tx = web3.eth.account.sign_transaction(swap_tx, account)
            raw_tx = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
            tx_hash = web3.to_hex(raw_tx)
            receipt = await self.wait_for_receipt(web3, tx_hash)
            if receipt:
                return tx_hash, receipt.blockNumber
            else:
                return None, None
        except Exception as e:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}Message :{Style.RESET_ALL}"
                f"{Fore.RED+Style.BRIGHT} Swap failed: {str(e)} {Style.RESET_ALL}"
            )
            return None, None

    async def get_dodo_route(self, address: str, from_token: str, to_token: str, amount: int):
        deadline = int(time.time()) + 600
        url = (
            f"https://api.dodoex.io/route-service/v2/widget/getdodoroute?chainId=688688&deadLine={deadline}"
            f"&apikey=a37546505892e1a952&slippage={self.slippage}&source=dodoV2AndMixWasm&toTokenAddress={to_token}"
            f"&fromTokenAddress={from_token}&userAddr={address}&estimateGas=false&fromAmount={amount}"
        )
        # Use a new HTTP session to avoid cache issues
        async with ClientSession(timeout=ClientTimeout(total=30)) as session:
            try:
                async with session.get(url=url, headers=self.HEADERS) as response:
                    response.raise_for_status()
                    result = await response.json()
                    if result.get("status") != 200:
                        self.log(
                            f"{Fore.CYAN+Style.BRIGHT}Message :{Style.RESET_ALL}"
                            f"{Fore.RED+Style.BRIGHT} Failed to get price: {result.get('message', 'Unknown error')} {Style.RESET_ALL}"
                        )
                        return None
                    return result
            except Exception as e:
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}Message :{Style.RESET_ALL}"
                    f"{Fore.RED+Style.BRIGHT} Failed to get Dodo route: {str(e)} {Style.RESET_ALL}"
                )
                return None

    async def print_timer(self):
        for remaining in range(random.randint(self.min_delay, self.max_delay), 0, -1):
            print(
                f"{Fore.CYAN + Style.BRIGHT}[ {datetime.now().astimezone(wib).strftime('%x %X %Z')} ]{Style.RESET_ALL}"
                f"{Fore.BLUE + Style.BRIGHT}Waiting for {remaining} seconds...{Style.RESET_ALL}",
                end="\r",
                flush=True
            )
            await asyncio.sleep(1)

    async def process_swap(self, account: str, address: str):
        self.log(f"{Fore.CYAN+Style.BRIGHT}Swapping PHRS to USDT:{Style.RESET_ALL}")
        for i in range(self.swap_count):
            self.log(
                f"{Fore.MAGENTA+Style.BRIGHT}Swap {i+1}/{self.swap_count}{Style.RESET_ALL}"
            )
            balance = await self.get_token_balance(address, self.PHRS_CONTRACT_ADDRESS)
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}Balance :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {balance} PHRS {Style.RESET_ALL}"
            )
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}Amount :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {self.phrs_swap_amount} PHRS {Style.RESET_ALL}"
            )
            if not balance or balance < self.phrs_swap_amount:
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}Status :{Style.RESET_ALL}"
                    f"{Fore.YELLOW+Style.BRIGHT} Insufficient PHRS balance {Style.RESET_ALL}"
                )
                continue
            tx_hash, block_number = await self.perform_swap(account, address)
            if tx_hash and block_number:
                explorer = f"https://testnet.pharosscan.xyz/tx/{tx_hash}"
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}Status :{Style.RESET_ALL}"
                    f"{Fore.GREEN+Style.BRIGHT} Swap successful {Style.RESET_ALL}"
                    f"{Fore.CYAN+Style.BRIGHT} Tx Hash :{Fore.WHITE+Style.BRIGHT} {tx_hash}"
                    f"{Fore.CYAN+Style.BRIGHT} Explorer :{Fore.WHITE+Style.BRIGHT} {explorer}"
                )
            else:
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}Status :{Style.RESET_ALL}"
                    f"{Fore.RED+Style.BRIGHT} Swap failed {Style.RESET_ALL}"
                )
            await self.print_timer()

    async def main(self):
        try:
            with open('accounts.txt', 'r') as file:
                accounts = [line.strip() for line in file if line.strip()]
            self.welcome()
            self.log(
                f"{Fore.GREEN + Style.BRIGHT}Total accounts: {Style.RESET_ALL}"
                f"{Fore.WHITE + Style.BRIGHT}{len(accounts)}{Style.RESET_ALL}"
            )
            for account in accounts:
                address = self.generate_address(account)
                self.log(
                    f"{Fore.CYAN + Style.BRIGHT}===[{Style.RESET_ALL}"
                    f"{Fore.WHITE + Style.BRIGHT} {self.mask_account(address)} {Style.RESET_ALL}"
                    f"{Fore.CYAN + Style.BRIGHT}]==={Style.RESET_ALL}"
                )
                if not address:
                    self.log(
                        f"{Fore.CYAN + Style.BRIGHT}Status :{Style.RESET_ALL}"
                        f"{Fore.RED + Style.BRIGHT} Invalid private key {Style.RESET_ALL}"
                    )
                    continue
                await self.process_swap(account, address)
                await asyncio.sleep(3)
            self.log(f"{Fore.CYAN + Style.BRIGHT}={Style.RESET_ALL}"*72)
            seconds = 24 * 60 * 60
            while seconds > 0:
                formatted_time = f"{seconds // 3600:02}:{(seconds % 3600) // 60:02}:{seconds % 60:02}"
                print(
                    f"{Fore.CYAN+Style.BRIGHT}[ Waiting {formatted_time} ... ]{Style.RESET_ALL}"
                    f"{Fore.BLUE+Style.BRIGHT} All accounts processed.{Style.RESET_ALL}",
                    end="\r"
                )
                await asyncio.sleep(1)
                seconds -= 1
        except FileNotFoundError:
            self.log(f"{Fore.RED}'accounts.txt' file not found.{Style.RESET_ALL}")
        except Exception as e:
            self.log(f"{Fore.RED+Style.BRIGHT}Error: {e}{Style.RESET_ALL}")

if __name__ == "__main__":
    try:
        bot = Faroswap()
        asyncio.run(bot.main())
    except KeyboardInterrupt:
        print(
            f"{Fore.CYAN + Style.BRIGHT}[ {datetime.now().astimezone(wib).strftime('%x %X %Z')} ]{Style.RESET_ALL}"
            f"{Fore.RED + Style.BRIGHT}[ Exiting ] Faroswap - BOT{Style.RESET_ALL}"
                                                             )
