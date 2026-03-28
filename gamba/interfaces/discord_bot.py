"""Discord bot interface - slash commands + message forwarding."""

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


class DiscordBot(BaseInterface):
    """Discord bot using discord.py 2.0 with slash commands."""

    def __init__(self, bus: "MessageBus", config: "Config") -> None:
        super().__init__(bus, config)
        iface = config.interfaces.get("discord")
        if not iface or not iface.bot_token:
            raise ValueError("Discord bot token not configured")
        self.bot_token = iface.bot_token
        self._client = None
        self._channel = None

    async def start(self) -> None:
        try:
            import discord
            from discord import app_commands
        except ImportError:
            logger.error("discord.py not installed. Run: pip install discord.py")
            return

        intents = discord.Intents.default()
        intents.message_content = True

        client = discord.Client(intents=intents)
        tree = app_commands.CommandTree(client)
        self._client = client
        bot_self = self

        @tree.command(name="gamba", description="Send a prompt to GAMBA agents")
        async def gamba_cmd(interaction: discord.Interaction, prompt: str):
            await interaction.response.defer()
            bot_self._channel = interaction.channel

            response_event = asyncio.Event()
            response_text = ""

            async def capture_response(event: Event):
                nonlocal response_text
                response_text = event.data.get("response", "")
                response_event.set()

            unsub = bot_self.bus.subscribe(EventType.ORCHESTRATOR_RESPONSE, capture_response)

            await bot_self.send_user_input(prompt, source="discord")

            try:
                await asyncio.wait_for(response_event.wait(), timeout=120)
            except asyncio.TimeoutError:
                response_text = "Timed out waiting for response."
            finally:
                unsub()

            # Discord has 2000 char limit
            if len(response_text) > 1900:
                response_text = response_text[:1900] + "\n...(truncated)"
            await interaction.followup.send(response_text or "No response.")

        @tree.command(name="agents", description="List available GAMBA agents")
        async def agents_cmd(interaction: discord.Interaction):
            await interaction.response.send_message(
                "Agents are configured in `agents/*.yaml`.\n"
                "Use `/gamba <prompt>` to interact."
            )

        @client.event
        async def on_ready():
            logger.info(f"Discord bot connected as {client.user}")
            await tree.sync()
            logger.info("Slash commands synced")

        @client.event
        async def on_message(message):
            if message.author == client.user:
                return
            # Only respond if bot is mentioned
            if client.user in message.mentions:
                text = message.content.replace(f"<@{client.user.id}>", "").strip()
                if text:
                    bot_self._channel = message.channel
                    await bot_self.send_user_input(text, source="discord")

        logger.info("Starting Discord bot...")
        await client.start(self.bot_token)

    async def on_response(self, event: Event) -> None:
        response = event.data.get("response", "")
        if self._channel and response:
            try:
                if len(response) > 1900:
                    response = response[:1900] + "\n...(truncated)"
                await self._channel.send(response)
            except Exception as e:
                logger.error(f"Discord send error: {e}")

    async def on_agent_step(self, event: Event) -> None:
        # Don't flood Discord with step events
        pass

    async def on_agent_message(self, event: Event) -> None:
        target = event.data.get("target", "")
        msg = event.data.get("message", "")
        if self._channel:
            try:
                await self._channel.send(f"*{event.source} -> {target}:* {msg[:500]}")
            except Exception:
                pass

    async def stop(self) -> None:
        if self._client:
            await self._client.close()
