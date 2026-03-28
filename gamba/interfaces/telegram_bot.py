"""Telegram bot interface - long-polling, Termux-friendly."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from gamba.interfaces.base import BaseInterface
from gamba.core.message_bus import EventType, Event

if TYPE_CHECKING:
    from gamba.core.message_bus import MessageBus
    from gamba.state.schemas import Config

logger = logging.getLogger(__name__)


class TelegramBot(BaseInterface):
    """Telegram bot using long-polling (no webhook needed - works on Termux)."""

    def __init__(self, bus: "MessageBus", config: "Config") -> None:
        super().__init__(bus, config)
        iface = config.interfaces.get("telegram")
        if not iface or not iface.bot_token:
            raise ValueError("Telegram bot token not configured")
        self.bot_token = iface.bot_token
        self._app = None
        self._chat_ids: set[int] = set()

    async def start(self) -> None:
        try:
            from telegram import Update
            from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
        except ImportError:
            logger.error("python-telegram-bot not installed. Run: pip install python-telegram-bot")
            return

        self._app = (
            ApplicationBuilder()
            .token(self.bot_token)
            .build()
        )

        # Handlers
        self._app.add_handler(CommandHandler("start", self._cmd_start))
        self._app.add_handler(CommandHandler("agents", self._cmd_agents))
        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_text))

        logger.info("Starting Telegram bot (long-polling)...")
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling(drop_pending_updates=True)

        # Keep running
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            pass
        finally:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()

    async def _cmd_start(self, update, context) -> None:
        chat_id = update.effective_chat.id
        self._chat_ids.add(chat_id)
        await update.message.reply_text(
            "GAMBA connected.\n"
            "Send me any message and I'll route it to my agents.\n"
            "/agents - list available agents"
        )

    async def _cmd_agents(self, update, context) -> None:
        # We need access to orchestrator agents - get from bus
        await update.message.reply_text(
            "Available agents are configured in agents/*.yaml\n"
            "Send any message to interact."
        )

    async def _on_text(self, update, context) -> None:
        chat_id = update.effective_chat.id
        self._chat_ids.add(chat_id)
        text = update.message.text

        # Store context for reply
        self._pending_chat_id = chat_id
        self._pending_update = update

        await self.send_user_input(text, source=f"telegram:{chat_id}")

    async def on_response(self, event: Event) -> None:
        response = event.data.get("response", "")
        if not response:
            return
        await self._send_to_all(f"{response}")

    async def on_agent_step(self, event: Event) -> None:
        source = event.source
        action = event.data.get("action", "")
        if action:
            await self._send_to_all(f"[{source}] {action}")

    async def on_agent_message(self, event: Event) -> None:
        target = event.data.get("target", "")
        msg = event.data.get("message", "")
        await self._send_to_all(f"{event.source} -> {target}: {msg[:200]}")

    async def _send_to_all(self, text: str) -> None:
        """Send a message to all known chat IDs."""
        if not self._app or not self._chat_ids:
            return
        for chat_id in self._chat_ids:
            try:
                # Telegram has a 4096 char limit
                for i in range(0, len(text), 4000):
                    await self._app.bot.send_message(
                        chat_id=chat_id,
                        text=text[i:i+4000],
                        parse_mode=None,
                    )
            except Exception as e:
                logger.error(f"Failed to send to {chat_id}: {e}")

    async def stop(self) -> None:
        if self._app:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
