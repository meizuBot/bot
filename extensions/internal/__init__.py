import core
from .api import BackendAPI
from .background import BackgroundEvents
from .errorhandler import ErrorHandler

def setup(bot: core.Bot) -> None:
    cogs = (
        BackendAPI(bot),
        BackgroundEvents(bot),
        ErrorHandler(bot)
    )
    bot.add_category("Internal", cogs, path="private")