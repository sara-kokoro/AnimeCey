"""Inline keyboard generators for the Pyrogram bot."""

from __future__ import annotations

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def language_keyboard(folder_id: int, languages: list[str]) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(lang, callback_data=f"select_lang:{folder_id}:{lang}")
        for lang in languages
    ]
    return InlineKeyboardMarkup([buttons])


def season_keyboard(seasons: list[dict]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(
            f"Saison {s['season_number']}",
            callback_data=f"select_season:{s['id']}:{s['season_number']}",
        )]
        for s in seasons
    ]
    return InlineKeyboardMarkup(buttons)


def confirm_replace_keyboard(episode_number: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Oui, remplacer", callback_data=f"confirm_replace:{episode_number}:yes"),
            InlineKeyboardButton("Non, ignorer", callback_data=f"confirm_replace:{episode_number}:no"),
        ]
    ])


def confirm_number_keyboard(detected_number: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"Oui, épisode {detected_number}", callback_data=f"confirm_number:{detected_number}:yes"),
            InlineKeyboardButton("Non, corriger", callback_data=f"confirm_number:{detected_number}:no"),
        ]
    ])
