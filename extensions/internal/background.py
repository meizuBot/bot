import asyncio
from collections import Counter
from json import dumps
from logging import getLogger

import discord
from discord.ext import commands, tasks

import core
from utils.decos import wait_until_prepped

__all__ = ("setup",)

log = getLogger(__name__)


class BackgroundEvents(commands.Cog):
    def __init__(self, bot: core.CustomBot):
        self.bot = bot
        self._lock = asyncio.Lock(loop=self.bot.loop)

        self._command_cache = []
        self._socket_cache = Counter()
        self._nicknames_cache = []
        self._usernames_cache = []

        self.bulk_insert.start()

    def cog_unload(self):
        self.bulk_insert.stop()

    @tasks.loop(seconds=10)
    @wait_until_prepped()
    async def bulk_insert(self):
        if self.bot.is_closed():
            return
        async with self.bot.pool.acquire() as conn:
            if self._command_cache:
                async with self._lock:
                    query = """
                        INSERT INTO
                            stats.commands (guild, channel, author, used, prefix, command, failed)
                        SELECT x.guild, x.channel, x.author, x.used, x.prefix, x.command, x.failed
                            FROM JSONB_TO_RECORDSET($1::JSONB) AS
                            x(
                                    guild BIGINT,
                                    channel BIGINT,
                                    author BIGINT,
                                    used TIMESTAMP,
                                    prefix TEXT,
                                    command TEXT,
                                    failed BOOLEAN
                            )
                            """
                    await conn.execute(query, dumps(self._command_cache))
                    self._command_cache.clear()

            if self._nicknames_cache:
                async with self._lock:
                    query = """
                        INSERT INTO
                            users.nicknames (guild, member, nickname)
                        SELECT x.guild, x.member, x.nickname
                        FROM JSONB_TO_RECORDSET($1::JSONB)
                        AS x(guild BIGINT, member BIGINT, nickname TEXT)
                        """
                    await conn.execute(query, dumps(self._nicknames_cache))
                    self._nicknames_cache.clear()

            if self._usernames_cache:
                async with self._lock:
                    query = """
                        INSERT INTO
                            users.usernames (snowflake, username)
                        SELECT x.snowflake, x.username
                        FROM JSONB_TO_RECORDSET($1::JSONB)
                        AS x(snowflake BIGINT, username TEXT)
                        """
                    await conn.execute(query, dumps(self._usernames_cache))
                    self._usernames_cache.clear()

            if self._socket_cache:
                async with self._lock:
                    items = [(name, count) for name, count in self._socket_cache.most_common()]
                    query = """
                        INSERT INTO 
                            stats.socket
                        VALUES ($1, $2)
                        ON CONFLICT (name)
                        DO UPDATE SET 
                            count = socket.count + $2
                        """
                    await conn.executemany(query, items)
                    self._socket_cache.clear()

    @commands.Cog.listener()
    async def on_command_completion(self, ctx: core.CustomContext):
        if ctx.command is None:
            return

        self.bot.extra.command_stats[ctx.command.qualified_name] += 1
        async with self._lock:
            self._command_cache.append(
                {
                    "guild": getattr(ctx.guild, "id", None),
                    "channel": ctx.channel.id,
                    "author": ctx.author.id,
                    "used": ctx.message.created_at.isoformat(),
                    "prefix": ctx.clean_prefix,
                    "command": ctx.command.qualified_name,
                    "failed": ctx.command_failed,
                }
            )

    @commands.Cog.listener()
    async def on_socket_response(self, data):
        if event := data.get("t"):
            self.bot.extra.socket_stats[event] += 1

            self._socket_cache[event] += 1

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.display_name != after.display_name and after.nick is not None:
            async with self._lock:
                self._nicknames_cache.append(
                    {"guild": after.guild.id, "member": after.id, "nickname": after.nick}
                )

    @commands.Cog.listener()
    async def on_user_update(self, before: discord.User, after: discord.User):
        if before.name != after.name:
            async with self._lock:
                self._usernames_cache.append({"snowflake": after.id, "username": after.name})


def setup(bot: core.CustomBot):
    bot.add_cog(BackgroundEvents(bot))
