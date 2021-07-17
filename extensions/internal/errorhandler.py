import asyncio
from traceback import format_exception

import discord
from discord.ext import commands

import core

__all__ = ("setup",)


class ErrorHandler(commands.Cog):
    def __init__(self, bot: core.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx: core.Context, error: Exception):
        owner_errors = (
            commands.MissingAnyRole,
            commands.MissingPermissions,
            commands.MissingRole,
            commands.CommandOnCooldown,
            commands.DisabledCommand,
        )
        if await self.bot.is_owner(ctx.author) and isinstance(error, owner_errors):
            return await ctx.reinvoke()
        if ctx.command and ctx.command.has_error_handler():
            return
        if ctx.cog and ctx.cog.has_error_handler():
            return

        error = getattr(error, "original", error)

        if ctx.command and not isinstance(error, commands.CommandOnCooldown):
            ctx.command.reset_cooldown(ctx)

        simple_errors = (commands.BadArgument, commands.BotMissingPermissions, commands.MissingPermissions)

        if isinstance(error, simple_errors):
            return await ctx.send(embed=self.bot.embed(title=str(error)))

        if isinstance(error, commands.NoPrivateMessage):
            try:
                return await ctx.author.send(
                    embed=self.bot.embed(description=f"{ctx.invoked_with} can only be used in servers.")
                )
            except discord.HTTPException:
                pass

        if isinstance(error, commands.MissingRequiredArgument):
            errors = str(error).split(" ", maxsplit=1)
            desc = (
                f"`{errors[0]}` {errors[1]}\n"
                f"You can view the help for this command with `{ctx.clean_prefix}help` `{ctx.invoked_with}`"
            )
            return await ctx.send(embed=self.bot.embed(description=desc))

        if isinstance(error, commands.DisabledCommand):
            return await ctx.send(
                embed=self.bot.embed(description=f"`{ctx.invoked_with}` has been disabled.")
            )

        if isinstance(error, asyncio.TimeoutError):
            return await ctx.send(embed=self.bot.embed(description=f"{ctx.invoked_with} timed out."))

        traceback = "".join(format_exception(type(error), error, error.__traceback__))
        if len(traceback) > 2000:
            traceback = await self.bot.paste(traceback)
        else:
            traceback = "```py\n" + traceback + "```"
        await ctx.send("Oops, an error occured. Here's some info on it: \n" + traceback)


def setup(bot: core.Bot):
    bot.add_cog(ErrorHandler(bot))
