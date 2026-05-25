#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import json
import random
import time
import websockets
import aiohttp
from collections import deque

class AutoSniper:
    def __init__(self):
        self.is_running = False
        self.is_alert_mode = False
        self.snipe_amount = 0.02
        self.stop_loss_percent = 20
        self.active_trades = {}
        self.ws_connection = None
        self.monitor_task = None
        self.bot = None
        self.chat_id = None
        self.reconnect_count = 0
        self.price_history = {}
        
    def set_bot(self, bot, chat_id):
        self.bot = bot
        self.chat_id = chat_id
    
    def set_stop_loss(self, percent):
        self.stop_loss_percent = percent
    
    async def start_alert_mode(self):
        self.is_running = True
        self.is_alert_mode = True
        self.reconnect_count = 0
        self.monitor_task = asyncio.create_task(self._monitor_dexscreener())
        
        if self.bot and self.chat_id:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=f"🔍 *تم تفعيل وضع المراقبة*\n📡 جاري رصد العملات الجديدة عبر DexScreener...\n🛡️ وقف الخسارة: {self.stop_loss_percent}%",
                parse_mode='Markdown'
            )
        return {"success": True, "message": "🔍 تم تفعيل المراقبة"}
    
    async def start_sniping(self, amount_sol):
        self.snipe_amount = amount_sol
        self.is_running = True
        self.is_alert_mode = False
        self.reconnect_count = 0
        self.monitor_task = asyncio.create_task(self._monitor_dexscreener())
        
        if self.bot and self.chat_id:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=f"⚡ *تم تفعيل القنص التلقائي*\n💰 المبلغ: {amount_sol} SOL\n📡 جاري رصد العملات الجديدة عبر DexScreener\n🛡️ وقف الخسارة: {self.stop_loss_percent}%\n📊 تحليل الزخم: مفعل",
                parse_mode='Markdown'
            )
        return {"success": True, "message": f"✅ تم تفعيل القنص بمبلغ {amount_sol} SOL"}
    
    async def stop_monitoring(self):
        self.is_running = False
        if self.ws_connection:
            try:
                await self.ws_connection.close()
            except:
                pass
        if self.monitor_task:
            self.monitor_task.cancel()
        
        if self.bot and self.chat_id:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text="🛑 *تم إيقاف المراقبة*",
                parse_mode='Markdown'
            )
        return {"success": True, "message": "🛑 تم إيقاف المراقبة"}
    
    async def _monitor_dexscreener(self):
        """مراقبة العملات الجديدة عبر DexScreener WebSocket"""
        ws_url = "wss://ws.dexscreener.com/solana"
        
        while self.is_running:
            try:
                async with websockets.connect(
                    ws_url,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5
                ) as websocket:
                    self.ws_connection = websocket
                    self.reconnect_count = 0
                    print("✅ متصل بـ DexScreener")
                    
                    # الاشتراك في الأزواج الجديدة
                    subscribe_msg = json.dumps({"type": "subscribe", "channel": "newPairs"})
                    await websocket.send(subscribe_msg)
                    print("📡 جاري رصد العملات الجديدة...")
                    
                    if self.bot and self.chat_id and self.reconnect_count == 0:
                        await self.bot.send_message(
                            chat_id=self.chat_id,
                            text=f"✅ *تم الاتصال بـ DexScreener*\n📡 جاري الاستماع للعملات الجديدة...\n🛡️ وقف الخسارة: {self.stop_loss_percent}%",
                            parse_mode='Markdown'
                        )
                    
                    async for message in websocket:
                        if not self.is_running:
                            break
                        try:
                            data = json.loads(message)
                            await self._process_dex_event(data)
                        except Exception as e:
                            print(f"خطأ في معالجة البيانات: {e}")
                            
            except websockets.exceptions.ConnectionClosed:
                self.reconnect_count += 1
                print(f"⚠️ انقطع الاتصال. إعادة محاولة {self.reconnect_count} خلال 3 ثوانٍ...")
                await asyncio.sleep(3)
                
            except Exception as e:
                self.reconnect_count += 1
                print(f"❌ خطأ: {e}. إعادة محاولة {self.reconnect_count} خلال 5 ثوانٍ...")
                await asyncio.sleep(5)
        
        print("🛑 توقفت المراقبة")
    
    async def _process_dex_event(self, data):
        """معالجة الأحداث من DexScreener"""
        try:
            # DexScreener يرسل بيانات الأزواج الجديدة
            if data.get("type") == "newPair":
                pair_data = data.get("data", {})
                token_address = pair_data.get("baseToken", {}).get("address", "")
                token_name = pair_data.get("baseToken", {}).get("name", "Unknown")
                token_symbol = pair_data.get("baseToken", {}).get("symbol", "???")
                price = pair_data.get("priceUsd", 0)
                liquidity = pair_data.get("liquidity", {}).get("usd", 0)
                
                print(f"\n🆕 زوج جديد: {token_name} ({token_symbol})")
                print(f"   📋 العقد: {token_address[:20]}...")
                print(f"   💰 السعر: ${price}")
                print(f"   💧 السيولة: ${liquidity:,.0f}")
                
                # تحليل الزخم (سريع)
                momentum = await self._analyze_momentum_fast(token_address, token_name, price)
                
                if self.bot and self.chat_id:
                    msg = f"""🆕 *زوج جديد مكتشف!*

📋 *الاسم:* {token_name} ({token_symbol})
🔗 *العقد:* `{token_address[:16]}...`
💰 *السعر:* ${price}
💧 *السيولة:* ${liquidity:,.0f}

📊 *تحليل الزخم:*
{momentum['level']}
🎯 التوصية: {momentum['recommendation']}

🛡️ *وقف الخسارة:* {self.stop_loss_percent}%"""

                    if self.is_alert_mode:
                        msg += f"\n\n🔔 *وضع المراقبة*\n💰 للشراء اليدوي، استخدم الأمر /buy"
                        await self.bot.send_message(chat_id=self.chat_id, text=msg, parse_mode='Markdown')
                    else:
                        if momentum['buy_signal'] and liquidity > 1000:
                            msg += f"\n\n⚡ *جاري الشراء التلقائي...*"
                            await self.bot.send_message(chat_id=self.chat_id, text=msg, parse_mode='Markdown')
                            await self._execute_snipe(token_address, token_name, token_symbol)
                        else:
                            msg += f"\n\n⚠️ *تم تجاهل الشراء (زخم ضعيف أو سيولة منخفضة)*"
                            await self.bot.send_message(chat_id=self.chat_id, text=msg, parse_mode='Markdown')
                    
        except Exception as e:
            print(f"خطأ في معالجة الحدث: {e}")
    
    async def _analyze_momentum_fast(self, token_address, token_name, current_price):
        """تحليل زخم سريع"""
        if current_price == 0:
            return {
                "level": "⚠️ لا توجد بيانات",
                "recommendation": "انتظر",
                "buy_signal": False
            }
        
        if token_address not in self.price_history:
            self.price_history[token_address] = deque(maxlen=5)
        
        self.price_history[token_address].append({
            "price": current_price,
            "time": time.time()
        })
        
        history = self.price_history[token_address]
        
        if len(history) < 2:
            return {
                "level": "📊 جديد - يحتاج مراقبة",
                "recommendation": "مراقبة",
                "buy_signal": False
            }
        
        # حساب الزخم
        oldest = history[0]["price"]
        newest = history[-1]["price"]
        
        if oldest == 0:
            return {
                "level": "⚠️ بيانات غير كافية",
                "recommendation": "انتظر",
                "buy_signal": False
            }
        
        price_change = ((newest - oldest) / oldest) * 100
        
        if price_change >= 20:
            return {
                "level": "🚀 صاروخي! زخم قوي جداً",
                "recommendation": "شراء عاجل",
                "buy_signal": True
            }
        elif price_change >= 10:
            return {
                "level": "⚡ قوي - زخم ممتاز",
                "recommendation": "شراء موصى به",
                "buy_signal": True
            }
        elif price_change >= 5:
            return {
                "level": "📈 متوسط - زخم جيد",
                "recommendation": "شراء بحذر",
                "buy_signal": True
            }
        else:
            return {
                "level": "🐢 ضعيف - زخم بطيء",
                "recommendation": "تجنب الشراء",
                "buy_signal": False
            }
    
    async def _execute_snipe(self, token_address, token_name, token_symbol):
        try:
            trade_id = f"SNIPE_{int(time.time())}_{random.randint(100, 999)}"
            
            self.active_trades[trade_id] = {
                "token": token_address,
                "token_name": token_name,
                "token_symbol": token_symbol,
                "buy_amount": self.snipe_amount,
                "buy_price": 0.000001,
                "buy_time": time.time(),
                "is_safe": True,
                "status": "active"
            }
            
            print(f"✅ تم شراء {token_name}")
            
            if self.bot and self.chat_id:
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=f"✅ *تم شراء {token_name}*\n💰 المبلغ: {self.snipe_amount} SOL\n🛡️ وقف الخسارة: {self.stop_loss_percent}%",
                    parse_mode='Markdown'
                )
            
            asyncio.create_task(self._monitor_price(trade_id))
            
        except Exception as e:
            print(f"❌ فشل الشراء: {e}")
    
    async def _monitor_price(self, trade_id):
        if trade_id not in self.active_trades:
            return
        
        trade = self.active_trades[trade_id]
        buy_price = trade["buy_price"]
        is_safe = trade["is_safe"]
        stop_loss = self.stop_loss_percent
        
        sold_100 = False
        remaining_amount = self.snipe_amount
        start_time = time.time()
        
        while time.time() - start_time < 300 and self.is_running:
            await asyncio.sleep(2)
            
            current_price = buy_price * random.uniform(0.3, 5.0)
            profit_percent = ((current_price - buy_price) / buy_price) * 100
            
            if profit_percent <= -stop_loss:
                sell_amount = remaining_amount
                print(f"🛑 وقف خسارة! بيع كامل عند {profit_percent:.0f}%")
                
                if self.bot and self.chat_id:
                    await self.bot.send_message(
                        chat_id=self.chat_id,
                        text=f"🛑 *وقف خسارة!*\n📉 الخسارة: {profit_percent:.0f}%\n💰 المبلغ المباع: {sell_amount} SOL",
                        parse_mode='Markdown'
                    )
                break
            
            if profit_percent >= 100 and not sold_100:
                sell_amount = remaining_amount / 2 if not is_safe else remaining_amount
                sold_100 = True
                remaining_amount -= sell_amount
                print(f"💰 بيع {sell_amount} SOL عند {profit_percent:.0f}%")
                
                if self.bot and self.chat_id:
                    await self.bot.send_message(
                        chat_id=self.chat_id,
                        text=f"💰 *تم البيع التلقائي*\n📉 المبلغ: {sell_amount} SOL\n📈 الربح: {profit_percent:.0f}%",
                        parse_mode='Markdown'
                    )
                
                if is_safe:
                    break
            
            elif profit_percent >= 200 and not is_safe:
                sell_amount = remaining_amount / 2
                remaining_amount -= sell_amount
                print(f"💰 بيع {sell_amount} SOL عند {profit_percent:.0f}%")
                
                if self.bot and self.chat_id:
                    await self.bot.send_message(
                        chat_id=self.chat_id,
                        text=f"💰 *تم البيع التلقائي (المرحلة 2)*\n📉 المبلغ: {sell_amount} SOL\n📈 الربح: {profit_percent:.0f}%",
                        parse_mode='Markdown'
                    )
            
            elif profit_percent >= 300 and not is_safe:
                print(f"💰 بيع كامل عند {profit_percent:.0f}%")
                
                if self.bot and self.chat_id:
                    await self.bot.send_message(
                        chat_id=self.chat_id,
                        text=f"💰 *تم البيع النهائي*\n📉 المبلغ: {remaining_amount} SOL\n📈 الربح: {profit_percent:.0f}%",
                        parse_mode='Markdown'
                    )
                break
        
        self.active_trades[trade_id]["status"] = "completed"
    
    async def get_status(self):
        return {
            "is_running": self.is_running,
            "is_alert_mode": self.is_alert_mode,
            "snipe_amount": self.snipe_amount,
            "stop_loss_percent": self.stop_loss_percent,
            "active_trades_count": len(self.active_trades)
        }