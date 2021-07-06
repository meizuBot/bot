from discord.ext import commands
from .bot import CustomBot
from .context import CustomContext

__all__ = ("command", "group", "CustomBot", "CustomContext")


class CommandMixin:
    def __init__(self, func, name, **attrs):
        super().__init__(func, name=name, **attrs)
        self.examples: tuple = attrs.pop("examples", (None,))
        self.params_: dict = attrs.pop("params", "This command takes no parameters")
        self.returns: str = attrs.pop("returns", "I guess nothing?")


class Command(CommandMixin, commands.Command):
    pass


class Group(Command, commands.Group):
    def command(self, *args, **kwargs):

        def wrapper(func):
            kwargs.setdefault('parent', self)
            result = command(*args, **kwargs)(func)
            self.add_command(result)
            return result

        return wrapper

    def group(self, *args, **kwargs):

        def wrapper(func):
            kwargs.setdefault('parent', self)
            result = group(*args, **kwargs)(func)
            self.add_command(result)
            return result

        return wrapper


def command(name=None, cls=None, **attrs):
    if not cls:
        cls = Command

    def decorator(func):
        if isinstance(func, (Command, commands.Command)):
            raise TypeError("Callback is already a command.")
        return cls(func, name=name, **attrs)

    return decorator


def group(name=None, **attrs):
    attrs.setdefault("cls", Group)
    return command(name=name, **attrs)
