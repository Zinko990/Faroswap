from web3 import Web3
from web3.exceptions import TransactionNotFound
from eth_account import Account
from aiohttp import ClientSession, ClientTimeout
from datetime import datetime
from colorama import *
import asyncio, random, json, time, os, pytz

wib = pytz.timezone('Asia/Jakarta')

class Faroswap:
    def __init__(self) -> None:
        self.HEADERS = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
            "Origin": "https://faroswap.xyz",
            "Referer": "https://faroswap.xyz/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        }
        self.RPC_URL = "https://api.zan.top/node/v1/pharos/testnet/54b49326c9f44b6e8730dc5dd4348421"
        self.PHRS_CONTRACT_ADDRESS = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"
        self.USDC_CONTRACT_ADDRESS = "0x72df0bcd7276f2dFbAc900D1CE63c272C4BCcCED"
        self.USDT_CONTRACT_ADDRESS = "0xD4071393f8716661958F766DF660033b3d35fD29"
        self.MIXSWAP_ROUTER_ADDRESS = "0x3541423f25A1Ca5C98fdBCf478405d3f0aaD1164"
        self.TICKERS = ["PHRS", "USDC", "USDT"]
        self.ERC20_CONTRACT_ABI = json.loads('''[
            {"type":"function","name":"balanceOf","stateMutability":"view","inputs":[{"name":"address","type":"address"}],"outputs":[{"name":"","type":"uint256"}]},
            {"type":"function","name":"allowance","stateMutability":"view","inputs":[{"name":"owner","type":"address"},{"name":"spender","type":"address"}],"outputs":[{"name":"","type":"uint256"}]},
            {"type":"function","name":"approve","stateMutability":"nonpayable","inputs":[{"name":"spender","type":"address"},{"name":"amount","type":"uint256"}],"outputs":[{"name":"","type":"bool"}]},
            {"type":"function","name":"decimals","stateMutability":"view","inputs":[],"outputs":[{"name":"","type":"uint8"}]}
        ]''')
        self.swap_count = 0
        self.phrs_swap_amount = 0
        self.min_delay = 0
        self.max_delay = 0

    def clear_terminal(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    def log(self, message):
        print(
            f"{Fore.CYAN + Style.BRIGHT}[ {datetime.now().astimezone(wib).strftime('%x %X %Z')} ]{Style.RESET_ALL}"
            f"{Fore.WHITE + Style.BRIGHT} | {Style.RESET_ALL}{message}",
            flush=True
        )

    def welcome(self):
        print(
            f"{Fore.GREEN + Style.BRIGHT}Faroswap Auto BOT - Simplified Swap"
            f"{Fore.YELLOW + Style.BRIGHT} | Rey? <INI WATERMARK>"
        )

    def format_seconds(self, seconds):
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"

    def generate_address(self, account: str):
        try:
            account = Account.from_key(account)
            return account.address
        except Exception as e:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}Status    :{Style.RESET_ALL}"
                f"{Fore.RED+Style.BRIGHT} Generate Address Failed {Style.RESET_ALL}"
                f"{Fore.YELLOW+Style.BRIGHT} {str(e)} {Style.RESET_ALL}"
            )
            return None

    def mask_account(self, account):
        try:
            return account[:6] + '*' * 6 + account[-6:]
        except Exception:
            return None

    def generate_swap_option(self):
        valid_pairs = [
            (from_t, to_t) for from_t in self.TICKERS for to_t in self.TICKERS
            if from_t != to_t
        ]
        from_ticker, to_ticker = random.choice(valid_pairs)
        from_token = getattr(self, f"{from_ticker}_CONTRACT_ADDRESS")
        to_token = getattr(self, f"{to_ticker}_CONTRACT_ADDRESS")
        amount = self.phrs_swap_amount if from_ticker == "PHRS" else 0.01  # Default small amount for non-PHRS
        swap_option = f"{from_ticker} to {to_ticker}"
        return {
            "swap_option": swap_option,
            "from_token": from_token,
            "to_token": to_token,
            "ticker": from_ticker,
            "amount": amount
        }

    async def get_web3(self, address: str):
        try:
            web3 = Web3(Web3.HTTPProvider(self.RPC_URL, request_kwargs={"timeout": 60}))
            web3.eth.get_block_number()
            return web3
        except Exception as e:
            raise Exception(f"Failed to Connect to RPC: {str(e)}")

    async def get_token_balance(self, address: str, contract_address: str):
        try:
            web3 = await self.get_web3(address)
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
                f"{Fore.RED+Style.BRIGHT} {str(e)} {Style.RESET_ALL}"
            )
            return None

    async def wait_for_receipt(self, web3, tx_hash):
        try:
            receipt = await asyncio.to_thread(web3.eth.wait_for_transaction_receipt, tx_hash, timeout=300)
            return receipt
        except (Exception, TransactionNotFound) as e:
            raise Exception(f"Transaction receipt not found: {str(e)}")

    async def approving_token(self, account: str, address: str, router_address: str, asset_address: str, amount_to_wei: int):
        try:
            web3 = await self.get_web3(address)
            spender = web3.to_checksum_address(router_address)
            token_contract = web3.eth.contract(address=web3.to_checksum_address(asset_address), abi=self.ERC20_CONTRACT_ABI)
            allowance = token_contract.functions.allowance(address, spender).call()
            if allowance < amount_to_wei:
                approve_data = token_contract.functions.approve(spender, 2**256 - 1)
                estimated_gas = approve_data.estimate_gas({"from": address})
                approve_tx = approve_data.build_transaction({
                    "from": address,
                    "gas": int(estimated_gas * 1.2),
                    "maxFeePerGas": web3.to_wei(1, "gwei"),
                    "maxPriorityFeePerGas": web3.to_wei(1, "gwei"),
                    "nonce": web3.eth.get_transaction_count(address, "pending"),
                    "chainId": web3.eth.chain_id,
                })
                signed_tx = web3.eth.account.sign_transaction(approve_tx, account)
                raw_tx = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
                tx_hash = web3.to_hex(raw_tx)
                receipt = await self.wait_for_receipt(web3, tx_hash)
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}Approve :{Style.RESET_ALL}"
                    f"{Fore.GREEN+Style.BRIGHT} Success {Style.RESET_ALL}"
                    f"{Fore.CYAN+Style.BRIGHT} Tx Hash :{Fore.WHITE+Style.BRIGHT} {tx_hash}"
                )
            return True
        except Exception as e:
            raise Exception(f"Approving Token Contract Failed: {str(e)}")

    async def perform_swap(self, account: str, address: str, from_token: str, to_token: str, amount: float):
        try:
            web3 = await self.get_web3(address)
            decimals = 18 if from_token == self.PHRS_CONTRACT_ADDRESS else web3.eth.contract(
                address=web3.to_checksum_address(from_token), abi=self.ERC20_CONTRACT_ABI
            ).functions.decimals().call()
            await self.approving_token(account, address, self.MIXSWAP_ROUTER_ADDRESS, from_token, int(amount * (10 ** decimals)))
            amount_to_wei = int(amount * (10 ** decimals))
            dodo_route = await self.get_dodo_route(address, from_token, to_token, amount_to_wei)
            if not dodo_route:
                return None, None
            value = dodo_route.get("data", {}).get("value")
            calldata = dodo_route.get("data", {}).get("data")
            estimated_gas = await asyncio.to_thread(web3.eth.estimate_gas, {
                "to": self.MIXSWAP_ROUTER_ADDRESS,
                "from": address,
                "data": calldata,
                "value": int(value)
            })
            swap_tx = {
                "to": self.MIXSWAP_ROUTER_ADDRESS,
                "from": address,
                "data": calldata,
                "value": int(value),
                "gas": int(estimated_gas * 1.2),
                "maxFeePerGas": web3.to_wei(1, "gwei"),
                "maxPriorityFeePerGas": web3.to_wei(1, "gwei"),
                "nonce": web3.eth.get_transaction_count(address, "pending"),
                "chainId": web3.eth.chain_id,
            }
            signed_tx = web3.eth.account.sign_transaction(swap_tx, account)
            raw_tx = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
            tx_hash = web3.to_hex(raw_tx)
            receipt = await self.wait_for_receipt(web3, tx_hash)
            return tx_hash, receipt.blockNumber
        except Exception as e:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}Message :{Style.RESET_ALL}"
                f"{Fore.RED+Style.BRIGHT} {str(e)} {Style.RESET_ALL}"
            )
            return None, None

    async def get_dodo_route(self, address: str, from_token: str, to_token: str, amount: int):
        deadline = int(time.time()) + 600
        url = (
            f"https://api.dodoex.io/route-service/v2/widget/getdodoroute?chainId=688688&deadLine={deadline}"
            f"&apikey=a37546505892e1a952&slippage=3.225&source=dodoV2AndMixWasm&toTokenAddress={to_token}"
            f"&fromTokenAddress={from_token}&userAddr={address}&estimateGas=false&fromAmount={amount}"
        )
        async with ClientSession(timeout=ClientTimeout(total=30)) as session:
            async with session.get(url=url, headers=self.HEADERS) as response:
                response.raise_for_status()
                result = await response.json()
                if result.get("status") != 200:
                    self.log(
                        f"{Fore.CYAN+Style.BRIGHT}Message :{Style.RESET_ALL}"
                        f"{Fore.RED+Style.BRIGHT} Quote Not Available {Style.RESET_ALL}"
                    )
                    return None
                return result

    async def print_timer(self):
        for remaining in range(random.randint(self.min_delay, self.max_delay), 0, -1):
            print(
                f"{Fore.CYAN + Style.BRIGHT}[ {datetime.now().astimezone(wib).strftime('%x %X %Z')} ]{Style.RESET_ALL}"
                f"{Fore.BLUE + Style.BRIGHT}Wait For {remaining} Seconds...{Style.RESET_ALL}",
                end="\r",
                flush=True
            )
            await asyncio.sleep(1)

    def print_swap_question(self):
        while True:
            try:
                self.swap_count = int(input(f"{Fore.YELLOW + Style.BRIGHT}How Many Swaps? -> {Style.RESET_ALL}").strip())
                if self.swap_count > 0:
                    break
                print(f"{Fore.RED + Style.BRIGHT}Please enter a positive number.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED + Style.BRIGHT}Invalid input. Enter a number.{Style.RESET_ALL}")
        while True:
            try:
                self.phrs_swap_amount = float(input(f"{Fore.YELLOW + Style.BRIGHT}Enter PHRS Amount per Swap (e.g., 0.01) -> {Style.RESET_ALL}").strip())
                if self.phrs_swap_amount > 0:
                    break
                print(f"{Fore.RED + Style.BRIGHT}PHRS Amount must be greater than 0.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED + Style.BRIGHT}Invalid input. Enter a decimal number.{Style.RESET_ALL}")
        while True:
            try:
                self.min_delay = int(input(f"{Fore.YELLOW + Style.BRIGHT}Min Delay Each Tx (seconds) -> {Style.RESET_ALL}").strip())
                if self.min_delay >= 0:
                    break
                print(f"{Fore.RED + Style.BRIGHT}Min Delay must be >= 0.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED + Style.BRIGHT}Invalid input. Enter a number.{Style.RESET_ALL}")
        while True:
            try:
                self.max_delay = int(input(f"{Fore.YELLOW + Style.BRIGHT}Max Delay Each Tx (seconds) -> {Style.RESET_ALL}").strip())
                if self.max_delay >= self.min_delay:
                    break
                print(f"{Fore.RED + Style.BRIGHT}Max Delay must be >= Min Delay.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED + Style.BRIGHT}Invalid input. Enter a number.{Style.RESET_ALL}")

    async def process_swap(self, account: str, address: str):
        self.log(f"{Fore.CYAN+Style.BRIGHT}Random Swap:{Style.RESET_ALL}")
        for i in range(self.swap_count):
            self.log(
                f"{Fore.MAGENTA+Style.BRIGHT}Swap {i+1}/{self.swap_count}{Style.RESET_ALL}"
            )
            option = self.generate_swap_option()
            swap_option = option["swap_option"]
            from_token = option["from_token"]
            to_token = option["to_token"]
            ticker = option["ticker"]
            amount = option["amount"]
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}Option :{Style.RESET_ALL}"
                f"{Fore.BLUE+Style.BRIGHT} {swap_option} {Style.RESET_ALL}"
            )
            balance = await self.get_token_balance(address, from_token)
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}Balance :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {balance} {ticker} {Style.RESET_ALL}"
            )
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}Amount :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {amount} {ticker} {Style.RESET_ALL}"
            )
            if not balance or balance < amount:
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}Status :{Style.RESET_ALL}"
                    f"{Fore.YELLOW+Style.BRIGHT} Insufficient {ticker} Balance {Style.RESET_ALL}"
                )
                continue
            tx_hash, block_number = await self.perform_swap(account, address, from_token, to_token, amount)
            if tx_hash and block_number:
                explorer = f"https://testnet.pharosscan.xyz/tx/{tx_hash}"
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}Status :{Style.RESET_ALL}"
                    f"{Fore.GREEN+Style.BRIGHT} Swap Success {Style.RESET_ALL}"
                    f"{Fore.CYAN+Style.BRIGHT} Tx Hash :{Fore.WHITE+Style.BRIGHT} {tx_hash}"
                    f"{Fore.CYAN+Style.BRIGHT} Explorer :{Fore.WHITE+Style.BRIGHT} {explorer}"
                )
            else:
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}Status :{Style.RESET_ALL}"
                    f"{Fore.RED+Style.BRIGHT} Swap Failed {Style.RESET_ALL}"
                )
            await self.print_timer()

    async def main(self):
        try:
            with open('accounts.txt', 'r') as file:
                accounts = [line.strip() for line in file if line.strip()]
            self.clear_terminal()
            self.welcome()
            self.log(
                f"{Fore.GREEN + Style.BRIGHT}Account's Total: {Style.RESET_ALL}"
                f"{Fore.WHITE + Style.BRIGHT}{len(accounts)}{Style.RESET_ALL}"
            )
            self.print_swap_question()
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
                        f"{Fore.RED + Style.BRIGHT} Invalid Private Key {Style.RESET_ALL}"
                    )
                    continue
                await self.process_swap(account, address)
                await asyncio.sleep(3)
            self.log(f"{Fore.CYAN + Style.BRIGHT}={Style.RESET_ALL}"*72)
            seconds = 24 * 60 * 60
            while seconds > 0:
                formatted_time = self.format_seconds(seconds)
                print(
                    f"{Fore.CYAN+Style.BRIGHT}[ Wait for {formatted_time} ... ]{Style.RESET_ALL}"
                    f"{Fore.BLUE+Style.BRIGHT} All Accounts Processed.{Style.RESET_ALL}",
                    end="\r"
                )
                await asyncio.sleep(1)
                seconds -= 1
        except FileNotFoundError:
            self.log(f"{Fore.RED}File 'accounts.txt' Not Found.{Style.RESET_ALL}")
        except Exception as e:
            self.log(f"{Fore.RED+Style.BRIGHT}Error: {e}{Style.RESET_ALL}")

if __name__ == "__main__":
    try:
        bot = Faroswap()
        asyncio.run(bot.main())
    except KeyboardInterrupt:
        print(
            f"{Fore.CYAN + Style.BRIGHT}[ {datetime.now().astimezone(wib).strftime('%x %X %Z')} ]{Style.RESET_ALL}"
            f"{Fore.RED + Style.BRIGHT}[ EXIT ] Faroswap - BOT{Style.RESET_ALL}"
          )
