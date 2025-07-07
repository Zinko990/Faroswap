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
        self.PHRS_CONTRACT_ADDRESS = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"  # Replace with Liqquidity's PHRS token address
        self.USDT_CONTRACT_ADDRESS = "0xD4071393f8716661958F766DF660033b3d35fD29"  # Replace with Liqquidity's USDT token address
        self.TICKERS = ["PHRS", "USDT"]  # Replace with Liqquidity's supported tokens
        self.ERC20_CONTRACT_ABI = json.loads('''[
            {"type":"function","name":"balanceOf","stateMutability":"view","inputs":[{"name":"address","type":"address"}],"outputs":[{"name":"","type":"uint256"}]},
            {"type":"function","name":"decimals","stateMutability":"view","inputs":[],"outputs":[{"name":"","type":"uint8"}]}
        ]''')
        self.proxies = []
        self.proxy_index = 0
        self.account_proxies = {}

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
        {Fore.GREEN + Style.BRIGHT}Liqquidity{Fore.BLUE + Style.BRIGHT} Auto BOT
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
                web3.eth.get_block_number()
                return web3
            except Exception as e:
                if attempt < retries:
                    await asyncio.sleep(3)
                    continue
                raise Exception(f"Failed to Connect to RPC: {str(e)}")

    async def get_token_balance(self, address: str, contract_address: str, use_proxy: bool):
        try:
            web3 = await self.get_web3_with_check(address, use_proxy)
            if contract_address == self.PHRS_CONTRACT_ADDRESS:
                balance = web3.eth.get_balance(address)
                decimals = 18
            else:
                token_contract = web3.eth.contract(address=web3.to_checksum_address(contract_address), abi=self.ERC20_CONTRACT_ABI)
                balance = token_contract.functions.balanceOf(address).call()
                decimals = token_contract.functions.decimals().call()
            token_balance = balance / (10 ** decimals)
            return token_balance
        except Exception as e:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}Message :{Style.RESET_ALL}"
                f"{Fore.RED+Style.BRIGHT} {str(e)} {Style.RESET_ALL}"
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

    async def process_accounts(self, account: str, address: str, use_proxy: bool):
        proxy = self.get_next_proxy_for_account(address) if use_proxy else None
        self.log(
            f"{Fore.CYAN + Style.BRIGHT}Proxy        :{Style.RESET_ALL}"
            f"{Fore.WHITE + Style.BRIGHT} {proxy} {Style.RESET_ALL}"
        )

        for ticker in self.TICKERS:
            contract_address = getattr(self, f"{ticker}_CONTRACT_ADDRESS") if ticker != "PHRS" else self.PHRS_CONTRACT_ADDRESS
            balance = await self.get_token_balance(address, contract_address, use_proxy)
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}Balance ({ticker}):{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {balance if balance is not None else 'N/A'} {ticker} {Style.RESET_ALL}"
            )
        await asyncio.sleep(3)

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
            seconds = 24 * 60 * 60
            while seconds > 0:
                formatted_time = f"{seconds // 3600:02}:{(seconds % 3600) // 60:02}:{seconds % 60:02}"
                print(
                    f"{Fore.CYAN+Style.BRIGHT}[ Wait for {formatted_time} ... ]{Style.RESET_ALL}"
                    f"{Fore.WHITE + Style.BRIGHT} | {Style.RESET_ALL}"
                    f"{Fore.BLUE+Style.BRIGHT}All Accounts Have Been Processed.{Style.RESET_ALL}",
                    end="\r"
                )
                await asyncio.sleep(1)
                seconds -= 1

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
            f"{Fore.RED + Style.BRIGHT}[ EXIT ] Liqquidity - BOT{Style.RESET_ALL}"
                   )
