from typing import List, Mapping, Union

import discord
from discord import ui
from discord.ext import commands

import core
from utils import decos
from utils.buttons import menus

__all__ = ("setup",)


def get_sig(ctx: core.Context, command: Union[core.Command, commands.Command]) -> str:
    sig = command.signature
    if not sig and not command.parent:
        return f"`{ctx.clean_prefix}{command.name}`"
    if not command.parent:
        return f"`{ctx.clean_prefix}{command.name}` `{sig}`"
    if not sig:
        return f"`{ctx.clean_prefix}{command.parent}` `{command.name}`"
    return f"`{ctx.clean_prefix}{command.parent}` `{command.name}` `{sig}`"


def add_formatting(command):
    fmt = "{0}" if command.short_doc else "No help was provided for this command."
    return fmt.format(command.short_doc)


@decos.pages(per_page=4)
async def CogSource(source, menu: menus.ButtonMenu, _commands: List[Union[core.Command, commands.Command]]):
    ctx: core.Context = menu.ctx
    page = f"{menu.current_page + 1}/{source.get_max_pages()}"
    cog: commands.Cog = _commands[0].cog
    name = cog.qualified_name
    if hasattr(cog, "emoji"):
        name = f"{cog.emoji} {name}"
    embed = ctx.bot.embed(title=f"{name} | {page} ({len(source.entries)} Commands)")
    for command in _commands:
        embed.add_field(
            name=get_sig(ctx, command),
            value=add_formatting(command).format(prefix=ctx.clean_prefix),
            inline=False,
        )
    if menu.current_page == 0:
        embed.description = cog.description

    return embed


class GroupSource(menus.ListButtonSource):
    def __init__(
        self,
        group: Union[core.Group, commands.Group],
        entries: List[Union[core.Command, commands.Command]],
        *,
        per_page: int,
    ):
        super().__init__(entries=entries, per_page=per_page)
        self.group = group

    async def format_page(self, menu: menus.ButtonPages, cmds: List[core.Command]):
        ctx = menu.ctx
        page = f"{menu.current_page + 1}/{self.get_max_pages()}"
        embed = ctx.bot.embed(
            title=f"{self.group.cog.qualified_name.lower()}:{self.group.qualified_name} | {page} ({len(self.entries)} Subcommands)"
        )

        for command in cmds:
            embed.add_field(
                name=get_sig(ctx, command),
                value=add_formatting(command).format(prefix=ctx.clean_prefix),
                inline=False,
            )

        if menu.current_page == 0:
            embed.description = self.group.description

        return embed


class CustomHelp(commands.HelpCommand):
    context: core.Context

    async def filter_commands(self, cmds, *, sort=True, key=None):
        if sort and key is None:
            key = lambda c: c.name

        iterator = cmds if self.show_hidden else list(filter(lambda c: not c.hidden, cmds))

        return sorted(iterator, key=key) if sort else iterator

    async def send(self, **send_kwargs):
        if not send_kwargs.get("view"):
            view = ui.View()
            view.add_item(
                ui.Button(label="Invite Me", url="https://google.com", style=discord.ButtonStyle.grey)
            )
            view.add_item(
                ui.Button(
                    label="Join the Support Server",
                    url="https://google.com",
                    style=discord.ButtonStyle.grey,
                )
            )

            send_kwargs["view"] = view

        destination = self.get_destination()
        await destination.send(**send_kwargs)

    async def send_bot_help(
        self, mapping: Mapping[commands.Cog, List[Union[core.Command, commands.Command]]]
    ):
        cogs = [
            f"{cog.emoji} `{self.context.clean_prefix}help` `{cog.qualified_name}`"
            for cog in mapping
            if hasattr(cog, "emoji")
        ]
        description = (
            "`<argument>` means the argument is required",
            "`[argument]` means the argument is optional\n",
            f"Send `{self.context.clean_prefix}help` `[command]` for more info on a command.",
            f"You can also send `{self.context.clean_prefix}help` `[module]` for more info on a particular module.",
        )
        embed = self.context.bot.embed(title=f"Bot Help", description="\n".join(description))
        embed.add_field(name="Modules", value="\n".join(cogs))
        await self.send(embed=embed)

    async def send_cog_help(self, cog: commands.Cog):
        if not hasattr(cog, "emoji") and not await self.context.bot.is_owner(self.context.author):
            return await self.send_error_message(self.command_not_found(cog.qualified_name))

        if getattr(cog, "show_subcommands", False) is True:
            _commands = list(cog.walk_commands())
        else:
            _commands = cog.get_commands()
        source = CogSource(entries=await self.filter_commands(_commands))
        menu = menus.ButtonPages(source=source)
        await menu.start(self.context)

    async def send_group_help(self, group: Union[core.Group, commands.Group]):
        if not hasattr(group.cog, "emoji") and not await self.context.bot.is_owner(self.context.author):
            return await self.send_error_message(self.command_not_found(group.cog.qualified_name))

        _commands = list(group.walk_commands())

        source = GroupSource(group, entries=await self.filter_commands(_commands), per_page=4)
        menu = menus.ButtonPages(source=source)
        await menu.start(self.context)

    async def send_command_help(self, command: Union[core.Command, commands.Command]):
        if not hasattr(command.cog, "emoji") and not await self.context.bot.is_owner(self.context.author):
            return await self.send_error_message(self.command_not_found(command.qualified_name))

        ctx = self.context
        embed = ctx.bot.embed(title=f"{command.cog.qualified_name.lower()}:{command.qualified_name}")
        help_string = command.help or "No help was provided for this command ._."
        embed.description = help_string.format(prefix=ctx.clean_prefix)

        usage = get_sig(self.context, command)
        if returns := getattr(command, "returns", None):
            usage += "\nReturns: " + returns

        embed.add_field(name="Usage", value=usage, inline=False)

        if aliases := command.aliases:
            embed.add_field(name="Aliases", value="`" + "`, `".join(aliases) + "`", inline=True)

        if isinstance(command, core.Command):
            params = command.params_
            if isinstance(params, dict):
                _formatted = "\n".join(f"`{param}`: {value}" for param, value in params.items())
            else:
                _formatted = params

            embed.add_field(name="Parameters", value=_formatted)

            embed.add_field(
                name="Examples",
                value="\n".join(
                    f"`{ctx.clean_prefix}{command.qualified_name}` `{example}`"
                    if example
                    else f"`{ctx.clean_prefix}{command.qualified_name}`"
                    for example in command.examples
                ),
            )

        await self.send(embed=embed)


def setup(bot: core.Bot):
    bot.help_command = CustomHelp()


def teardown(bot: core.Bot):
    bot.help_command = commands.DefaultHelpCommand()
