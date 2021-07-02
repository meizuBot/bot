import asyncio
import logging
from datetime import datetime as dt, timedelta
from json import dumps, loads

import asyncpg
import discord
from discord.ext import commands

import core
from utils.time import human_timedelta, parse_time, utcnow

__all__ = ("setup",)

log = logging.getLogger(__name__)


class Reminders(commands.Cog):
    def __init__(self, bot: core.CustomBot):
        self.bot = bot
        self.emoji = "<a:pikawink:853236064991182909>"
        self.show_subcommands = True

        self._current_timer = None
        self._event = asyncio.Event(loop=self.bot.loop)

        self._task = self.bot.loop.create_task(self._reminder_dispatch())

    async def get_active_reminder(self, days: int = 10, *, connection=None):
        query = """
            SELECT * 
            FROM 
                events.timers
            WHERE
                expires < (CURRENT_DATE + $1::interval) 
            ORDER BY
                expires 
            LIMIT
                1
            """
        conn = connection or self.bot.pool

        ret = await conn.fetchrow(query, timedelta(days=days))
        return ret or None

    async def wait_for_reminders(self, *, days=10):
        async with self.bot.pool.acquire() as conn:
            reminder = await self.get_active_reminder(days, connection=conn)
            if reminder is not None:
                self._event.set()
                return reminder

            self._event.clear()

            self._current_timer = None

            await self._event.wait()

            return await self.get_active_reminder(days, connection=conn)

    async def call_timer(self, reminder):
        await self.bot.pool.execute("DELETE FROM events.timers WHERE id = $1", reminder["id"])
        reminder = dict(reminder)
        reminder["data"] = loads(reminder["data"])

        self.bot.dispatch(f"{reminder['event']}_complete", reminder)

    async def _reminder_dispatch(self):
        await self.bot.wait_until_ready()
        try:
            while not self.bot.is_closed():
                reminder = self._current_timer = await self.wait_for_reminders()

                if (expires := reminder["expires"]) >= (now := utcnow()):
                    to_sleep = (expires - now).total_seconds()
                    await asyncio.sleep(to_sleep)

                await self.call_timer(reminder)
        except asyncio.CancelledError:
            raise
        except (OSError, discord.ConnectionClosed, asyncpg.PostgresConnectionError):
            # re-run the loop
            self._task.cancel()
            self._task = self.bot.loop.create_task(self._reminder_dispatch())

    async def create_timer(self, event: str, created: dt, expires: dt, data: dict):
        query = """
            INSERT INTO
                events.timers (event, created, expires, data)
            VALUES 
                ($1, $2, $3, $4::JSONB)
            RETURNING * 
            """
        values = (event, created, expires, dumps(data))
        timer = await self.bot.pool.fetchrow(query, *values)

        delta = (expires - created).total_seconds()

        if delta <= (86400 * 10):
            self._event.set()

        if self._current_timer and expires < self._current_timer["expires"]:
            self._task.cancel()
            self._task = self.bot.loop.create_task(self._reminder_dispatch())

        return timer

    @core.command(
        examples=(
            "1w take out the trash",
            '"4 months and 2 days" william\'s birthday',
            "1week",
            "1week2days fix this code",
        ),
        params={
            "time": "The time when you want me to remind you for something.",
            "thing": "The thing you want me to remind you to do.",
        },
        returns="Confirmation that I have registered your reminder.",
    )
    async def remind(self, ctx: core.CustomContext, time: str, *, thing: str = "Nothing"):
        """A command to remind yourself of things
        Times are in UTC.
        """
        expires = parse_time(ctx, time)
        data = {
            "author": ctx.author.id,
            "channel": ctx.channel.id,
            "message": ctx.message.id,
            "reminder_content": thing,
        }

        await self.create_timer("reminder", ctx.message.created_at, expires, data)

        delta = human_timedelta(expires, source=ctx.message.created_at)
        await ctx.send(f"In {delta}: {thing}")

    @commands.Cog.listener()
    async def on_reminder_complete(self, reminder):
        data = reminder["data"]
        try:
            channel = self.bot.get_channel(data["channel"]) or (await self.bot.fetch_channel(data["channel"]))
        except discord.HTTPException:
            return

        delta = human_timedelta(reminder["created"])

        msg = f"<@{data['author']}>, {delta}: {data['reminder_content']}"
        msg += "\n\n" + f"<https://discord.com/channels/{channel.guild.id}/{channel.id}/{data['message']}>"

        try:
            await channel.send(msg)
        except discord.HTTPException:
            return


def setup(bot: core.CustomBot):
    bot.add_cog(Reminders(bot))
