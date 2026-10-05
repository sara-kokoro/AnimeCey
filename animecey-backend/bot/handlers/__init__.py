"""Register all bot handlers on import."""

from bot.handlers.admin import register as register_admin
from bot.handlers.upload import register as register_upload
from bot.handlers.callbacks import register as register_callbacks
from bot.handlers.quick_upload import register as register_quick_upload
from bot.handlers.fiche import register as register_fiche
from bot.handlers.vignettes import register as register_vignettes
from bot.handlers.bilan import register as register_bilan


def register_all(bot):
    register_quick_upload(bot)  # en premier : /anime et les envois par légende
    register_fiche(bot)         # /fiche : choisir la fiche TMDB d'un animé
    register_vignettes(bot)     # /vignettes : vignettes des épisodes depuis TMDB
    register_bilan(bot)         # /bilan : ce qui est en ligne pour un animé
    register_admin(bot)
    register_upload(bot)
    register_callbacks(bot)
