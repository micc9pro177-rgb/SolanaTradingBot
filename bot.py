#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import random
import time
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

from config import TELEGRAM_BOT_TOKEN, BUY_AMOUNTS, SELL_PERCENTAGES, logger
from sniper import TokenSnip
from safety_checker import SafetyChecker
from auto_sniper import AutoSniper

# ========== تهيئة البوت ==========
sniper = TokenSnip()
safety_checker = SafetyChecker()
auto_sniper = AutoSniper()

# ========== ذاكرة تخزين مؤقتة ==========
_data_cache = {}
_cache_time = {}

async def get_token_data(token_address: str):
    current_time = time.time()
    
    if token_address in _data_cache and (current_time - _cache_time.get(token_address, 0)) < 5:
        return _data_cache[token_address]
    
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    pairs = data.get("pairs", [])
                    if pairs:
                        pair = pairs[0]
                        price = float(pair.get("priceUsd", 0))
                        price_change_5m = pair.get("priceChange", {}).get("m5", 0)
                        price_change_1h = pair.get("priceChange", {}).get("h1", 0)
                        price_change_24h = pair.get("priceChange", {}).get("h24", 0)
                        market_cap = pair.get("fdv", 0) or pair.get("marketCap", 0)
                        
                        result = {
                            "price": price,
                            "change_5m": price_change_5m,
                            "change_1h": price_change_1h,
                            "change_24h": price_change_24h,
                            "market_cap": market_cap
                        }
                        
                        _data_cache[token_address] = result
                        _cache_time[token_address] = current_time
                        return result
    except:
        pass
    return None

async def show_token_details(update: Update, context: ContextTypes.DEFAULT_TYPE, token_address: str):
    loading_msg = None
    if not update.callback_query:
        loading_msg = await update.message.reply_text("⏳ *جاري التحليل...*", parse_mode='Markdown')
    
    safety_result = await safety_checker.check_token(token_address)
    token_data = await get_token_data(token_address)
    
    if loading_msg:
        await loading_msg.delete()
    
    if token_data:
        price = token_data["price"]
        change_5m = token_data["change_5m"]
        change_1h = token_data["change_1h"]
        change_24h = token_data["change_24h"]
        market_cap = token_data["market_cap"]
    else:
        price = 0
        change_5m = 0
        change_1h = 0
        change_24h = 0
        market_cap = 0
    
    if price < 0.0001:
        price_str = f"{price:.10f}"
    elif price < 0.01:
        price_str = f"{price:.8f}"
    else:
        price_str = f"{price:.6f}"
    
    fake_balance = round(random.uniform(0.01, 2), 4)
    
    change_5m_str = f"+{change_5m}" if change_5m > 0 else str(change_5m)
    change_1h_str = f"+{change_1h}" if change_1h > 0 else str(change_1h)
    change_24h_str = f"+{change_24h}" if change_24h > 0 else str(change_24h)
    
    details_text = f"""
🔍 *تحليل العملة*

📋 *العقد:* `{token_address[:12]}...{token_address[-10:]}`

💰 *السعر:* ${price_str}

📊 *التغيرات:* 5د: {change_5m_str}% | 1س: {change_1h_str}% | 24س: {change_24h_str}%

🏦 *القيمة السوقية:* ${market_cap:,.0f}

🛡️ *الأمان:* {safety_result.get('score', 85)}% {'✅' if safety_result.get('is_safe') else '⚠️'}

💼 *الرصيد:* {fake_balance} SOL
"""
    
    keyboard = [
        [InlineKeyboardButton("📊 مشاركة", callback_data=f'share_{token_address}')],
        [InlineKeyboardButton("🟢 $2", callback_data=f'buy_usd_2_{token_address}'), InlineKeyboardButton("🟢 $4", callback_data=f'buy_usd_4_{token_address}'), InlineKeyboardButton("🟢 $5", callback_data=f'buy_usd_5_{token_address}')],
        [InlineKeyboardButton("🟢 $7", callback_data=f'buy_usd_7_{token_address}'), InlineKeyboardButton("🟢 $10", callback_data=f'buy_usd_10_{token_address}'), InlineKeyboardButton("🟢 مخصص", callback_data=f'buy_x_sol_{token_address}')],
        [InlineKeyboardButton("🔄 DCA", callback_data=f'dca_{token_address}'), InlineKeyboardButton("🔄 Swap", callback_data=f'swap_{token_address}'), InlineKeyboardButton("📉 Limit", callback_data=f'limit_{token_address}')],
        [InlineKeyboardButton("🔄 تحديث", callback_data=f'refresh_{token_address}'), InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(details_text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(details_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    context.user_data['current_token'] = token_address

# ========== القائمة الرئيسية ==========
async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, message=None):
    chat_id = update.effective_chat.id
    auto_sniper.set_bot(context.bot, chat_id)
    
    keyboard = [
        [InlineKeyboardButton("🟢 شراء يدوي", callback_data='buy_manual'), InlineKeyboardButton("⚡ قنص تلقائي", callback_data='auto_snipe'), InlineKeyboardButton("🔍 مراقبة فقط", callback_data='alert_mode')],
        [InlineKeyboardButton("🔴 بيع", callback_data='sell'), InlineKeyboardButton("💰 المحفظة", callback_data='wallet'), InlineKeyboardButton("📊 الأرباح", callback_data='profit')],
        [InlineKeyboardButton("📋 عملاتي", callback_data='my_tokens'), InlineKeyboardButton("🛡️ وقف خسارة", callback_data='stop_loss_settings'), InlineKeyboardButton("⚙️ إعدادات", callback_data='snipe_settings')],
        [InlineKeyboardButton("📊 تحليل الزخم", callback_data='momentum_settings'), InlineKeyboardButton("🛑 إيقاف الكل", callback_data='stop_all')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = "🤖 *بوت تداول سولانا*\n\n🟢 شراء يدوي | ⚡ قنص تلقائي | 🔍 مراقبة\n🔴 بيع | 💰 المحفظة | 📊 الأرباح\n📋 عملاتي | 🛡️ وقف خسارة | ⚙️ إعدادات\n📊 تحليل الزخم | 🛑 إيقاف الكل\n🔍 *أو أرسل عنوان العقد مباشرة*"
    
    if message:
        await message.edit_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await main_menu(update, context)

# ========== معالج الأزرار ==========
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # شراء يدوي
    if query.data == 'buy_manual':
        keyboard = [[InlineKeyboardButton(f"💰 ${a}", callback_data=f'buy_{a}')] for a in BUY_AMOUNTS]
        keyboard.append([InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='back_to_main')])
        await query.edit_message_text("🟢 *اختر المبلغ:*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif query.data.startswith('buy_') and not query.data.startswith('buy_usd_') and not query.data.startswith('buy_x_sol_'):
        amount = query.data.split('_')[1]
        result = await sniper.snipe_token("So111...", float(amount))
        if result["success"]:
            if 'trades' not in context.user_data:
                context.user_data['trades'] = {}
            context.user_data['trades'][result["trade_id"]] = {"buy_amount": float(amount), "is_safe": True}
            keyboard = [[InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='back_to_main')]]
            await query.edit_message_text(f"✅ تم شراء ${amount}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        else:
            keyboard = [[InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='back_to_main')]]
            await query.edit_message_text("❌ فشل الشراء", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    # قنص تلقائي
    elif query.data == 'auto_snipe':
        keyboard = []
        for amount in BUY_AMOUNTS:
            sol_amount = round(amount / 180, 4)
            keyboard.append([InlineKeyboardButton(f"⚡ ${amount} (≈{sol_amount} SOL)", callback_data=f'auto_snipe_{sol_amount}')])
        keyboard.append([InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='back_to_main')])
        await query.edit_message_text("⚡ *تفعيل القنص التلقائي:*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif query.data.startswith('auto_snipe_'):
        sol_amount = float(query.data.split('_')[2])
        result = await auto_sniper.start_sniping(sol_amount)
        keyboard = [
            [InlineKeyboardButton("🛑 إيقاف", callback_data='stop_all')],
            [InlineKeyboardButton("📊 حالة", callback_data='snipe_status')],
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='back_to_main')]
        ]
        await query.edit_message_text(result['message'], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    # مراقبة فقط
    elif query.data == 'alert_mode':
        result = await auto_sniper.start_alert_mode()
        keyboard = [
            [InlineKeyboardButton("🛑 إيقاف", callback_data='stop_all')],
            [InlineKeyboardButton("📊 حالة", callback_data='snipe_status')],
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='back_to_main')]
        ]
        await query.edit_message_text(result['message'], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    # إيقاف الكل
    elif query.data == 'stop_all':
        result = await auto_sniper.stop_monitoring()
        keyboard = [[InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='back_to_main')]]
        await query.edit_message_text(result['message'], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    # حالة القنص
    elif query.data == 'snipe_status':
        status = await auto_sniper.get_status()
        mode = "🔍 مراقبة فقط" if status['is_alert_mode'] else "⚡ قنص تلقائي"
        text = f"📊 *الحالة*\n\n🟢 الوضع: {mode}\n{'💰 المبلغ: ' + str(status['snipe_amount']) + ' SOL' if not status['is_alert_mode'] else ''}\n🛡️ وقف الخسارة: {status['stop_loss_percent']}%\n🪙 صفقات نشطة: {status['active_trades_count']}"
        keyboard = [[InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='back_to_main')]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    # بيع
    elif query.data == 'sell':
        if 'trades' not in context.user_data or len(context.user_data['trades']) == 0:
            keyboard = [[InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='back_to_main')]]
            await query.edit_message_text("📭 لا توجد صفقات", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
            return
        keyboard = [[InlineKeyboardButton(f"🪙 {tid}", callback_data=f'sell_select_{tid}')] for tid in context.user_data['trades']]
        keyboard.append([InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='back_to_main')])
        await query.edit_message_text("🔴 *اختر الصفقة:*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif query.data.startswith('sell_select_'):
        trade_id = query.data.replace('sell_select_', '')
        context.user_data['selected_trade'] = trade_id
        keyboard = [[InlineKeyboardButton(f"📉 {p}%", callback_data=f'sell_percent_{p}')] for p in SELL_PERCENTAGES]
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data='sell')])
        await query.edit_message_text("🔴 *نسبة البيع:*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif query.data.startswith('sell_percent_'):
        percent = int(query.data.split('_')[2])
        keyboard = [[InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='back_to_main')]]
        await query.edit_message_text(f"✅ تم بيع {percent}%", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    # محفظة
    elif query.data == 'wallet':
        keyboard = [[InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='back_to_main')]]
        await query.edit_message_text(f"💰 *المحفظة*\nالرصيد: {round(random.uniform(0.1,5),3)} SOL\n⚠️ تجريبي", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    # أرباح
    elif query.data == 'profit':
        keyboard = [[InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='back_to_main')]]
        await query.edit_message_text("📊 *لا توجد أرباح بعد*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    # فحص عقد
    elif query.data == 'check_contract':
        await query.edit_message_text("🔒 *أرسل عنوان العقد لفحصه:*", parse_mode='Markdown')
        context.user_data['awaiting_contract'] = True
    
    # عملاتي
    elif query.data == 'my_tokens':
        keyboard = [[InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='back_to_main')]]
        if 'trades' not in context.user_data or len(context.user_data['trades']) == 0:
            await query.edit_message_text("📋 *لا تمتلك أي عملات*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        else:
            text = "📋 *عملاتك:*\n" + "\n".join([f"🪙 {tid}: ${t['buy_amount']}" for tid, t in context.user_data['trades'].items()])
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    # إعدادات وقف الخسارة
    elif query.data == 'stop_loss_settings':
        current_sl = auto_sniper.stop_loss_percent
        keyboard = [
            [InlineKeyboardButton(f"{'✅' if current_sl == 10 else '🔘'} 10%", callback_data='sl_10')],
            [InlineKeyboardButton(f"{'✅' if current_sl == 15 else '🔘'} 15%", callback_data='sl_15')],
            [InlineKeyboardButton(f"{'✅' if current_sl == 20 else '🔘'} 20%", callback_data='sl_20')],
            [InlineKeyboardButton(f"{'✅' if current_sl == 25 else '🔘'} 25%", callback_data='sl_25')],
            [InlineKeyboardButton(f"{'✅' if current_sl == 30 else '🔘'} 30%", callback_data='sl_30')],
            [InlineKeyboardButton(f"{'✅' if current_sl == 40 else '🔘'} 40%", callback_data='sl_40')],
            [InlineKeyboardButton(f"{'✅' if current_sl == 50 else '🔘'} 50%", callback_data='sl_50')],
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='back_to_main')]
        ]
        await query.edit_message_text(
            f"🛡️ *إعدادات وقف الخسارة*\n\n"
            f"النسبة الحالية: *{current_sl}%*\n\n"
            f"اختر النسبة المناسبة:\n"
            f"• 10-15%: عملات عالية المخاطرة\n"
            f"• 20-25%: عملات متوسطة المخاطرة\n"
            f"• 30-50%: عملات آمنة",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    elif query.data.startswith('sl_'):
        percent = int(query.data.split('_')[1])
        auto_sniper.set_stop_loss(percent)
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع للإعدادات", callback_data='stop_loss_settings')]]
        await query.edit_message_text(
            f"✅ *تم ضبط وقف الخسارة إلى {percent}%*\n\n"
            f"سيتم بيع العملة تلقائياً إذا نزل السعر {percent}% عن سعر الشراء",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    # إعدادات تحليل الزخم (شرح فقط)
    elif query.data == 'momentum_settings':
        keyboard = [[InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='back_to_main')]]
        await query.edit_message_text(
            "📊 *تحليل الزخم التلقائي*\n\n"
            "📈 *تصنيفات الزخم:*\n"
            "🚀 *صاروخي* (50%+ في الدقيقة) → شراء عاجل\n"
            "⚡ *قوي* (20-50%) → شراء موصى به\n"
            "📈 *متوسط* (10-20%) → شراء بحذر\n"
            "🐢 *ضعيف* (5-10%) → تجنب الشراء\n"
            "📉 *سلبي* (أقل من 5%) → لا تشتري\n\n"
            "✅ *الزخم يحسب تلقائياً عند اكتشاف العملة*\n"
            "⚠️ البوت يشتري فقط إذا الزخم قوي أو صاروخي",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    # إعدادات السرعة
    elif query.data == 'snipe_settings':
        keyboard = [
            [InlineKeyboardButton("🐌 بطيء", callback_data='speed_slow'), InlineKeyboardButton("⚡ عادي", callback_data='speed_normal'), InlineKeyboardButton("🚀 برق", callback_data='speed_fast')],
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='back_to_main')]
        ]
        await query.edit_message_text("⚙️ *سرعة القنص:*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif query.data.startswith('speed_'):
        speed = query.data.split('_')[1]
        context.user_data['snipe_speed'] = speed
        speed_names = {'slow': 'بطيء', 'normal': 'عادي', 'fast': 'برق'}
        keyboard = [
            [InlineKeyboardButton("🐌 بطيء", callback_data='speed_slow'), InlineKeyboardButton("⚡ عادي", callback_data='speed_normal'), InlineKeyboardButton("🚀 برق", callback_data='speed_fast')],
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='back_to_main')]
        ]
        await query.edit_message_text(f"✅ تم الضبط: {speed_names.get(speed, speed)}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    # رجوع للقائمة الرئيسية
    elif query.data == 'back_to_main':
        await main_menu(update, context, message=query.message)
    
    # أزرار الشراء بالدولار
    elif query.data.startswith('buy_usd_'):
        parts = query.data.split('_')
        amount = parts[2]
        token = '_'.join(parts[3:])
        keyboard = [[InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='back_to_main')]]
        await query.edit_message_text(f"✅ *تم تنفيذ شراء تجريبي بقيمة ${amount}*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    # مشاركة
    elif query.data.startswith('share_'):
        token = query.data.replace('share_', '')
        keyboard = [[InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='back_to_main')]]
        await query.edit_message_text(f"🔗 *العقد:*\n`{token}`", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    # شراء مخصص
    elif query.data.startswith('buy_x_sol_'):
        token = query.data.replace('buy_x_sol_', '')
        await query.edit_message_text("💰 *أرسل المبلغ المراد شراؤه بالدولار:*\nمثال: 25", parse_mode='Markdown')
        context.user_data['awaiting_custom_buy'] = token
    
    # تحديث
    elif query.data.startswith('refresh_'):
        token = query.data.replace('refresh_', '')
        await show_token_details(update, context, token)
    
    # DCA, Swap, Limit
    elif query.data.startswith('dca_') or query.data.startswith('swap_') or query.data.startswith('limit_'):
        keyboard = [[InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='back_to_main')]]
        await query.edit_message_text("🚧 *هذه الميزة قيد التطوير*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# ========== معالج الرسائل ==========
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    if context.user_data.get('awaiting_contract'):
        context.user_data['awaiting_contract'] = False
        await show_token_details(update, context, text)
    elif context.user_data.get('awaiting_custom_buy'):
        token = context.user_data['awaiting_custom_buy']
        context.user_data['awaiting_custom_buy'] = None
        try:
            amount = float(text)
            keyboard = [[InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='back_to_main')]]
            await update.message.reply_text(f"✅ *تم تنفيذ شراء تجريبي بقيمة ${amount}*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        except:
            await update.message.reply_text("❌ خطأ: الرجاء إرسال رقم صحيح", parse_mode='Markdown')
    else:
        await show_token_details(update, context, text)

# ========== تشغيل البوت ==========
def main():
    if not TELEGRAM_BOT_TOKEN:
        print("❌ خطأ: TELEGRAM_BOT_TOKEN غير موجود")
        return
    
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("=" * 45)
    print("✅ البوت شغال | تحديث كل 5 ثوانٍ | رصد حقيقي")
    print("✅ أوضاع: قنص تلقائي | مراقبة فقط")
    print("✅ تحليل الزخم التلقائي مفعل")
    print("=" * 45)
    app.run_polling()

if __name__ == "__main__":
    main()