from .background import BackgroundEvents
import core
from .api import BackendAPI

def setup(bot: core.CustomBot) -> None:
    cogs = (
        BackendAPI(bot),
        BackgroundEvents(bot)
    )
    bot.add_category("Internal", cogs)