"""Register all bot handlers on import."""

from bot.handlers.admin import register as register_admin
from bot.handlers.upload import register as register_upload
from bot.handlers.callbacks import register as register_callbacks


def register_all(bot):
    register_admin(bot)
    register_upload(bot)
    register_callbacks(bot)
