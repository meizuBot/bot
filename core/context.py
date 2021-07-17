from discord.ext import commands

from . import Bot

__all__ = ("CustomContext", "setup", "teardown")


class Context(commands.Context):
    bot: Bot


def setup(bot: Bot) -> None:
    bot.context = Context


def teardown(bot: Bot) -> None:
    bot.context = commands.Context
