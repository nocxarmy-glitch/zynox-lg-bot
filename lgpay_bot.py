"""
LG Pay Telegram Bot — aiogram v3
Made by [@Misakaishere] & help by [@Rohan]
"""

import asyncio
import hashlib
import logging
import os
import time
from typing import Any

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message
from aiohttp import web  # Railway/Render ke liye zaroori hai

# ─────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────

BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
LGPAY_APP_ID: str = os.environ.get("LGPAY_APP_ID", "YOUR_APP_ID_HERE")
LGPAY_KEY: str = os.environ.get("LGPAY_KEY", "YOUR_SECRET_KEY_HERE")
LGPAY_TRADE_TYPE: str = os.environ.get("LGPAY_TRADE_TYPE", "TEST")

LGPAY_PAYOUT_URL = "https://www.lg-pay.com/api/deposit/create"
LGPAY_PAYIN_URL = "https://www.lg-pay.com/api/order/create"
LGPAY_PAYIN_TRADE_TYPE: str = os.environ.get("LGPAY_PAYIN_TRADE_TYPE", "INRUPI")

# ─────────────────────────────────────────────────
# Whitelist — Asli IDs (Screenshot 128-129 ke hisab se)
# ─────────────────────────────────────────────────

WHITELIST_IDS: set[int] = {
    6554884930,  # Aapki ID
    1005640892,  # Misaka ID
    1005640892,  # rosan
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────
# FSM States
# ─────────────────────────────────────────────────

class PayoutStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_bank = State()
    waiting_for_account = State()
    waiting_for_amount = State()

# ─────────────────────────────────────────────────
# LG Pay Functions (Signature & API)
# ─────────────────────────────────────────────────

def build_signature(params: dict[str, Any]) -> str:
    filtered = {k: str(v) for k, v in params.items() if str(v) != ""}
    sorted_keys = sorted(filtered.keys())
    query_string = "&".join(f"{k}={filtered[k]}" for k in sorted_keys)
    sign_string = f"{query_string}&key={LGPAY_KEY}"
    return hashlib.md5(sign_string.encode("utf-8")).hexdigest().upper()

async def create_payout_order(beneficiary_name: str, bank_name: str, account_number: str, amount_inr: float) -> dict[str, Any]:
    order_sn = f"PO{int(time.time() * 1000)}"
    money = int(amount_inr * 100)
    payload = {
        "app_id": LGPAY_APP_ID,
        "trade_type": LGPAY_TRADE_TYPE,
        "order_sn": order_sn,
        "money": money,
        "name": beneficiary_name,
        "bank_name": bank_name,
        "card": account_number,
        "notify_url": "",
    }
    payload["sign"] = build_signature(payload)
    async with aiohttp.ClientSession() as session:
        async with session.post(LGPAY_PAYOUT_URL, data=payload) as resp:
            return await resp.json(content_type=None)

async def create_payin_order(amount_inr: float, chat_id: int) -> dict[str, Any]:
    order_sn = f"TG{chat_id}_{int(time.time() * 1000)}"
    money = int(amount_inr * 100)
    payload = {
        "app_id": LGPAY_APP_ID,
        "trade_type": LGPAY_PAYIN_TRADE_TYPE,
        "order_sn": order_sn,
        "money": money,
        "notify_url": "",
        "ip": "0.0.0.0",
        "remark": f"TG:{chat_id}",
    }
    payload["sign"] = build_signature(payload)
    async with aiohttp.ClientSession() as session:
        async with session.post(LGPAY_PAYIN_URL, data=payload) as resp:
            return await resp.json(content_type=None)

def is_whitelisted(user_id: int) -> bool:
    return user_id in WHITELIST_IDS

# ─────────────────────────────────────────────────
# Handlers (GREETING MESSAGE IS HERE)
# ─────────────────────────────────────────────────

async def handle_start(message: Message) -> None:
    if not is_whitelisted(message.from_user.id): return
    display_name = message.from_user.first_name or "User"
    _special = r"\`*_{}[]()#+-.!|>"
    safe_name = "".join(f"\\{c}" if c in _special else c for c in display_name)
    divider = "━" * 26
    
    MAKER_USERNAME = "Misakaishere"
    PARTNER_USERNAME = "Rohan"
    MERCHANT_ID = "YD5038"

    text = (
        f"👋 *Welcome, {safe_name}\!*\n"
        f"`{divider}`\n"
        "🤖 *Zynox LG PAY BOT*\n"
        "_Instant payment processing via LG Payment Gateway\._\n"
        f"`{divider}`\n"
        "📋 *Available Commands:*\n\n"
        "🔹 /pay — Create a payment link\n"
        "    _e\.g\. /pay 500_\n\n"
        "🔹 /payout — Initiate a payout\n\n"
        "🔹 /cancel — Cancel current operation\n\n"
        "🔹 /help — Show this help message\n"
        f"`{divider}`\n"
        f"⚡ *Made by:* [@{MAKER_USERNAME}](https://t.me/{MAKER_USERNAME})\n"
        f"🤝 *Helped by:* [@{PARTNER_USERNAME}](https://t.me/{PARTNER_USERNAME})\n"
        f"`{divider}`\n"
        f"💳 [LG Payment Gateway](https://www\.lg\-pay\.com) · Merchant: ||{MERCHANT_ID}||"
    )
    await message.answer(text, parse_mode="MarkdownV2", disable_web_page_preview=True)

async def handle_pay(message: Message, state: FSMContext):
    if not is_whitelisted(message.from_user.id): return
    await state.clear()
    
    parts = message.text.strip().replace("/pay", "").strip().split()
    if not parts:
        await message.answer("❌ *Usage:* `/pay 500`", parse_mode="MarkdownV2")
        return
        
    try:
        amount = float(parts[0].replace(",", ""))
        if amount < 1: raise ValueError
    except:
        await message.answer("❌ *Invalid amount\!* Please enter a number\.", parse_mode="MarkdownV2")
        return

    # Loading message
    msg = await message.answer("⏳ *Generating secure payment link\.\.\.*", parse_mode="MarkdownV2")
    
    res = await create_payin_order(amount, message.from_user.id)
    
    if res.get("status") == 1:
        url = res['data']['pay_url']
        divider = "━" * 24
        
        # Premium Aesthetic Message
        success_text = (
            f"✅ *Payment Link Ready*\n"
            f"`{divider}`\n"
            f"💰 *Amount:* ₹{amount:,.2f}\n"
            f"🔗 *Link:* [Click here to Pay]({url})\n"
            f"`{divider}`\n"
            f"⚡ _Powered by LG Payment Gateway_"
        )
        await msg.edit_text(success_text, parse_mode="MarkdownV2", disable_web_page_preview=True)
    else:
        error_msg = res.get("msg", "Unknown error")
        await msg.edit_text(f"❌ *Failed:* {error_msg}", parse_mode="MarkdownV2")

# (Note: Payout handlers collect_name, bank, etc. exactly as in dev code)
async def handle_payout_start(message, state):
    if not is_whitelisted(message.from_user.id): return
    await state.clear()
    await state.set_state(PayoutStates.waiting_for_name)
    await message.answer("💸 <b>Step 1:</b> Enter Beneficiary Name:", parse_mode="HTML")

async def handle_collect_name(message, state):
    await state.update_data(beneficiary_name=message.text)
    await state.set_state(PayoutStates.waiting_for_bank)
    await message.answer("🏦 <b>Step 2:</b> Enter Bank Name:", parse_mode="HTML")

async def handle_collect_bank(message, state):
    await state.update_data(bank_name=message.text)
    await state.set_state(PayoutStates.waiting_for_account)
    await message.answer("💳 <b>Step 3:</b> Enter Account Number:", parse_mode="HTML")

async def handle_collect_account(message, state):
    await state.update_data(account_number=message.text)
    await state.set_state(PayoutStates.waiting_for_amount)
    await message.answer("💰 <b>Step 4:</b> Enter Amount:", parse_mode="HTML")

async def handle_collect_amount(message, state):
    try:
        amount = float(message.text)
        data = await state.get_data()
        await state.clear()
        await message.answer("⏳ Submitting payout...")
        res = await create_payout_order(data['beneficiary_name'], data['bank_name'], data['account_number'], amount)
        if res.get("status") == 1:
            await message.answer("✅ Payout Success!")
        else:
            await message.answer(f"❌ Failed: {res.get('msg')}")
    except:
        await message.answer("❌ Invalid amount.")

async def handle_cancel(message, state):
    await state.clear()
    await message.answer("❌ Operation cancelled.")

# ─────────────────────────────────────────────────
# Main Setup (With Health Check for Railway)
# ─────────────────────────────────────────────────

async def health_check(request):
    return web.Response(text="Bot is running!")

async def main() -> None:
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.register(handle_start, CommandStart())
    dp.message.register(handle_pay, Command("pay"))
    dp.message.register(handle_payout_start, Command("payout"))
    dp.message.register(handle_cancel, Command("cancel"))
    
    dp.message.register(handle_collect_name, PayoutStates.waiting_for_name, F.text)
    dp.message.register(handle_collect_bank, PayoutStates.waiting_for_bank, F.text)
    dp.message.register(handle_collect_account, PayoutStates.waiting_for_account, F.text)
    dp.message.register(handle_collect_amount, PayoutStates.waiting_for_amount, F.text)

    # Web Server Startup
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

    logger.info("Bot and Health Check Live!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
