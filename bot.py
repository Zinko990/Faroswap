from web3 import Web3
from eth_account import Account
from aiohttp import ClientSession, ClientTimeout, ClientResponseError
from aiohttp_socks import ProxyConnector
from fake_useragent import FakeUserAgent
from datetime import datetime
from colorama import *
import asyncio, random, json, time, os, pytz

wib = pytz.timezone('Asia/Jakarta')

class LiqquidityBot:
    def __init__(self) -> None:
        self.HEADERS = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
            "Origin": "https://liqquidity.io",  # Replace with Liqquidity's actual website
            "Referer": "https://liqquidity.io/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site",
            "User-Agent": FakeUserAgent().random
        }
        self.RPC_URL = "https://api.zan.top/node/v1/pharos/testnet/54b49326c9f44b6e8730dc5dd4348421"  # Replace with Liqquidity's actual RPC URL
        self.USDC_CONTRACT_ADDRESS = "0x72df0bcd7276f2dFbAc900D1CE63c272C4BCcCED"  # Replace with Liqquidity's USDC address
        self.USDT_CONTRACT_ADDRESS = "0xD4071393f8716661958F766DF660033b3d35fD29"  # Replace with Liqquidity's USDT address
        self.DVM_ROUTER_ADDRESS = "0x4b177AdEd3b8bD1D5D747F91B9E853513838Cd49"  # Replace with Liqquidity's DVM Router address
        self.POOL_ADDRESS_USDC_USDT = "0x633d8A492cf59b47F36eb8ef0F739D4FF5cE9af9"  # Replace with Liqquidity's USDC/USDT pool address
        self.ERC20_CONTRACT_ABI = json.loads('''[
            {"type":"function","name":"balanceOf","stateMutability":"view","inputs":[{"name":"address","type":"address"}],"outputs":[{"name":"","type":"uint256"}]},
            {"type":"function","name":"allowance","stateMutability":"view","inputs":[{"name":"owner","type":"address"},{"name":"spender","type":"address"}],"outputs":[{"name":"","type":"uint256"}]},
            {"type":"function","name":"approve","stateMutability":"nonpayable","inputs":[{"name":"spender","type":"address"},{"name":"amount","type":"uint256"}],"outputs":[{"name":"","type":"bool"}]},
            {"type":"function","name":"decimals","stateMutability":"view","inputs":[],"outputs":[{"name":"","type":"uint8"}]}
        ]''')
        self.UNISWAP_V2_CONTRACT_ABI = [
            {
                "type": "function",
                "name": "addDVMLiquidity",
                "stateMutability": "payable",
                "inputs": [
                    {"internalType": "address", "name": "dvmAddress", "type": "address"},
                    {"internalType": "uint256", "name": "baseInAmount", "type": "uint256"},
                    {"internalType": "uint256", "name": "quoteInAmount", "type": "uint256"},
                    {"internalType": "uint256", "name": "baseMinAmount", "type": "uint256"},
                    {"internalType": "uint256", "name": "quoteMinAmount", "type": "uint256"},
                    {"internalType": "uint8", "name": "flag", "type": "uint8"},
                    {"internalType": "uint256", "name": "deadLine", "type": "uint256"}
                ],
                "outputs": [
                    {"internalType": "uint256", "name": "shares", "type": "uint256"},
                    {"internalType": "uint256", "name": "baseAdjustedInAmount", "type": "uint256"},
                    {"internalType": "uint256", "name": "quoteAdjustedInAmount", "type": "uint256"}
                ]
            }
        ]
        self.proxies = []
        self.proxy_index = 0
        self.account_proxies = {}
        self.lp_amount = 0  # Amount for LP addition (to be set by user input)

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
            f"""
        {Fore.GREEN + Style.BRIGHT}Liqquidity{Fore.BLUE + Style.BRIGHT} LP Addition BOT
            """
        )

    def generate_address(self, account: str):
        try:
            account = Account.from_key(account)
            address = account.address
            return address
        except Exception as e:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}Status    :{Style.RESET_ALL}"
                f"{Fore.RED+Style.BRIGHT} Generate Address Failed {Style.RESET_ALL}"
                f"{Fore.YELLOW+Style.BRIGHT} {str(e)} {Style.RESET_ALL}"
            )
            return None

    def mask_account(self, account):
        try:
            mask_account = account[:6] + '*' * 6 + account[-6:]
            return mask_account
        except Exception:
            return None

    async def get_web3_with_check(self, address: str, use_proxy: bool, retries=3, timeout=60):
        request_kwargs = {"timeout": timeout}
        proxy = self.get_next_proxy_for_account(address) if use_proxy else None
        if use_proxy and proxy:
            request_kwargs["proxies"] = {"http": proxy, "https": proxy}
        for attempt in range(retries):
            try:
                web3 = Web3(Web3.HTTPProvider(self.RPC_URL, request_kwargs=request_kwargs))
                web3.eth.get_transaction_count(address)
                return web3
            except Exception as e:
                if attempt < retries - 1:
                    await asyncio.sleep(3)
                    continue
                raise Exception(f"Failed to Connect to RPC: {str(e)}")

    async def get_token_balance(self, address: str, contract_address: str, use_proxy: bool):
        try:
            web3 = await self.get_web3_with_check(address, use_proxy)
            token_contract = web3.eth.contract(address=web3.to_checksum_address(contract_address), abi=self.ERC20_CONTRACT_ABI)
            balance = token_contract.functions.balanceOf(address).call()
            decimals = token_contract.functions.decimals().call()
            return balance / (10 ** decimals)
        except Exception as e:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}     Message :{Style.RESET_ALL}"
                f"{Fore.RED+Style.BRIGHT} Failed to get balance: {str(e)} {Style.RESET_ALL}"
            )
            return 0

    async def approving_token(self, account: str, address: str, router_address: str, asset_address: str, amount_to_wei: int, use_proxy: bool):
        try:
            web3 = await self.get_web3_with_check(address, use_proxy)
            spender = web3.to_checksum_address(router_address)
            token_contract = web3.eth.contract(address=web3.to_checksum_address(asset_address), abi=self.ERC20_CONTRACT_ABI)
            allowance = token_contract.functions.allowance(address, spender).call()
            if allowance < amount_to_wei:
                approve_data = token_contract.functions.approve(spender, 2**256 - 1)
                estimated_gas = approve_data.estimate_gas({"from": address})
                max_priority_fee = web3.to_wei(1, "gwei")
                max_fee = max_priority_fee
                approve_tx = approve_data.build_transaction({
                    "from": address,
                    "gas": int(estimated_gas * 1.2),
                    "maxFeePerGas": int(max_fee),
                    "maxPriorityFeePerGas": int(max_priority_fee),
                    "nonce": web3.eth.get_transaction_count(address, "pending"),
                    "chainId": web3.eth.chain_id,
                })
                signed_tx = web3.eth.account.sign_transaction(approve_tx, account)
                raw_tx = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
                tx_hash = web3.to_hex(raw_tx)
                await asyncio.sleep(5)  # Wait for approval to process
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}     Approve :{Style.RESET_ALL}"
                    f"{Fore.GREEN+Style.BRIGHT} Success {Style.RESET_ALL}"
                    f"{Fore.WHITE+Style.BRIGHT} Tx Hash: {tx_hash} {Style.RESET_ALL}"
                )
            return True
        except Exception as e:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}     Message :{Style.RESET_ALL}"
                f"{Fore.RED+Style.BRIGHT} Approving Token Failed: {str(e)} {Style.RESET_ALL}"
            )
            return False

    async def perform_add_dvm_liquidity(self, account: str, address: str, base_token: str, quote_token: str, amount: float, use_proxy: bool):
        try:
            web3 = await self.get_web3_with_check(address, use_proxy)
            pair_address = self.POOL_ADDRESS_USDC_USDT  # Using USDC/USDT pair as default
            dvm_address = web3.to_checksum_address(pair_address)
            decimals = 6  # Assuming 6 decimals for USDC/USDT
            in_amount = int(amount * (10 ** decimals))
            min_amount = int(in_amount * (1 - 0.1 / 100))  # 0.1% slippage tolerance
            deadline = int(time.time()) + 600

            # Check token balances
            usdc_balance = await self.get_token_balance(address, base_token, use_proxy)
            usdt_balance = await self.get_token_balance(address, quote_token, use_proxy)
            if usdc_balance < amount or usdt_balance < amount:
                raise Exception(f"Insufficient balance: USDC={usdc_balance}, USDT={usdt_balance}, Required={amount}")

            # Approve both tokens
            base_approved = await self.approving_token(account, address, self.DVM_ROUTER_ADDRESS, base_token, in_amount, use_proxy)
            quote_approved = await self.approving_token(account, address, self.DVM_ROUTER_ADDRESS, quote_token, in_amount, use_proxy)
            if not (base_approved and quote_approved):
                raise Exception("Token approval failed")

            token_contract = web3.eth.contract(address=web3.to_checksum_address(self.DVM_ROUTER_ADDRESS), abi=self.UNISWAP_V2_CONTRACT_ABI)
            add_lp_data = token_contract.functions.addDVMLiquidity(
                dvm_address, in_amount, in_amount, min_amount, min_amount, 0, deadline
            )
            estimated_gas = add_lp_data.estimate_gas({"from": address, "value": 0})
            max_priority_fee = web3.to_wei(1, "gwei")
            max_fee = max_priority_fee
            add_lp_tx = add_lp_data.build_transaction({
                "from": address,
                "value": 0,
                "gas": int(estimated_gas * 1.2),
                "maxFeePerGas": int(max_fee),
                "maxPriorityFeePerGas": int(max_priority_fee),
                "nonce": web3.eth.get_transaction_count(address, "pending"),
                "chainId": web3.eth.chain_id,
            })
            signed_tx = web3.eth.account.sign_transaction(add_lp_tx, account)
            raw_tx = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
            tx_hash = web3.to_hex(raw_tx)
            await asyncio.sleep(10)  # Wait for transaction to be mined
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}     Status  :{Style.RESET_ALL}"
                f"{Fore.GREEN+Style.BRIGHT} Add Liquidity Success {Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} Tx Hash: {tx_hash} {Style.RESET_ALL}"
            )
            explorer = f"https://testnet.pharosscan.xyz/tx/{tx_hash}"
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}     Explorer:{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {explorer} {Style.RESET_ALL}"
            )
            return tx_hash
        except Exception as e:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}     Message :{Style.RESET_ALL}"
                f"{Fore.RED+Style.BRIGHT} Add Liquidity Failed: {str(e)} {Style.RESET_ALL}"
            )
            return None

    def check_proxy_schemes(self, proxies):
        schemes = ["http://", "https://", "socks4://", "socks5://"]
        if any(proxies.startswith(scheme) for scheme in schemes):
            return proxies
        return f"http://{proxies}"

    def get_next_proxy_for_account(self, token):
        if token not in self.account_proxies:
            if not self.proxies:
                return None
            proxy = self.check_proxy_schemes(self.proxies[self.proxy_index])
            self.account_proxies[token] = proxy
            self.proxy_index = (self.proxy_index + 1) % len(self.proxies)
        return self.account_proxies[token]

    async def load_proxies(self, use_proxy_choice: int):
        filename = "proxy.txt"
        try:
            if use_proxy_choice == 1:
                async with ClientSession(timeout=ClientTimeout(total=30)) as session:
                    async with session.get("https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=protocolipport&format=text") as response:
                        response.raise_for_status()
                        content = await response.text()
                        with open(filename, 'w') as f:
                            f.write(content)
                        self.proxies = [line.strip() for line in content.splitlines() if line.strip()]
            else:
                if not os.path.exists(filename):
                    self.log(f"{Fore.RED + Style.BRIGHT}File {filename} Not Found.{Style.RESET_ALL}")
                    return
                with open(filename, 'r') as f:
                    self.proxies = [line.strip() for line in f.read().splitlines() if line.strip()]
            
            if not self.proxies:
                self.log(f"{Fore.RED + Style.BRIGHT}No Proxies Found.{Style.RESET_ALL}")
                return

            self.log(
                f"{Fore.GREEN + Style.BRIGHT}Proxies Total  : {Style.RESET_ALL}"
                f"{Fore.WHITE + Style.BRIGHT}{len(self.proxies)}{Style.RESET_ALL}"
            )
        except Exception as e:
            self.log(f"{Fore.RED + Style.BRIGHT}Failed To Load Proxies: {e}{Style.RESET_ALL}")
            self.proxies = []

    def print_lp_amount_question(self):
        while True:
            try:
                amount = float(input(f"{Fore.YELLOW + Style.BRIGHT}Enter Amount for LP Addition (min: 0.00001, max: 0.0001): {Style.RESET_ALL}").strip())
                if 0.00001 <= amount <= 0.0001:
                    self.lp_amount = amount
                    break
                else:
                    print(f"{Fore.RED + Style.BRIGHT}Amount must be between 0.00001 and 0.0001.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED + Style.BRIGHT}Invalid input. Enter a float or decimal number between 0.00001 and 0.0001.{Style.RESET_ALL}")

    async def process_accounts(self, account: str, address: str, use_proxy: bool):
        proxy = self.get_next_proxy_for_account(address) if use_proxy else None
        self.log(
            f"{Fore.CYAN + Style.BRIGHT}Proxy        :{Style.RESET_ALL}"
            f"{Fore.WHITE + Style.BRIGHT} {proxy} {Style.RESET_ALL}"
        )
        
        for i in range(100):  # Loop 100 times for LP addition
            self.log(
                f"{Fore.CYAN + Style.BRIGHT}     Action  :{Style.RESET_ALL}"
                f"{Fore.WHITE + Style.BRIGHT} Adding Liquidity {i+1}/100 with {self.lp_amount} USDC/USDT {Style.RESET_ALL}"
            )
            tx_hash = await self.perform_add_dvm_liquidity(account, address, self.USDC_CONTRACT_ADDRESS, self.USDT_CONTRACT_ADDRESS, self.lp_amount, use_proxy)
            if not tx_hash:
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}     Warning :{Style.RESET_ALL}"
                    f"{Fore.YELLOW+Style.BRIGHT} Skipping to next iteration due to failure. {Style.RESET_ALL}"
                )
            await asyncio.sleep(5)  # Delay between each LP addition

    async def main(self):
        try:
            with open('accounts.txt', 'r') as file:
                accounts = [line.strip() for line in file if line.strip()]
            
            while True:
                print(f"{Fore.GREEN + Style.BRIGHT}Select Proxy Option:{Style.RESET_ALL}")
                print(f"{Fore.WHITE + Style.BRIGHT}1. Run With Free Proxyscrape Proxy{Style.RESET_ALL}")
                print(f"{Fore.WHITE + Style.BRIGHT}2. Run With Private Proxy{Style.RESET_ALL}")
                print(f"{Fore.WHITE + Style.BRIGHT}3. Run Without Proxy{Style.RESET_ALL}")
                use_proxy_choice = int(input(f"{Fore.BLUE + Style.BRIGHT}Choose [1/2/3] -> {Style.RESET_ALL}").strip())

                if use_proxy_choice in [1, 2, 3]:
                    proxy_type = (
                        "With Free Proxyscrape" if use_proxy_choice == 1 else 
                        "With Private" if use_proxy_choice == 2 else 
                        "Without"
                    )
                    print(f"{Fore.GREEN + Style.BRIGHT}Run {proxy_type} Proxy Selected.{Style.RESET_ALL}")
                    break
                else:
                    print(f"{Fore.RED + Style.BRIGHT}Please enter either 1, 2 or 3.{Style.RESET_ALL}")

            use_proxy = True if use_proxy_choice in [1, 2] else False
            self.print_lp_amount_question()

            self.clear_terminal()
            self.welcome()
            self.log(
                f"{Fore.GREEN + Style.BRIGHT}Account's Total: {Style.RESET_ALL}"
                f"{Fore.WHITE + Style.BRIGHT}{len(accounts)}{Style.RESET_ALL}"
            )

            if use_proxy:
                await self.load_proxies(use_proxy_choice)
            
            separator = "=" * 25
            for account in accounts:
                if account:
                    address = self.generate_address(account)

                    self.log(
                        f"{Fore.CYAN + Style.BRIGHT}{separator}[{Style.RESET_ALL}"
                        f"{Fore.WHITE + Style.BRIGHT} {self.mask_account(address)} {Style.RESET_ALL}"
                        f"{Fore.CYAN + Style.BRIGHT}]{separator}{Style.RESET_ALL}"
                    )

                    if not address:
                        self.log(
                            f"{Fore.CYAN + Style.BRIGHT}Status       :{Style.RESET_ALL}"
                            f"{Fore.RED + Style.BRIGHT} Invalid Private Key or Library Version Not Supported {Style.RESET_ALL}"
                        )
                        continue

                    await self.process_accounts(account, address, use_proxy)

            self.log(f"{Fore.CYAN + Style.BRIGHT}={Style.RESET_ALL}"*72)
            print(
                f"{Fore.CYAN+Style.BRIGHT}[ Process Completed ]{Style.RESET_ALL}"
                f"{Fore.WHITE + Style.BRIGHT} | {Style.RESET_ALL}"
                f"{Fore.BLUE+Style.BRIGHT}All LP Additions (100x per account) Processed.{Style.RESET_ALL}"
            )

        except FileNotFoundError:
            self.log(f"{Fore.RED}File 'accounts.txt' Not Found.{Style.RESET_ALL}")
            return
        except Exception as e:
            self.log(f"{Fore.RED+Style.BRIGHT}Error: {e}{Style.RESET_ALL}")
            raise e

if __name__ == "__main__":
    try:
        bot = LiqquidityBot()
        asyncio.run(bot.main())
    except KeyboardInterrupt:
        print(
            f"{Fore.CYAN + Style.BRIGHT}[ {datetime.now().astimezone(wib).strftime('%x %X %Z')} ]{Style.RESET_ALL}"
            f"{Fore.WHITE + Style.BRIGHT} | {Style.RESET_ALL}"
            f"{Fore.RED + Style.BRIGHT}[ EXIT ] Liqquidity - LP BOT{Style.RESET_ALL}"
                )
