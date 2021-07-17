from dataclasses import dataclass
from pathlib import Path

import discord
from discord.ext import commands

import core
from utils import codeblock

__all__ = ("setup",)


@dataclass
class LineCounter:
    files: int
    lines: int
    characters: int
    classes: int
    functions: int
    coroutines: int
    comments: int

    @classmethod
    def project(cls, path="./"):
        files = lines = characters = classes = functions = coroutines = comments = 0
        for f in Path(path).rglob("*.py"):
            if str(f).startswith("venv"):
                continue
            files += 1
            with f.open(encoding="utf-8") as of:
                _lines = of.readlines()
                lines += len(_lines)
                for l in _lines:
                    l = l.strip()
                    characters += len(l)
                    if l.startswith("class"):
                        classes += 1
                    if l.startswith("def"):
                        functions += 1
                    if l.startswith("async def"):
                        coroutines += 1
                    if "#" in l:
                        comments += 1

        return cls(
            files=files,
            lines=lines,
            characters=characters,
            classes=classes,
            functions=functions,
            coroutines=coroutines,
            comments=comments,
        )


class General(commands.Cog):
    """General commands, about the bot etc"""

    def __init__(self, bot: core.Bot):
        self.bot = bot
        self.emoji = "<a:pop_cat:854027957878390784>"

    async def send_socket_stats(self, ctx, stats, *, omit_minutes: bool = False) -> None:
        minutes = (discord.utils.utcnow() - self.bot.start_time).total_seconds() / 60
        total = 0
        lines = []

        for name, count in stats:
            total += count
            if not omit_minutes:
                lines.append(f"{name:<30}{count:<18}{round(count / minutes)} / minute\n")
            else:
                lines.append(f"{name:<30}{count:<18}\n")

        if not omit_minutes:
            msg = f"{''.join(lines)}\n{'TOTAL':<30}{total:<18}{round(total / minutes)} / minute"
        else:
            msg = f"{''.join(lines)}\n{'TOTAL':<30}{total:<18}"

        await ctx.send(codeblock(msg, lang="yaml"))

    @core.group(
        aliases=("socketstats", "socket_stats", "events"),
        returns="A chart showing socket stats of this bot.",
        invoke_without_command=True,
    )
    async def socket(self, ctx: core.Context):
        await self.send_socket_stats(ctx, self.bot.extra.socket_stats.most_common())

    @socket.command(name="total", aliases=("all",), returns="A table showing the total socket stats")
    async def socket_total(self, ctx: core.Context):
        raw = await self.bot.pool.fetch("SELECT name, count FROM stats.socket ORDER BY count DESC")
        stats = [(i["name"], i["count"]) for i in raw]
        await self.send_socket_stats(ctx, stats, omit_minutes=True)

    @core.command(returns="Things about the bot.")
    async def about(self, ctx: core.Context):
        embed = self.bot.embed(color=discord.Color.og_blurple())

        me = await self.bot.getch_user(self.bot.owner_id)
        embed.set_author(name=str(me))

        guilds = users = bots = text = voice = 0
        for guild in self.bot.guilds:
            guilds += 1
            if guild.unavailable is True:
                continue

            for user in guild.members:
                if user.bot is True:
                    bots += 1
                else:
                    users += 1

            for channel in guild.channels:
                if isinstance(channel, discord.TextChannel):
                    text += 1
                if isinstance(channel, discord.VoiceChannel):
                    voice += 1

        cmds = await self.bot.pool.fetchval("SELECT COUNT(*) FROM stats.commands")
        socket = await self.bot.pool.fetch("SELECT * FROM stats.socket")
        total = 0
        total_messages = 0
        for stat in socket:
            total += stat["count"]
            if stat["name"] == "MESSAGE_CREATE":
                total_messages = stat["count"]
        since_restart = sum(self.bot.extra.command_stats.values())

        links = (
            f'[Support Server](https://google.com "Join the support server!")\n'
            f'[Invite Link](https://google.com "Invite me to your server")\n'
            f'[Source Code](https://github.com/ppotatoo/bot-rewrite "View the source code for the bot.")'
        )

        fields = (
            ("Users", f"{(users + bots):,} total\n{users:,} humans\n{bots:,} robots", True),
            ("Channels", f"{(text + voice):,} total\n{text:,} text\n{voice:,} voice", True),
            ("Links", links, True),
            ("Guilds", f"{guilds:,}", True),
            ("Command Usage", f"{cmds:,} total\n{since_restart:,} since restart", True),
            ("Events", f"{total_messages:,} total messages seen\n{total:,} total socket events", True),
        )

        for title, desc, inline in fields:
            embed.add_field(name=title, value=desc, inline=inline)

        await ctx.send(embed=embed)

    @core.command(aliases=("codestats", "lines"), returns="Various code stats about me!")
    async def code_stats(self, ctx: core.Context):
        stats = LineCounter.project()
        await ctx.send(
            codeblock(
                text="\n".join(
                    (
                        f"Files: {stats.files:,}",
                        f"Lines: {stats.lines:,}",
                        f"Characters: {stats.characters:,}",
                        f"Classes: {stats.classes:,}",
                        f"Functions: {stats.functions:,}",
                        f"Coroutines: {stats.coroutines}",
                        f"Comments: {stats.comments:,}",
                    )
                ),
                lang="prolog",
            )
        )


def setup(bot: core.Bot):
    bot.add_cog(General(bot))
