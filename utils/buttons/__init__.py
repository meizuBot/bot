import asyncio
from typing import Optional, Tuple, Union

import discord

import core


class StopButton(discord.ui.Button):
    """A button that deletes the message when pressed."""

    def __init__(
        self,
        *,
        style: discord.ButtonStyle = discord.ButtonStyle.red,
        label: Optional[str] = "Stop",
        disabled: bool = False,
        custom_id: Optional[str] = None,
        emoji: Optional[Union[str, discord.PartialEmoji]] = None,
        row: Optional[int] = None,
    ):
        # we override some things so I don't have to pass in the same stuff every time
        super().__init__(
            style=style, label=label, disabled=disabled, custom_id=custom_id, emoji=emoji, row=row
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.message.delete()


class ConfirmationButton(discord.ui.Button["ComfirmationView"]):
    def __init__(self, value: bool, **kwargs):
        self.value = value
        super().__init__(**kwargs)

    async def callback(self, interaction: discord.Interaction):
        if self.view.delete_after:
            try:
                await interaction.message.delete()
            except discord.HTTPException:
                pass
            interaction.message = None

        self.view.message = interaction.message
        self.view.value = self.value

        self.view.event.set()
        self.view.stop()


class ConfirmationView(discord.ui.View):
    message: discord.Message = None
    value: bool = False

    def __init__(self, values, *, user: discord.User, delete_after=True):
        self.delete_after = delete_after
        self.user = user
        self.event = asyncio.Event()

        super().__init__()

        self.add_item(ConfirmationButton(True, label=values[0], style=discord.ButtonStyle.green))
        self.add_item(ConfirmationButton(False, label=values[1], style=discord.ButtonStyle.red))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return self.user == interaction.user

    async def start(self, ctx: core.CustomContext, **send_kwargs) -> Tuple[discord.Message, bool]:
        await ctx.send(**send_kwargs, view=self)
        await self.event.wait()
        return self.message, self.value
