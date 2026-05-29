import asyncio
import logging
import aiohttp
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8715945694:AAEsv5kOk0ZdYFDNRZlO7qTKbdpOEAbEuPg"
DEFAULT_DELAY = 200

active_tasks: dict[str, asyncio.Task] = {}
delay_seconds: int = DEFAULT_DELAY
ping_stats: dict[str, dict] = {}


async def ping_loop(url: str, chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    global delay_seconds
    logger.info(f"[START] Bắt đầu treo: {url}")

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                start = datetime.now()
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    elapsed = (datetime.now() - start).total_seconds()
                    status = resp.status
                    ping_stats[url] = {
                        "count": ping_stats.get(url, {}).get("count", 0) + 1,
                        "last_ping": datetime.now().strftime("%H:%M:%S %d/%m/%Y"),
                        "status": status,
                        "ms": round(elapsed * 1000),
                    }
                    logger.info(f"[PING] {url} → {status} ({elapsed*1000:.0f}ms)")

            except asyncio.CancelledError:
                logger.info(f"[STOP] Đã hủy treo: {url}")
                return
            except Exception as e:
                ping_stats[url] = {
                    "count": ping_stats.get(url, {}).get("count", 0) + 1,
                    "last_ping": datetime.now().strftime("%H:%M:%S %d/%m/%Y"),
                    "status": "❌ Lỗi",
                    "ms": 0,
                }
                logger.warning(f"[ERR] {url} → {e}")

            try:
                await asyncio.sleep(delay_seconds)
            except asyncio.CancelledError:
                return

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 *Render Keep-Alive Bot*\n\n"
        "Các lệnh:\n"
        "`/auto <url>` — Bắt đầu treo link\n"
        "`/huyauto <url>` — Hủy treo link\n"
        "`/delay <giây>` — Chỉnh delay giữa mỗi request\n"
        "`/list` — Xem danh sách đang treo\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")
    
async def cmd_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Dùng: `/auto <url>`", parse_mode="Markdown")
        return

    url = context.args[0].strip()
    if not url.startswith("http"):
        url = "https://" + url

    if url in active_tasks and not active_tasks[url].done():
        await update.message.reply_text(f"⚠️ `{url}` đang được treo rồi!", parse_mode="Markdown")
        return

    task = asyncio.create_task(
        ping_loop(url, update.effective_chat.id, context)
    )
    active_tasks[url] = task
    ping_stats[url] = {"count": 0, "last_ping": "Chưa ping", "status": "⏳", "ms": 0}

    await update.message.reply_text(
        f"✅ *Đã bắt đầu treo:*\n`{url}`\n⏱ Delay: `{delay_seconds}s`",
        parse_mode="Markdown"
    )



async def cmd_huyauto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Dùng: `/huyauto <url>`", parse_mode="Markdown")
        return

    url = context.args[0].strip()
    if not url.startswith("http"):
        url = "https://" + url

    if url not in active_tasks or active_tasks[url].done():
        await update.message.reply_text(f"❌ Không tìm thấy task cho `{url}`", parse_mode="Markdown")
        return

    active_tasks[url].cancel()
    del active_tasks[url]
    ping_stats.pop(url, None)

    await update.message.reply_text(
        f"🛑 *Đã hủy treo:*\n`{url}`",
        parse_mode="Markdown"
    )


async def cmd_delay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global delay_seconds

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(
            f"⚠️ Dùng: `/delay <giây>`\nDelay hiện tại: `{delay_seconds}s`",
            parse_mode="Markdown"
        )
        return

    new_delay = int(context.args[0])
    if new_delay < 10:
        await update.message.reply_text("⚠️ Delay tối thiểu là `10s` để tránh spam.", parse_mode="Markdown")
        return

    delay_seconds = new_delay
    await update.message.reply_text(
        f"✅ Đã đổi delay thành `{delay_seconds}s`\n"
        f"_(Áp dụng cho các vòng tiếp theo của tất cả task)_",
        parse_mode="Markdown"
    )



async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    running = {url: t for url, t in active_tasks.items() if not t.done()}

    if not running:
        await update.message.reply_text("📭 Không có link nào đang được treo.")
        return

    lines = [f"📋 *Danh sách đang treo* ({len(running)}) — Delay: `{delay_seconds}s`\n"]
    for i, url in enumerate(running, 1):
        stats = ping_stats.get(url, {})
        status = stats.get("status", "?")
        count = stats.get("count", 0)
        last = stats.get("last_ping", "Chưa ping")
        ms = stats.get("ms", 0)
        lines.append(
            f"*{i}.* `{url}`\n"
            f"   └ Status: `{status}` | Ping: `{count}` lần | `{ms}ms`\n"
            f"   └ Lần cuối: `{last}`"
        )

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("auto", cmd_auto))
    app.add_handler(CommandHandler("huyauto", cmd_huyauto))
    app.add_handler(CommandHandler("delay", cmd_delay))
    app.add_handler(CommandHandler("list", cmd_list))

    logger.info("Bot đang chạy...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
