import inspect
from typing import Callable, Optional, Union

import discord
from discord import Interaction, ui
from discord.ext import commands
from discord.ui.item import ItemCallbackType


class MenuError(Exception):
    pass


class CannotEmbedLinks(MenuError):
    def __init__(self):
        super().__init__("Bot does not have embed links permission in this channel.")


class CannotSendMessages(MenuError):
    def __init__(self):
        super().__init__("Bot cannot send messages in this channel.")


class CannotReadMessageHistory(MenuError):
    def __init__(self):
        super().__init__("Bot does not have Read Message History permissions in this channel.")


class ButtonSource:
    async def _prepare_once(self):
        try:
            self.__prepare
        except AttributeError:
            await self.prepare()
            self.__prepare = True

    async def prepare(self):
        return

    def is_paginating(self) -> Optional[bool]:
        raise NotImplementedError

    def get_max_pages(self) -> Optional[int]:
        return None

    async def get_page(self, page_number):
        raise NotImplementedError

    async def format_page(self, menu, page):
        raise NotImplementedError


class ListButtonSource(ButtonSource):
    def __init__(self, entries, *, per_page):
        self.entries = entries
        self.per_page = per_page

        pages, left_over = divmod(len(entries), per_page)
        if left_over:
            pages += 1

        self._max_pages = pages

    def is_paginating(self):
        return len(self.entries) > self.per_page

    def get_max_pages(self):
        return self._max_pages

    async def get_page(self, page_number):
        if self.per_page == 1:
            return self.entries[page_number]
        base = page_number * self.per_page
        return self.entries[base : base + self.per_page]


class ButtonMenu(ui.View):
    ctx: commands.Context
    current_page: int

    def __init__(self, *, timeout=180.0, delete_message_after=False):
        super().__init__(timeout=timeout)
        self.delete_message_after = delete_message_after
        self.message = None

    def should_add_reactions(self):
        return len(self.children)

    def _verify_permissions(self, ctx, channel, permissions):
        if not permissions.send_messages:
            raise CannotSendMessages()

        if self.should_add_reactions() and not permissions.read_message_history:
            raise CannotReadMessageHistory()

    async def start(self, ctx: commands.Context, *, channel=None, **send_kwargs):
        self.ctx = ctx

        channel = channel or ctx.channel
        is_guild = isinstance(channel, discord.abc.GuildChannel)
        me = channel.guild.me if is_guild else ctx.bot.user
        permissions = channel.permissions_for(me)
        self._verify_permissions(ctx, channel, permissions)

        self.message = await self.send_initial_message(channel, **send_kwargs)

    async def send_initial_message(self, channel, **send_kwargs):
        view = send_kwargs.pop("view", self)
        await channel.send(**send_kwargs, view=view)


def button(
    *,
    label: Optional[str] = None,
    custom_id: Optional[str] = None,
    disabled: bool = False,
    style: discord.ButtonStyle = discord.ButtonStyle.secondary,
    emoji: Optional[Union[str, discord.Emoji, discord.PartialEmoji]] = None,
    row: Optional[int] = None,
    skip_if: Callable = lambda x: True,
) -> Callable[[ItemCallbackType], ItemCallbackType]:
    def decorator(func: ItemCallbackType) -> ItemCallbackType:
        if not inspect.iscoroutinefunction(func):
            raise TypeError("button function must be a coroutine function")

        func.skip_if = skip_if
        func.__discord_ui_model_type__ = ui.Button
        func.__discord_ui_model_kwargs__ = {
            "style": style,
            "custom_id": custom_id,
            "url": None,
            "disabled": disabled,
            "label": label,
            "emoji": emoji,
            "row": row,
        }
        return func

    return decorator


class ButtonPages(ButtonMenu):
    def __init__(self, source: ButtonSource, **options):
        self._source = source
        self.current_page = 0
        super().__init__(**options)
        if not self._source.is_paginating():
            self.children = [b for b in self.children if b.label == "Stop"]

    async def show_page(self, interaction, page_number):
        page = await self._source.get_page(page_number)
        self.current_page = page_number
        kwargs = await self._get_kwargs_from_page(page)
        await interaction.response.edit_message(**kwargs)

    def format_view(self):
        if self._source.is_paginating():
            for i, b in enumerate(self.children):
                b.disabled = any(
                    [
                        self.current_page == 0 and i < 2,
                        self.current_page == self._source.get_max_pages() - 1 and i >= 3,
                    ]
                )

    async def show_checked_page(self, interaction, page_number):
        max_pages = self._source.get_max_pages()
        try:
            if max_pages is None or max_pages > page_number >= 0:
                # If it doesn't give maximum pages, it cannot be checked
                await self.show_page(interaction, page_number)
        except IndexError:
            # An error happened that can be handled, so ignore it.
            pass

    async def interaction_check(self, interaction):
        """Only allowing the context author to interact with the view"""
        ctx = self.ctx
        author = ctx.author
        if interaction.user != author:
            await interaction.response.send_message(f"Only `{author}` can use this menu.", ephemeral=True)
            return False
        return True

    async def start(self, ctx, *, channel=None):
        self.ctx = ctx
        await self._source._prepare_once()

        page = await self._source.get_page(0)
        kwargs = await self._get_kwargs_from_page(page)
        await super().start(ctx, channel=channel or ctx.channel, **kwargs)

    async def _get_kwargs_from_page(self, page):
        value = await discord.utils.maybe_coroutine(self._source.format_page, self, page)
        kwargs = {}
        if isinstance(value, dict):
            kwargs = value
        elif isinstance(value, str):
            kwargs = {"content": value, "embed": None}
        elif isinstance(value, discord.Embed):
            kwargs = {"embed": value, "content": None}
        self.format_view()
        if "view" not in kwargs:
            kwargs["view"] = self
        return kwargs

    @button(label="First Page", style=discord.ButtonStyle.primary)
    async def first_page(self, _, interaction: Interaction):
        await self.show_page(interaction, 0)

    @button(label="Last Page", style=discord.ButtonStyle.primary)
    async def before_page(self, _, interaction: Interaction):
        await self.show_checked_page(interaction, self.current_page - 1)

    @button(label="Stop", style=discord.ButtonStyle.danger)
    async def stop_page(self, _, interaction: Interaction):
        if self.delete_message_after:
            self.stop()
            await interaction.message.delete()
        else:
            for _button in self.children:
                _button.disabled = True
            self.stop()
            await interaction.response.edit_message(view=self)

    @button(label="Next Page", style=discord.ButtonStyle.primary)
    async def next_page(self, _, interaction: Interaction):
        await self.show_checked_page(interaction, self.current_page + 1)

    @button(label="Last Page", style=discord.ButtonStyle.primary)
    async def last_page(self, _, interaction: Interaction):
        await self.show_page(interaction, self._source.get_max_pages() - 1)
