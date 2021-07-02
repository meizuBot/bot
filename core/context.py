from discord.ext import commands

from . import CustomBot

__all__ = ("CustomContext", "setup", "teardown")


class CustomContext(commands.Context):
    bot: CustomBot


def setup(bot: CustomBot) -> None:
    bot.context = CustomContext


def teardown(bot: CustomBot) -> None:
    bot.context = commands.Context
