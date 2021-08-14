import logging


class NoGateway(logging.Filter):
    def filter(self, record: logging.LogRecord):
        return record.name != "discord.gateway"
