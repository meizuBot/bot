from typing import NamedTuple

from os import getenv

__all__ = (
    "token",
    "prefix",
    "postgres_uri",
    "osu",
    "twitter_bearer_token",
    "finnhub_key",
    "nasa_key",
    "perspective_key",
)

token = getenv("TOKEN")
prefix = getenv("PREFIX")
postgres_uri = getenv("POSTGRES_URI")

osu = NamedTuple("Osu", [("client_id", int), ("client_secret", int)])(
    getenv("OSU_CLIENT_ID"), getenv("OSU_CLIENT_SECRET")
)
twitter_bearer_token = None

finnhub_key = getenv("FINNHUB_KEY")
nasa_key = getenv("NASA_KEY")
perspective_key = getenv("PERSPECTIVE_KEY")
