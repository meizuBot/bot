import logging
from os import listdir
from typing import Tuple

import discord
from discord.ext import commands

import core

__all__ = ("setup",)

log = logging.getLogger(__name__)


fmt = "You've {plural} {user} {amount + 1} times! They've been {plural} a total of {total + 1} times."


class Interactions(commands.Cog):
    def __init__(self, bot: core.CustomBot):
        self.bot = bot
        self.emoji = "<:mitsuri_pleading:853237551262466108>"

    async def construct_embed(self, method: str, plural: str, initiator: discord.Member, receiver: discord.User) -> discord.Embed:
        embed = self.bot.embed()

        url = "https://api.waifu.pics/sfw/" + method
        async with self.bot.session.get(url) as resp:
            if resp.ok:
                data = await resp.json()
                if url := data.get("url") is not None:
                    embed.set_image(url=url)

            if embed.image is None:
                log.warning(f"Embed image failed to load. Method: {method}, Code: {resp.status}")
                embed.description = "Oops, something went wrong."


        embed.set_footer(fmt.format_map(await self.get_totals(method, initiator, receiver)))

        return embed

    async def get_totals(self, method: str, initiator: discord.User, receiver: discord.User) -> dict:
        query = """
            SELECT
                users.interactions.count AS amount, users.totals.count AS total
            FROM
               users.interactions
            INNER JOIN
                users.totals
                ON users.interactions.receiver = users.totals.snowflake
            WHERE
                initiator = $1 AND receiver = $2 AND users.interactions.method = $3 AND users.totals.method = $3
            """
        data = dict(await self.bot.pool.fetchrow(query, initiator.id, receiver.id, method))
        data.update({"user": receiver.display_name})
        return data

    async def update(self, method: str, initiator: discord.User, receiver: discord.User):
        query = """
            WITH total_update AS (
                INSERT INTO users.totals (method, snowflake) VALUES ($1, $3)
                ON CONFLICT (method, snowflake) DO UPDATE SET count = totals.count + 1
            )
            INSERT INTO users.interactions (method, initiator, receiver) VALUES ($1, $2, $3)
            ON CONFLICT (method, initiator, receiver) DO UPDATE
            SET count = interactions.count + 1
            """
        await self.bot.pool.execute(query, method, initiator.id, receiver.id)

    def invoke_check(self, verb: str, plural: str, initiator: discord.User, receiver: discord.User):
        if initiator == receiver:
            raise commands.BadArgument(f"You can't {verb} yourself!")
        if receiver.bot is True and receiver.id != self.bot.user.id:
            raise commands.BadArgument(f"Bots can't be {plural}!")

    async def run_interaction(self, ctx: core.Context, verb: str, plural: str, initiator: discord.Member, receiver: discord.User):
        self.invoke_check(verb, plural, initiator, receiver)

        await ctx.send(embed=await self.construct_embed())

        await self.update(verb, initiator, receiver)


    @core.command(
        examples=("@ppotatoo",),
        params={"user": "The user you want to bonk 🔨"},
        returns="You bonking a user",
    )
    async def bonk(self, ctx: core.CustomContext, user: discord.User):
        """Bonk!
        You can view how many times you have bonked the user, and how many times they have been bonked in total.
        """
        await self.run_interaction(ctx, "bonk", "bonked", ctx.author, user)

    @core.command(
        examples=("@ppotatoo",),
        params={"user": "The user you want to bite 😳"},
        returns="You biting a user",
    )
    async def bite(self, ctx: core.CustomContext, user: discord.User):
        """A command that lets you bite another user!
        You can view how many times you've bitten this user, and how many times they've been bitten
        """
        await self.run_interaction(ctx, "bite", "bitten", ctx.author, user)

    @core.command(
        examples=("@ppotatoo",),
        params={"user": "The user you want to cuddle"},
        returns="A cuddle between friends ❤️",
    )
    async def cuddle(self, ctx: core.CustomContext, user: discord.User):
        """A command to hug a user.
        You can view how many times you have cuddled this user, and how many times they have been cuddled with.
        """
        await self.run_interaction(ctx, "cuddle", "cuddled", ctx.author, user)


def setup(bot):
    bot.add_cog(Interactions(bot))
