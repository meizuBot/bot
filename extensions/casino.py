import random

import discord
from discord import ui
from discord.ext import commands

import core

__all__ = ("setup",)

COLORS = {"win": discord.Color.green(), "lose": discord.Color.red(), "draw": discord.Color.gold()}
DEFAULT_DESC = "`Hit`: Add another card\n`Stand`: End the game"
suits = ("♥", "♦", "♠️", "♣")

values = {
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "10": 10,
    "Jack": 10,
    "Queen": 10,
    "King": 10,
    "Ace": 11,
}


class Card:
    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank

    def __str__(self):
        return self.suit + self.rank

    def __int__(self):
        return values[self.rank]

    def __repr__(self):
        return self.__str__()


class Deck:
    def __init__(self):
        self.cards = []
        for suit in suits:
            for rank in values:
                self.cards.append(Card(suit, rank))

    def shuffle(self):
        random.shuffle(self.cards)

    def deal(self):
        return self.cards.pop()


class Hand:
    def __init__(self):
        self.cards = []
        self.value = 0
        self.aces = 0

    def add_card(self, card):
        self.cards.append(card)
        self.value += values[card.rank]
        if card.rank == "Ace":
            self.aces += 1
        self.adjust_for_ace()

    def adjust_for_ace(self):
        while self.value > 21 and self.aces:
            self.value -= 10
            self.aces -= 1


class Gamble:
    def __init__(self, bet):
        self.total = bet
        self.value = bet

    def win(self):
        self.total += self.value

    def lose(self):
        self.total -= self.value

    def blackjack(self):
        self.total += int(self.value * 1.5)


class Blackjack(ui.View):
    def __init__(self, ctx: core.Context, *, bet: int):
        super().__init__()
        self.ctx = ctx
        self.embed = None
        self.playing = True

        self.deck = Deck()
        self.deck.shuffle()

        self.player = Hand()
        self.player.add_card(self.deck.deal())
        self.player.add_card(self.deck.deal())

        self.dealer = Hand()
        self.dealer.add_card(self.deck.deal())
        self.dealer.add_card(self.deck.deal())

        self.bet = Gamble(bet)

    @ui.button(label="Hit", style=discord.ButtonStyle.success)
    async def hit_button(self, button: ui.Button, interaction: discord.Interaction):
        self.player.add_card(self.deck.deal())
        await self.check(interaction)

    @ui.button(label="Stand", style=discord.ButtonStyle.danger)
    async def stand_button(self, button: ui.Button, interaction: discord.Interaction):
        self.playing = False
        await self.check(interaction)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.ctx.author

    async def check(self, interaction=None):
        player = self.player.value
        dealer = self.dealer.value

        ret = None
        color = COLORS["win"]

        emoji = "$"

        if dealer > 21:
            self.bet.win()
            ret = f"Result: Dealer bust {emoji}{self.bet.value:,d}"
            self.playing = False

        if player == 21:
            self.playing = False

        elif player > 21:
            self.bet.lose()
            ret = f"Result: Player bust {emoji}-{self.bet.value:,d}"
            color = COLORS["lose"]
            self.playing = False

        elif player > dealer and not self.playing:
            self.bet.win()
            ret = f"Result: Win {emoji}{self.bet.value:,d}"

        elif dealer > player:
            print(dealer)
            print(player)
            self.bet.lose()
            ret = f"Result: Loss {emoji}-{self.bet.value:,d}"
            color = COLORS["lose"]
            self.playing = False

        elif dealer == player:
            ret = f"Result: Push, money back."
            color = COLORS["draw"]
            self.playing = False

        else:
            ret = DEFAULT_DESC

        if interaction:
            if self.playing is False and player <= 21:
                while self.dealer.value < 17:
                    self.dealer.add_card(self.deck.deal())
                self.stop()
            embed = self.format_embed(ret, color)
            await interaction.response.edit_message(embed=embed, view=self)

        return ret, color

    def stop(self):
        for button in self.children:
            button.disabled = True
        super().stop()

    def format_embed(self, description, color):
        player = self.player
        dealer = self.dealer

        some = self.playing

        embed = self.ctx.bot.embed(description=description, color=color)
        embed.set_footer(text=f"Cards remaining: {len(self.deck.cards)}/52")

        embed.add_field(
            name="Your hand:",
            value=(f"`{'`, `'.join(str(card) for card in player.cards)}`\n" f"Value: `{player.value}`"),
        )
        dealer_cards = (
            f"`{'`, `'.join(str(card) for card in dealer.cards)}`"
            if some is False
            else f"`?`, `{dealer.cards[1]}`"
        )
        dealer_value = dealer.value if some is False else int(dealer.cards[1])

        embed.add_field(name="Dealer's hand:", value=(f"{dealer_cards}\n" f"Value: `{dealer_value}`"))

        return embed

    async def start(self):
        player = self.player.value
        dealer = self.dealer.value

        color = COLORS["win"]
        desc = DEFAULT_DESC

        if player == 21 and dealer != 21:
            self.bet.blackjack()
            desc = f"Result: Blackjack! {self.bet.value:,d}"
            color = COLORS["win"]
            self.playing = False
            self.stop()

        elif dealer == 21:
            self.bet.lose()
            desc = f"Result: Dealer Blackjack. -{self.bet.value:,d}"
            color = COLORS["lose"]
            self.playing = False
            self.stop()

        embed = self.format_embed(desc, color)
        await self.ctx.send(embed=embed, view=self)


class Casino(commands.Cog):
    def __init__(self, bot: core.Bot):
        self.bot = bot

    @core.command()
    @commands.is_owner()
    async def blackjack(self, ctx: core.Context):
        game = Blackjack(ctx, bet=1000)
        await game.start()


def setup(bot: core.Bot):
    bot.add_cog(Casino(bot))
