import core

from .osu import Osu


def setup(bot: core.Bot):
    cogs = (Osu(bot),)
    bot.add_category("Games", cogs, emoji="🎮")
