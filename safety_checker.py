import aiohttp
import asyncio
import json

class SafetyChecker:
    def __init__(self):
        self.rugcheck_api = "https://api.rugcheck.xyz/v1"
    
    async def check_token(self, token_address):
        """فحص العقد مباشرة من RugCheck API"""
        try:
            # طلب التقرير من RugCheck
            async with aiohttp.ClientSession() as session:
                url = f"{self.rugcheck_api}/tokens/{token_address}/report"
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._format_rugcheck_report(data, token_address)
                    else:
                        # فشل الاتصال
                        return self._offline_report(token_address, f"HTTP {response.status}")
        except Exception as e:
            return self._offline_report(token_address, str(e))
    
    def _format_rugcheck_report(self, data, token_address):
        """تنسيق تقرير RugCheck الحقيقي"""
        
        # ======== استخراج البيانات الحقيقية من الـ API ========
        score = data.get("score", 0)
        risks = data.get("risks", [])
        holder_count = data.get("holderCount", 0)
        mint_authority = data.get("mintAuthority")
        freeze_authority = data.get("freezeAuthority")
        
        # نسبة أكبر المالكين
        top_holders = data.get("topHolders", [])
        top_10_pct = 0
        top_1_pct = 0
        
        if top_holders:
            top_1_pct = top_holders[0].get("pct", 0) if len(top_holders) > 0 else 0
            top_10_pct = sum([h.get("pct", 0) for h in top_holders[:10]])
        
        # فحص قفل السيولة
        locks = data.get("locks", [])
        lp_locked = len(locks) > 0
        lp_lock_percentage = 0
        
        if lp_locked:
            # حساب نسبة السيولة المقفولة
            total_locked = sum([lock.get("amount", 0) for lock in locks])
            lp_lock_percentage = min(100, total_locked / 1000)  # تبسيط
        
        # هل يمكن سحب السيولة؟
        can_drain = not lp_locked and mint_authority is not None
        
        # هل العقد معدل (Mintable)؟
        is_mintable = mint_authority is not None and mint_authority != "disabled"
        
        # تحديد مستوى الأمان بناءً على البيانات الحقيقية
        if score >= 90 and lp_locked and not is_mintable and not can_drain:
            status = "✅ آمن جداً"
            emoji = "🟢"
            safe = True
        elif score >= 70 and lp_locked:
            status = "⚠️ آمن نسبياً - تداول بحذر"
            emoji = "🟡"
            safe = True
        elif score >= 50:
            status = "⚠️ مخاطر متوسطة"
            emoji = "🟠"
            safe = False
        else:
            status = "🔴 خطر عالي - لا تتداول"
            emoji = "🔴"
            safe = False
        
        # بناء التقرير النهائي
        report = f"""
{emoji} *نتيجة فحص العقد - RugCheck*

📋 *العقد:* `{token_address[:16]}...{token_address[-12:]}`

🎯 *نسبة الأمان:* {score}% ({status})

📊 *عدد الحاملين:* {holder_count:,}

🏦 *أكبر مالك يملك:* {top_1_pct:.1f}%
🏦 *أكبر 10 مالكين يملكون:* {top_10_pct:.1f}%

🔒 *السيولة مقفلة:* {'✅ نعم' if lp_locked else '❌ لا'} ({lp_lock_percentage:.0f}%)

💸 *إمكانية سحب السيولة:* {'⚠️ نعم (خطر)' if can_drain else '✅ لا'}

✏️ *العقد قابل للزيادة (Mintable):* {'⚠️ نعم' if is_mintable else '✅ لا'}

❄️ *التجميد (Freeze):* {'⚠️ متاح' if freeze_authority else '✅ غير متاح'}

⚠️ *عدد المخاطر:* {len(risks)}
"""
        
        # إضافة المخاطر إن وجدت
        if risks:
            report += "\n⚠️ *المخاطر المكتشفة:*\n"
            for risk in risks[:5]:
                name = risk.get("name", "مخطر")
                level = risk.get("level", "unknown")
                level_emoji = "🔴" if level == "high" else "🟡" if level == "medium" else "🟢"
                report += f"{level_emoji} {name}\n"
        
        # رابط الموقع
        report += f"\n🔗 *رابط الفحص الكامل:* rugcheck.xyz/tokens/{token_address}"
        
        return {
            "is_safe": safe,
            "score": score,
            "details": report,
            "raw_score": score
        }
    
    def _offline_report(self, token_address, error_msg):
        """تقرير عند فشل الاتصال (بدون أرقام وهمية)"""
        return {
            "is_safe": False,
            "score": 0,
            "details": f"""
❌ *تعذر الاتصال بـ RugCheck*

📋 *العقد:* `{token_address[:20]}...`

⚠️ *السبب:* {error_msg}

💡 *الحل:* جرب الفحص يدوياً على:
🔗 rugcheck.xyz/tokens/{token_address}

📌 بعد فتح الرابط، قارن النتائج بنفسك
"""
        }
    
    async def get_token_info(self, token_address):
        """معلومات إضافية (للاستخدام المستقبلي)"""
        return None