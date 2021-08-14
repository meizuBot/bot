from typing import NamedTuple

from yaml import safe_load

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

with open("config.yml") as f:
    _config = safe_load(f)

token = _config["token"]
prefix = _config["prefix"]
postgres_uri = _config["postgres_uri"]

_keys = _config["keys"]

osu = NamedTuple("Osu", [("client_id", int), ("client_secret", int)])(
    _keys["osu"]["client_id"], _keys["osu"]["client_secret"]
)
gist = NamedTuple("Gist", (["id", str], ["token", str]))(_keys["gist"]["id"], _keys["gist"]["token"])
twitter_bearer_token = _keys["twitter_bearer_token"]
finnhub_key = _keys["finnhub_key"]
nasa_key = _keys["nasa_key"]
perspective_key = _keys["perspective_key"]

del _config, _keys
