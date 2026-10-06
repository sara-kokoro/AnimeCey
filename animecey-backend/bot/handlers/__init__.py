"""Register all bot handlers on import."""

from bot.handlers.admin import register as register_admin
from bot.handlers.upload import register as register_upload
from bot.handlers.callbacks import register as register_callbacks
from bot.handlers.quick_upload import register as register_quick_upload
from bot.handlers.fiche import register as register_fiche
from bot.handlers.vignettes import register as register_vignettes
from bot.handlers.bilan import register as register_bilan
from bot.handlers.ajouter import register as register_ajouter
from bot.handlers.supprimer import register as register_supprimer
from bot.handlers.alias import register as register_alias
from bot.handlers.delsaison import register as register_delsaison
from bot.handlers.live import register as register_live


def register_all(bot):
    register_quick_upload(bot)  # en premier : /anime et les envois par légende
    register_fiche(bot)         # /fiche : choisir la fiche TMDB d'un animé
    register_vignettes(bot)     # /vignettes : vignettes des épisodes depuis TMDB
    register_bilan(bot)         # /bilan : ce qui est en ligne pour un animé
    register_ajouter(bot)       # /ajouter : ajouter un animé absent du catalogue
    register_supprimer(bot)     # /supprimer : supprimer un animé (avec confirmation)
    register_alias(bot)         # /alias : autres noms d'un animé (recherche)
    register_delsaison(bot)     # /delsaison : supprimer une seule saison
    register_live(bot)          # /add : films et séries live-action (TMDB)
    register_admin(bot)
    register_upload(bot)
    register_callbacks(bot)
