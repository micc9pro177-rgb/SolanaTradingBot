import os
from dotenv import load_dotenv
import logging

load_dotenv()

# توكن بوت تيليجرام
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# إعدادات سولانا
SOLANA_RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.devnet.solana.com")
WALLET_PRIVATE_KEY = os.getenv("WALLET_PRIVATE_KEY", "")

# إعدادات التداول
SLIPPAGE = int(os.getenv("SLIPPAGE", "5"))
TRANSACTION_TIMEOUT = int(os.getenv("TRANSACTION_TIMEOUT", "30"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

# إعدادات الشراء والبيع
BUY_AMOUNTS = [2, 4, 5, 7, 10]
SELL_PERCENTAGES = [100, 75, 50, 25]

# ========== قائمة المستخدمين المسموح لهم (Whitelist) ==========
# ضع معرفات المستخدمين (User IDs) الذين تسمح لهم باستخدام البوت
ALLOWED_USERS = [
    7013786917,  # 👈 ضع معرفك أنت هنا
957098098,  # 👈 ضع معرف صديقك هنا (أزل علامة # وأضف الرقم)
]

# إعدادات التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
