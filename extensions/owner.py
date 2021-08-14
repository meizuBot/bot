import ast
import asyncio
import contextlib
import inspect
import io
import traceback

import asyncpg
import discord
import import_expression
from discord.ext import commands
from jishaku.codeblocks import codeblock_converter
from jishaku.paginators import PaginatorInterface, WrappedPaginator
from tabulate import tabulate

import core
from utils import codeblock
from utils.time import Timer

__all__ = ("setup",)


async def send(ctx: core.Context, result, stdout_):
    try:
        await ctx.message.add_reaction("<:prettythumbsup:806390638044119050>")
    except (discord.HTTPException, discord.Forbidden):
        pass
    else:
        value = stdout_.getvalue()
        if not result:
            if value:
                await ctx.send(f"```py\n{value}\n```")
            return

        kwargs = {}

        if isinstance(result, discord.Embed):
            kwargs["embed"] = result
        elif isinstance(result, discord.File):
            kwargs["file"] = result

        if not isinstance(result, str):
            result = str(repr(result))

        if result.strip() == "":
            result = "\u200b"

        to_be_sent = f"{value}{result}".replace(ctx.bot.http.token, "< adios token >")

        if len(to_be_sent) < 1990:
            return await ctx.send(to_be_sent, **kwargs)

        paginator = WrappedPaginator(prefix="", suffix="", max_size=1990, wrap_on=("",))
        paginator.add_line(to_be_sent)
        interface = PaginatorInterface(ctx.bot, paginator, owner=ctx.author)
        await interface.send_to(ctx)


class Owner(commands.Cog, command_attrs=dict(hidden=True)):
    def __init__(self, bot: core.Bot):
        self.bot = bot
        self.pool = self.bot.pool

    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author)

    @core.command()
    async def eval(self, ctx: core.Context, *, argument: codeblock_converter):
        env = {
            "ctx": ctx,
            "discord": discord,
            "commands": commands,
            "bot": ctx.bot,
            "channel": ctx.channel,
            "guild": ctx.guild,
            "message": ctx.message,
            "reference": ctx.message.reference,
            "find": discord.utils.find,
            "get": discord.utils.get,
            "core": core,
            "inspect": inspect,
            "asyncio": asyncio,
            "session": self.bot.session,
        }
        env.update(globals())

        parsed = import_expression.parse(argument.content)
        base_function = "async def __execute(): pass"
        parsed_function = import_expression.parse(base_function)

        for node in parsed.body:
            ast.increment_lineno(node)

        def check_for_yield(payload):
            if isinstance(payload, (list, tuple)):
                for node_ in payload:
                    if check_for_yield(node_):
                        return True
            if isinstance(payload, (ast.Yield, ast.YieldFrom)):
                return True
            if hasattr(payload, "body"):
                for node_ in payload.body:
                    if check_for_yield(node_):
                        return True
            if hasattr(payload, "value"):
                if check_for_yield(payload.value):
                    return True
            return False

        def insert_returns(body):
            if isinstance(body[-1], ast.Expr):
                body[-1] = ast.Return(body[-1].value)
                ast.fix_missing_locations(body[-1])

            if isinstance(body[-1], ast.If):
                insert_returns(body[-1].body)
                insert_returns(body[-1].orelse)

            if isinstance(body[-1], (ast.With, ast.AsyncWith)):
                insert_returns(body[-1].body)

        if not check_for_yield(parsed.body):
            insert_returns(parsed.body)

        parsed_function.body[0].body = parsed.body

        try:
            import_expression.exec(
                import_expression.compile(parsed_function, filename="<repl>", mode="exec"), env, locals()
            )
        except Exception as err:
            return await ctx.send(f"```py\n" f"{err.__class__.__name__}: {err}```")

        func = locals()["__execute"]
        with io.StringIO() as stdout:
            try:
                with contextlib.redirect_stdout(stdout):
                    to_exec = func()

                    if inspect.isasyncgenfunction(func):
                        async for output in to_exec:
                            if not output:
                                continue
                            await send(ctx, output, stdout)
                        return

                    result = await to_exec
                    await send(ctx, result, stdout)
            except Exception as err:
                base = (type(err), err, err.__traceback__)
                exception = "".join(traceback.format_exception(*base, limit=2))
                value = stdout.getvalue()
                return await ctx.send(f"```py\n{value}{exception}```"[:1990])

    @core.group()
    async def sql(self, ctx: core.Context):
        if not ctx.invoked_subcommand:
            await ctx.send_help(ctx.command)

    @sql.command(aliases=("e",))
    async def execute(self, ctx: core.Context, *, query: str):
        with Timer() as timer:
            ret = await self.pool.execute(query.strip("`"))
        await ctx.send(f"`{ret}`\n**Executed in {timer.exact}**")

    @sql.command(aliases=("f",))
    async def fetch(self, ctx: core.Context, *, query: str):
        with Timer() as timer:
            ret = await self.pool.fetch(query.strip("`"))
        table = tabulate((dict(row) for row in ret), headers="keys", tablefmt="github")
        if len(table) > 1000:
            table = await self.bot.paste(table)
        await ctx.send(f"{codeblock(table)}\n**Retrieved {len(ret)} rows in {timer.exact}**")

    @sql.command(aliases=("fv",))
    async def fetchval(self, ctx: core.Context, *, query: str):
        with Timer() as timer:
            ret = await self.pool.fetchval(query.strip("`"))
        await ctx.send(f"{codeblock(f'{ret!r}')}\n**Retrieved in {timer.exact}**")

    @sql.error
    async def sql_error(self, ctx: core.Context, error: Exception):
        if isinstance(error, commands.CommandInvokeError):
            error = error.original
            if isinstance(error, asyncpg.exceptions.PostgresSyntaxError):
                return await ctx.send(embed=self.bot.embed(description=f"Syntax error:```\n {error} ```"))
        await ctx.send(error)

    @fetch.error
    async def fetch_error(self, ctx: core.Context, error):
        await self.sql_error(ctx, error)

    @fetchval.error
    async def fetchval_error(self, ctx: core.Context, error):
        await self.sql_error(ctx, error)

    @execute.error
    async def execute_error(self, ctx: core.Context, error):
        await self.sql_error(ctx, error)


def setup(bot: core.Bot):
    bot.add_cog(Owner(bot))
