from telegram.ext import (
    Application,
    ApplicationBuilder,
)

from src.helper.config import CONFIG
from src.helper.log import get_logger
from src.handlers import register_conversation


# Main
def get_app(token: str) -> Application:
    app = ApplicationBuilder().token(token).build()
    return app


if __name__ == "__main__":
    # Init
    logger = get_logger()

    # Setup
    app = get_app(token = CONFIG.BOT_API_TOKEN.get_secret_value())
    register_conversation(app)

    # Run
    app.run_polling()