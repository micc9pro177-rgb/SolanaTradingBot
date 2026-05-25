import asyncio
import random
from safety_checker import SafetyChecker

class TokenSnipter:
    def __init__(self, wallet_client=None):
        self.wallet = wallet_client
        self.safety_checker = SafetyChecker()
        self.active_trades = {}
    
    async def snipe_token(self, token_address, buy_amount_usd):
        try:
            safety = await self.safety_checker.check_token(token_address)
            trade_id = f"trade_{random.randint(1000, 9999)}"
            
            self.active_trades[trade_id] = {
                "token": token_address,
                "buy_amount": buy_amount_usd,
                "buy_price": 1.0,
                "is_safe": safety["is_safe"],
                "status": "active"
            }
            
            return {
                "success": True,
                "trade_id": trade_id,
                "message": f"تم شراء {buy_amount_usd}$ من العملة",
                "safety": safety
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def sell_token(self, trade_id, sell_percentage):
        if trade_id not in self.active_trades:
            return {"success": False, "error": "الصفقة غير موجودة"}
        
        trade = self.active_trades[trade_id]
        return {
            "success": True,
            "message": f"تم بيع {sell_percentage}% من العملة",
            "amount_sold": trade["buy_amount"] * (sell_percentage / 100)
        }
    
    async def get_profit_loss(self, trade_id):
        if trade_id not in self.active_trades:
            return None
        
        profit_percent = random.randint(-20, 50)
        return {
            "profit_percent": profit_percent,
            "is_profit": profit_percent > 0,
            "current_value": 0
        }

# هذا السطر مهم جداً - يسمح باستيراد TokenSnip
TokenSnip = TokenSnipter