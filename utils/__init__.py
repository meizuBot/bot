import re

from discord.ext.commands import Converter
from discord.utils import maybe_coroutine

__all__ = ("MENTION_REGEX", "codeblock", "converter")

MENTION_REGEX = re.compile(r"<@!?(?P<id>[0-9]{15,20})>")


def codeblock(text: str, *, lang="py"):
    return f"```{lang}\n{text}```"


def converter(func):
    class Wrapper(Converter):
        async def convert(self, ctx, arg):
            await maybe_coroutine(func, ctx, arg)

    return Wrapper
