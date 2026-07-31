from telegram import (
    Update,
    InlineQueryResultArticle,
    InputTextMessageContent
)

from telegram.ext import (
    InlineQueryHandler,
    ContextTypes
)

from uuid import uuid4
from game import games


async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.inline_query

    if not query:
        return

    user_id = query.from_user.id

    cards = []

    for chat_id, game in games.items():

        if user_id in game["hands"]:
            cards = game["hands"][user_id]
            break

    results = []

    if not cards:
        results.append(
            InlineQueryResultArticle(
                id=str(uuid4()),
                title="Kart bulunamadı",
                input_message_content=InputTextMessageContent(
                    "Şu anda aktif bir oyunda değilsin."
                )
            )
        )

    else:

        for i, card in enumerate(cards):

            results.append(
                InlineQueryResultArticle(
                    id=str(uuid4()),
                    title=f"{i+1}. {card}",
                    description="Oynamak için seç",
                    input_message_content=InputTextMessageContent(
                        f"/at {i+1}"
                    )
                )
            )

    await query.answer(
        results,
        cache_time=0,
        is_personal=True
    )


def register(app):
    app.add_handler(
        InlineQueryHandler(inline_query)
    )
