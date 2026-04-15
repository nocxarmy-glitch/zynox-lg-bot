"""
LG Pay Telegram Bot — aiogram v3
Made by [@Misakaishere] & help by [@Rohan]

Features:
  - Whitelist-only access (3 authorized users)
  - /start greeting with command menu
  - Async step-by-step payout flow via LG Pay Deposit API
  - MD5 signature (ASCII-sorted, key-appended)
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

# ─────────────────────────────────────────────────
# Configuration — load from environment variables
# ─────────────────────────────────────────────────

BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

LGPAY_APP_ID: str = os.environ.get("LGPAY_APP_ID", "YOUR_APP_ID_HERE")
LGPAY_KEY: str = os.environ.get("LGPAY_KEY", "YOUR_SECRET_KEY_HERE")
# Use 'TEST' for sandbox payout, change to live trade_type when ready
LGPAY_TRADE_TYPE: str = os.environ.get("LGPAY_TRADE_TYPE", "TEST")

LGPAY_PAYOUT_URL = "https://www.lg-pay.com/api/deposit/create"

# ─────────────────────────────────────────────────
# Whitelist — Telegram numeric user IDs ONLY
# Replace placeholder values with real IDs.
# How to get your ID: message @userinfobot on Telegram.
# ─────────────────────────────────────────────────

WHITELIST_IDS: set[int] = {
    # @Forzahere  — replace with your numeric user ID
    123456789,
    # @Misakaishere — replace with partner 1 numeric user ID
    987654321,
    # @Derickcarder69 — replace with partner 2 numeric user ID
    111222333,
}

# ─────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────
# FSM States — payout collection flow
# ─────────────────────────────────────────────────

class PayoutStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_bank = State()
    waiting_for_account = State()
    waiting_for_amount = State()


# ─────────────────────────────────────────────────
# LG Pay Signature
# ─────────────────────────────────────────────────

def build_signature(params: dict[str, Any]) -> str:
    """
    Build LG Pay MD5 signature.

    Algorithm:
      1. Filter out empty-string values.
      2. Sort remaining keys by ASCII order.
      3. Join as query string: k=v&k=v
      4. Append &key=<SECRET_KEY>
      5. MD5 hex digest -> uppercase
    """
    filtered = {k: str(v) for k, v in params.items() if str(v) != ""}
    sorted_keys = sorted(filtered.keys())
    query_string = "&".join(f"{k}={filtered[k]}" for k in sorted_keys)
    sign_string = f"{query_string}&key={LGPAY_KEY}"
    logger.debug("Sign input: %s", sign_string)
    return hashlib.md5(sign_string.encode("utf-8")).hexdigest().upper()


# ─────────────────────────────────────────────────
# LG Pay Payout API
# ─────────────────────────────────────────────────

async def create_payout_order(
    beneficiary_name: str,
    bank_name: str,
    account_number: str,
    amount_inr: float,
) -> dict[str, Any]:
    """
    POST to LG Pay Deposit (payout) API.

    Returns the parsed JSON response dict from the gateway.
    Raises aiohttp.ClientError on network failures.

    Payload fields:
      app_id, trade_type, order_sn, money (paise / cents),
      name, bank_name, card, notify_url, sign
    """
    order_sn = f"PO{int(time.time() * 1000)}"
    money = int(amount_inr * 100)  # convert INR to paise (remove decimal)

    payload: dict[str, Any] = {
        "app_id": LGPAY_APP_ID,
        "trade_type": LGPAY_TRADE_TYPE,
        "order_sn": order_sn,
        "money": money,
        "name": beneficiary_name,
        "bank_name": bank_name,
        "card": account_number,
        "notify_url": "",  # Set to your callback URL if needed
    }

    # Sign BEFORE submitting — exclude empty notify_url
    payload["sign"] = build_signature(payload)

    logger.info(
        "Payout request | order=%s | amount=%.2f INR | beneficiary=%s",
        order_sn, amount_inr, beneficiary_name,
    )

    async with aiohttp.ClientSession() as session:
        async with session.post(
            LGPAY_PAYOUT_URL,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            json_data: dict[str, Any] = await resp.json(content_type=None)
            logger.info("LG Pay response: %s", json_data)
            return json_data


# ─────────────────────────────────────────────────
# Whitelist helper
# ─────────────────────────────────────────────────

def is_whitelisted(user_id: int) -> bool:
    return user_id in WHITELIST_IDS


# ─────────────────────────────────────────────────
# Handlers
# ─────────────────────────────────────────────────

async def handle_start(message: Message) -> None:
    """Handle /start — premium aesthetic greeting with command menu (MarkdownV2)."""
    if not is_whitelisted(message.from_user.id):
        return  # Silently ignore

    # Prefer first name for a natural greeting; fall back to username or 'there'
    display_name = (
        message.from_user.first_name
        or (f"@{message.from_user.username}" if message.from_user.username else "there")
    )

    # Escape any MarkdownV2 special chars that might appear in the display name
    _special = r"\`*_{}[]()#+-.!|>"
    safe_name = "".join(f"\\{c}" if c in _special else c for c in display_name)

    divider = "━" * 26  # thick horizontal rule

    # ── PLACEHOLDERS ──────────────────────────────────────────────────────────
    # Replace the username strings below with your actual Telegram usernames.
    # Example: MAKER_USERNAME = "YourRealUsername"
    MAKER_USERNAME = "Misakaishere"    # ← your username (without @)
    PARTNER_USERNAME = "Rohan"         # ← partner's username (without @)
    MERCHANT_ID = "YD5038"            # ← your LG Pay merchant ID
    # ─────────────────────────────────────────────────────────────────────────

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
        "🔹 /help — Show this help message\n"
        f"`{divider}`\n"
        f"⚡ *Made by:* [@{MAKER_USERNAME}](https://t.me/{MAKER_USERNAME})\n"
        f"🤝 *Helped by:* [@{PARTNER_USERNAME}](https://t.me/{PARTNER_USERNAME})\n"
        f"`{divider}`\n"
        f"💳 [LG Payment Gateway](https://www\.lg\-pay\.com) · Merchant: ||{MERCHANT_ID}||"
    )

    await message.answer(text, parse_mode="MarkdownV2", disable_web_page_preview=True)


async def handle_help(message: Message) -> None:
    """Handle /help — delegates to /start handler."""
    if not is_whitelisted(message.from_user.id):
        return
    await handle_start(message)


async def handle_payout_start(message: Message, state: FSMContext) -> None:
    """Handle /payout — step 1: request beneficiary name."""
    if not is_whitelisted(message.from_user.id):
        return

    await state.clear()
    await state.set_state(PayoutStates.waiting_for_name)

    await message.answer(
        "\U0001f4b8 <b>New Payout Request</b>\n\n"
        "\U0001f4dd <b>Step 1 of 4</b>\n\n"
        "Enter the <b>Beneficiary Name</b>:\n"
        "<i>(Full name exactly as on the bank account)</i>",
        parse_mode="HTML",
    )


async def handle_collect_name(message: Message, state: FSMContext) -> None:
    """FSM step 1 — collect beneficiary name."""
    if not is_whitelisted(message.from_user.id):
        return

    name = message.text.strip()
    if len(name) < 2:
        await message.answer("\u274c Name is too short. Please enter a valid full name:")
        return

    await state.update_data(beneficiary_name=name)
    await state.set_state(PayoutStates.waiting_for_bank)

    await message.answer(
        f"\u2705 Name: <b>{name}</b>\n\n"
        "\U0001f4dd <b>Step 2 of 4</b>\n\n"
        "Enter the <b>Bank Name</b>:\n"
        "<i>(e.g. SBI, HDFC, ICICI, Axis)</i>",
        parse_mode="HTML",
    )


async def handle_collect_bank(message: Message, state: FSMContext) -> None:
    """FSM step 2 — collect bank name."""
    if not is_whitelisted(message.from_user.id):
        return

    bank = message.text.strip()
    if len(bank) < 2:
        await message.answer("\u274c Bank name is too short. Please try again:")
        return

    await state.update_data(bank_name=bank)
    await state.set_state(PayoutStates.waiting_for_account)

    await message.answer(
        f"\u2705 Bank: <b>{bank}</b>\n\n"
        "\U0001f4dd <b>Step 3 of 4</b>\n\n"
        "Enter the <b>Account / Card Number</b>:\n"
        "<i>(Bank account number or card number)</i>",
        parse_mode="HTML",
    )


async def handle_collect_account(message: Message, state: FSMContext) -> None:
    """FSM step 3 — collect account/card number."""
    if not is_whitelisted(message.from_user.id):
        return

    account = message.text.strip()
    if len(account) < 4:
        await message.answer("\u274c Account number seems too short. Please enter a valid number:")
        return

    masked = "*" * (len(account) - 4) + account[-4:]
    await state.update_data(account_number=account)
    await state.set_state(PayoutStates.waiting_for_amount)

    await message.answer(
        f"\u2705 Account: <code>{masked}</code>\n\n"
        "\U0001f4dd <b>Step 4 of 4</b>\n\n"
        "Enter the <b>Payout Amount (INR \u20b9)</b>:\n"
        "<i>(Numbers only, e.g. 5000)</i>",
        parse_mode="HTML",
    )


async def handle_collect_amount(message: Message, state: FSMContext) -> None:
    """FSM step 4 — collect amount, submit to LG Pay, show result."""
    if not is_whitelisted(message.from_user.id):
        return

    raw = message.text.strip().replace(",", "")

    try:
        amount = float(raw)
    except ValueError:
        await message.answer("\u274c Invalid amount. Please enter a number (e.g. 5000):")
        return

    if amount <= 0:
        await message.answer("\u274c Amount must be greater than \u20b90. Please enter a valid amount:")
        return

    if amount < 100:
        await message.answer("\u274c Minimum payout is \u20b9100. Please enter a higher amount:")
        return

    data = await state.get_data()
    await state.clear()

    beneficiary_name: str = data["beneficiary_name"]
    bank_name: str = data["bank_name"]
    account_number: str = data["account_number"]
    masked_acct = "*" * (len(account_number) - 4) + account_number[-4:]

    summary = (
        "\U0001f4cb <b>Payout Summary</b>\n"
        "\u2501" * 22 + "\n"
        f"\U0001f464 <b>Name:</b>    {beneficiary_name}\n"
        f"\U0001f3e6 <b>Bank:</b>    {bank_name}\n"
        f"\U0001f4b3 <b>Account:</b> <code>{masked_acct}</code>\n"
        f"\U0001f4b0 <b>Amount:</b>  \u20b9{amount:,.2f}\n"
        "\u2501" * 22 + "\n"
        "\u23f3 Submitting payout request..."
    )
    status_msg = await message.answer(summary, parse_mode="HTML")

    try:
        response = await create_payout_order(
            beneficiary_name=beneficiary_name,
            bank_name=bank_name,
            account_number=account_number,
            amount_inr=amount,
        )

        if response.get("status") == 1:
            data_block = response.get("data") or {}
            order_sn = data_block.get("order_sn", "N/A")
            trade_no = data_block.get("trade_no", "N/A")

            success_text = (
                "\u2705 <b>Payout Submitted Successfully!</b>\n"
                "\u2501" * 22 + "\n"
                f"\U0001f464 <b>Beneficiary:</b> {beneficiary_name}\n"
                f"\U0001f3e6 <b>Bank:</b>        {bank_name}\n"
                f"\U0001f4b3 <b>Account:</b>     <code>{masked_acct}</code>\n"
                f"\U0001f4b0 <b>Amount:</b>      \u20b9{amount:,.2f}\n"
                f"\U0001f516 <b>Order ID:</b>   <code>{order_sn}</code>\n"
                f"\U0001f3e7 <b>Trade No:</b>   <code>{trade_no}</code>\n"
                "\u2501" * 22 + "\n"
                "\u23f0 Payout is being processed. You will be notified upon completion."
            )
            await status_msg.edit_text(success_text, parse_mode="HTML")

        else:
            error_msg = response.get("msg", "Unknown error from LG Pay")
            error_code = response.get("status", "?")

            fail_text = (
                "\u274c <b>Payout Failed</b>\n"
                "\u2501" * 22 + "\n"
                f"\u26a0\ufe0f <b>Error:</b>  {error_msg}\n"
                f"\U0001f4df <b>Code:</b>   <code>{error_code}</code>\n"
                "\u2501" * 22 + "\n"
                "Please verify the details and try again with /payout"
            )
            await status_msg.edit_text(fail_text, parse_mode="HTML")

    except aiohttp.ClientError as exc:
        logger.exception("Network error during payout: %s", exc)
        await status_msg.edit_text(
            "\u274c <b>Network Error</b>\n\n"
            "Could not reach LG Pay servers. Please try again later.",
            parse_mode="HTML",
        )
    except Exception as exc:
        logger.exception("Unexpected error during payout: %s", exc)
        await status_msg.edit_text(
            "\u274c <b>Unexpected Error</b>\n\n"
            "Something went wrong. Please contact support.",
            parse_mode="HTML",
        )


async def handle_cancel(message: Message, state: FSMContext) -> None:
    """Handle /cancel — clear any active FSM state."""
    if not is_whitelisted(message.from_user.id):
        return

    current = await state.get_state()
    await state.clear()

    if current:
        await message.answer(
            "\u274c <b>Operation cancelled.</b>\n\nUse /payout to start a new request.",
            parse_mode="HTML",
        )
    else:
        await message.answer("\u2139\ufe0f No active operation to cancel.", parse_mode="HTML")


async def handle_unknown(message: Message, state: FSMContext) -> None:
    """
    Catch-all handler.
    Non-whitelisted users are silently ignored.
    Whitelisted users outside a flow get a hint.
    """
    if not is_whitelisted(message.from_user.id):
        return  # Silently drop

    current = await state.get_state()
    if not current:
        await message.answer(
            "\u2753 Unknown command.\n\nUse /help to see available commands.",
            parse_mode="HTML",
        )


# ─────────────────────────────────────────────────
# Bot startup
# ─────────────────────────────────────────────────
from aiohttp import web

async def health_check(request):
    """Render ko batane ke liye ki server zinda hai"""
    return web.Response(text="LG Pay Bot is running 24/7 on Render!")

async def main() -> None:
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    # ── Command handlers (top priority)
    dp.message.register(handle_start, CommandStart())
    dp.message.register(handle_help, Command("help"))
    dp.message.register(handle_cancel, Command("cancel"))    # works from any state
    dp.message.register(handle_cancel, Command("cancel")) 
    dp.message.register(handle_payout_start, Command("payout"))

    # ── FSM step handlers (ordered: name → bank → account → amount)
    # ── FSM step handlers
    dp.message.register(handle_collect_name, PayoutStates.waiting_for_name, F.text)
    dp.message.register(handle_collect_bank, PayoutStates.waiting_for_bank, F.text)
    dp.message.register(handle_collect_account, PayoutStates.waiting_for_account, F.text)
    dp.message.register(handle_collect_amount, PayoutStates.waiting_for_amount, F.text)

    # ── Catch-all (must be registered last)
    # ── Catch-all
    dp.message.register(handle_unknown)

    logger.info("LG Pay Bot starting (long-polling mode)")
    await dp.start_polling(bot)

    logger.info("Starting LG Pay Bot and Web Server...")
    
    # 1. Telegram Bot ko background mein start karein
    asyncio.create_task(dp.start_polling(bot))

    # 2. Render ke liye ek chhota sa Web Server start karein
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Render khud ek port number deta hai, hum use yahan dhoondh rahe hain
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    
    logger.info(f"Web server is live on port {port}")
    await site.start()

    # Program ko band hone se rokne ke liye
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
