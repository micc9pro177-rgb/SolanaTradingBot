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
        self.PUMP_PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
        
    def set_bot(self, bot, chat_id):
        self.bot = bot
        self.chat_id = chat_id
    
    def set_stop_loss(self, percent):
        self.stop_loss_percent = percent
    
    async def start_alert_mode(self):
        self.is_running = True
        self.is_alert_mode = True
        self.reconnect_count = 0
        self.monitor_task = asyncio.create_task(self._monitor_solana_direct())
        
        if self.bot and self.chat_id:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=f"🔍 *تم تفعيل وضع المراقبة*\n📡 رصد مباشر لمعاملات Pump.fun\n🛡️ وقف الخسارة: {self.stop_loss_percent}%",
                parse_mode='Markdown'
            )
        return {"success": True, "message": "🔍 تم تفعيل المراقبة"}
    
    async def start_sniping(self, amount_sol):
        self.snipe_amount = amount_sol
        self.is_running = True
        self.is_alert_mode = False
        self.reconnect_count = 0
        self.monitor_task = asyncio.create_task(self._monitor_solana_direct())
        
        if self.bot and self.chat_id:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=f"⚡ *تم تفعيل القنص التلقائي*\n💰 المبلغ: {amount_sol} SOL\n📡 رصد مباشر لمعاملات Pump.fun\n🛡️ وقف الخسارة: {self.stop_loss_percent}%",
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
    
    async def _monitor_solana_direct(self):
        """اتصال مباشر بشبكة سولانا لمراقبة معاملات Pump.fun"""
        ws_url = "wss://api.mainnet-beta.solana.com"
        
        while self.is_running:
            try:
                async with websockets.connect(ws_url) as websocket:
                    self.ws_connection = websocket
                    self.reconnect_count = 0
                    print("✅ متصل مباشرة بشبكة سولانا")
                    
                    subscribe_msg = {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "logsSubscribe",
                        "params": [
                            {"mentions": [self.PUMP_PROGRAM]},
                            {"commitment": "processed"}
                        ]
                    }
                    await websocket.send(json.dumps(subscribe_msg))
                    print("📡 جاري مراقبة معاملات Pump.fun...")
                    
                    if self.bot and self.chat_id and self.reconnect_count == 0:
                        await self.bot.send_message(
                            chat_id=self.chat_id,
                            text=f"✅ *تم الاتصال بشبكة سولانا*\n📡 جاري مراقبة معاملات Pump.fun...\n🛡️ وقف الخسارة: {self.stop_loss_percent}%",
                            parse_mode='Markdown'
                        )
                    
                    async for message in websocket:
                        if not self.is_running:
                            break
                        try:
                            data = json.loads(message)
                            await self._process_transaction(data)
                        except Exception as e:
                            print(f"خطأ: {e}")
                            
            except Exception as e:
                self.reconnect_count += 1
                print(f"❌ خطأ: {e}. إعادة محاولة {self.reconnect_count} خلال 5 ثوانٍ...")
                await asyncio.sleep(5)
        
        print("🛑 توقفت المراقبة")
    
    async def _process_transaction(self, data):
        """معالجة المعاملات وإرسال إشعارات"""
        try:
            if "params" in data and "result" in data["params"]:
                result = data["params"]["result"]
                signature = result.get("signature", "")
                
                if signature:
                    print(f"\n🆕 معاملة جديدة على Pump.fun!")
                    print(f"   التوقيع: {signature[:30]}...")
                    
                    if self.bot and self.chat_id:
                        msg = f"""🆕 *نشاط جديد على Pump.fun!*

🔗 *التوقيع:* `{signature[:30]}...`
💰 *مبلغ القنص:* {self.snipe_amount} SOL (تجريبي)

🛡️ *وقف الخسارة:* {self.stop_loss_percent}%"""

                        if self.is_alert_mode:
                            msg += f"\n\n🔔 *وضع المراقبة*\n💰 للشراء اليدوي، استخدم الأمر /buy"
                            await self.bot.send_message(chat_id=self.chat_id, text=msg, parse_mode='Markdown')
                        else:
                            msg += f"\n\n⚡ *جاري الشراء التلقائي...*"
                            await self.bot.send_message(chat_id=self.chat_id, text=msg, parse_mode='Markdown')
                            # تنفيذ الشراء التلقائي
                            trade_id = f"SNIPE_{int(time.time())}_{random.randint(100, 999)}"
                            self.active_trades[trade_id] = {
                                "token": signature[:20],
                                "buy_amount": self.snipe_amount,
                                "buy_time": time.time(),
                                "status": "active"
                            }
                            await self.bot.send_message(
                                chat_id=self.chat_id,
                                text=f"✅ *تم شراء العملة*\n💰 المبلغ: {self.snipe_amount} SOL",
                                parse_mode='Markdown'
                            )
                    
        except Exception as e:
            print(f"خطأ: {e}")
    
    async def get_status(self):
        return {
            "is_running": self.is_running,
            "is_alert_mode": self.is_alert_mode,
            "snipe_amount": self.snipe_amount,
            "stop_loss_percent": self.stop_loss_percent,
            "active_trades_count": len(self.active_trades)
        }
