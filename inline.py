from telegram import InlineQueryResultArticle, InputTextMessageContent
from uuid import uuid4

def build_inline_result(text="UNO"):
    return [
        InlineQueryResultArticle(
            id=str(uuid4()),
            title="Uno oyunu başlat",
            input_message_content=InputTextMessageContent(text)
        )
    ]
