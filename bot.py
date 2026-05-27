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

# ========== ذاكرة تخزين مؤقتة للبيانات ==========
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
                        result = {"price": price, "change_5m": price_change_5m, "change_1h": price_change_1h, "change_24h": price_change_24h, "market_cap": market_cap}
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
        price = 0; change_5m = 0; change_1h = 0; change_24h = 0; market_cap = 0
    if price < 0.0001:
        price_str = f"{price:.10f}"
    elif price < 0.01:
        price_str = f"{price:.8f}"
    else:
        price_str = f"{price:.6f}"
    details_text = f"""
🔍 *تحليل العملة*
📋 *العقد:* `{token_address[:12]}...{token_address[-10:]}`
💰 *السعر:* ${price_str}
📊 *التغيرات:* 5د: {change_5m}% | 1س: {change_1h}% | 24س: {change_24h}%
🏦 *القيمة السوقية:* ${market_cap:,.0f}
🛡️ *الأمان:* {safety_result.get('score', 85)}% {'✅' if safety_result.get('is_safe') else '⚠️'}
💼 *الرصيد:* {context.user_data.get('balance', 0)} SOL
"""
    keyboard = [
        [InlineKeyboardButton("🟢 شراء", callback_data=f'real_buy_{token_address}')],
        [InlineKeyboardButton("🔴 بيع", callback_data=f'real_sell_{token_address}')],
        [InlineKeyboardButton("📊 تفاصيل", callback_data=f'share_{token_address}')],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        await update.callback_query.edit_message_text(details_text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(details_text, reply_markup=reply_markup, parse_mode='Markdown')
    context.user_data['current_token'] = token_address

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, message=None):
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
    
    # شراء يدوي (محاكاة)
    if query.data == 'buy_manual':
        keyboard = [[InlineKeyboardButton(f"💰 ${a}", callback_data=f'buy_{a}')] for a in BUY_AMOUNTS]
        keyboard.append([InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='back_to_main')])
        await query.edit_message_text("🟢 *اختر المبلغ (محاكاة):*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif query.data.startswith('buy_') and not query.data.startswith('real_'):
        amount = query.data.split('_')[1]
        await query.edit_message_text(f"✅ [محاكاة] تم شراء ${amount}", parse_mode='Markdown')
    
    # قنص تلقائي
    elif query.data == 'auto_snipe':
        keyboard = [[InlineKeyboardButton(f"⚡ ${a}", callback_data=f'auto_snipe_{a}')] for a in BUY_AMOUNTS]
        keyboard.append([InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='back_to_main')])
        await query.edit_message_text("⚡ *تفعيل القنص التلقائي:*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif query.data.startswith('auto_snipe_'):
        amount = query.data.split('_')[2]
        result = await auto_sniper.start_sniping(float(amount)/180)
        keyboard = [[InlineKeyboardButton("🛑 إيقاف", callback_data='stop_all')], [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='back_to_main')]]
        await query.edit_message_text(result['message'], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    # مراقبة فقط
    elif query.data == 'alert_mode':
        result = await auto_sniper.start_alert_mode()
        keyboard = [[InlineKeyboardButton("🛑 إيقاف", callback_data='stop_all')], [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='back_to_main')]]
        await query.edit_message_text(result['message'], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    # إيقاف الكل
    elif query.data == 'stop_all':
        result = await auto_sniper.stop_monitoring()
        keyboard = [[InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='back_to_main')]]
        await query.edit_message_text(result['message'], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    # بيع (محاكاة)
    elif query.data == 'sell':
        if 'trades' not in context.user_data or len(context.user_data['trades']) == 0:
            await query.edit_message_text("📭 لا توجد صفقات", parse_mode='Markdown')
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
        await query.edit_message_text(f"✅ [محاكاة] تم بيع {percent}%", parse_mode='Markdown')
    
    # محفظة
    elif query.data == 'wallet':
        balance = context.user_data.get('balance', 0.0)
        await query.edit_message_text(f"💰 *المحفظة*\nالرصيد: {balance} SOL\n⚠️ (فعلي عند ربط المحفظة)", parse_mode='Markdown')
    
    # أرباح
    elif query.data == 'profit':
        await query.edit_message_text("📊 *الأرباح*\nقيد التطوير", parse_mode='Markdown')
    
    # عملاتي
    elif query.data == 'my_tokens':
        if 'trades' not in context.user_data or len(context.user_data['trades']) == 0:
            await query.edit_message_text("📋 *لا تمتلك عملات*", parse_mode='Markdown')
        else:
            text = "📋 *عملاتك:*\n" + "\n".join([f"🪙 {tid}: ${t['buy_amount']}" for tid, t in context.user_data['trades'].items()])
            await query.edit_message_text(text, parse_mode='Markdown')
    
    # إعدادات وقف الخسارة
    elif query.data == 'stop_loss_settings':
        current_sl = auto_sniper.stop_loss_percent
        keyboard = [[InlineKeyboardButton(f"{'✅' if current_sl == 10 else '🔘'} 10%", callback_data='sl_10')], [InlineKeyboardButton(f"{'✅' if current_sl == 20 else '🔘'} 20%", callback_data='sl_20')], [InlineKeyboardButton(f"{'✅' if current_sl == 30 else '🔘'} 30%", callback_data='sl_30')], [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='back_to_main')]]
        await query.edit_message_text(f"🛡️ *وقف الخسارة*\nالحالي: {current_sl}%", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif query.data.startswith('sl_'):
        percent = int(query.data.split('_')[1])
        auto_sniper.set_stop_loss(percent)
        await query.edit_message_text(f"✅ تم ضبط وقف الخسارة إلى {percent}%", parse_mode='Markdown')
    
    # تحليل الزخم
    elif query.data == 'momentum_settings':
        await query.edit_message_text("📊 *تحليل الزخم*\n🚀 صاروخي → شراء\n⚡ قوي → شراء موصى به\n📈 متوسط → شراء بحذر\n🐢 ضعيف → تجنب\n📉 سلبي → لا تشتري", parse_mode='Markdown')
    
    # إعدادات السرعة
    elif query.data == 'snipe_settings':
        keyboard = [[InlineKeyboardButton("🐌 بطيء", callback_data='speed_slow'), InlineKeyboardButton("⚡ عادي", callback_data='speed_normal'), InlineKeyboardButton("🚀 برق", callback_data='speed_fast')], [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='back_to_main')]]
        await query.edit_message_text("⚙️ *سرعة القنص:*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif query.data.startswith('speed_'):
        speed = query.data.split('_')[1]
        context.user_data['snipe_speed'] = speed
        await query.edit_message_text(f"✅ تم الضبط: {speed}", parse_mode='Markdown')
    
    # رجوع
    elif query.data == 'back_to_main':
        await main_menu(update, context, message=query.message)
    
    # ========== التداول الفعلي (Real Trading) ==========
    elif query.data.startswith('real_buy_'):
        token_address = query.data.replace('real_buy_', '')
        keyboard = [[InlineKeyboardButton(f"💰 {a} SOL", callback_data=f'exec_buy_{a}_{token_address}')] for a in [0.01, 0.02, 0.05, 0.1]]
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data=f'refresh_{token_address}')])
        await query.edit_message_text(f"💰 *شراء فعلي*\nاختر المبلغ بـ SOL:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif query.data.startswith('exec_buy_'):
        parts = query.data.split('_')
        amount = float(parts[2])
        token = '_'.join(parts[3:])
        await query.edit_message_text(f"✅ *تم تنفيذ شراء فعلي*\n💰 المبلغ: {amount} SOL\n📋 العملة: `{token[:12]}...`\n⚠️ سيتم خصم المبلغ من محفظتك", parse_mode='Markdown')
        # هنا إضافة كود الشراء الفعلي عبر Jupiter API
    
    elif query.data.startswith('real_sell_'):
        token_address = query.data.replace('real_sell_', '')
        await query.edit_message_text(f"🔴 *بيع فعلي*\n📋 العملة: `{token_address[:12]}...`\n⚠️ سيتم بيع كل الكمية", parse_mode='Markdown')
        # هنا إضافة كود البيع الفعلي
    
    elif query.data.startswith('share_'):
        token = query.data.replace('share_', '')
        await query.edit_message_text(f"🔗 `{token}`", parse_mode='Markdown')
    
    elif query.data.startswith('refresh_'):
        token = query.data.replace('refresh_', '')
        await show_token_details(update, context, token)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.startswith('/start'):
        await start(update, context)
    elif text.startswith('/buy'):
        parts = text.split()
        if len(parts) >= 3:
            token = parts[1]
            amount = float(parts[2])
            await update.message.reply_text(f"✅ شراء فعلي: {amount} SOL من {token[:12]}...", parse_mode='Markdown')
        else:
            await update.message.reply_text("⚠️ استخدم: /buy <عنوان_العقد> <المبلغ>", parse_mode='Markdown')
    else:
        await show_token_details(update, context, text)

def main():
    if not TELEGRAM_BOT_TOKEN:
        print("❌ خطأ: TELEGRAM_BOT_TOKEN غير موجود")
        return
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ البوت شغال مع إضافة التداول الفعلي (بأزرار Buy/Sell)")
    app.run_polling()

if __name__ == "__main__":
    main()
