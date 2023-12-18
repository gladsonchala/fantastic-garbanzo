from math import ceil

from flask import Flask
from telegram.ext import CommandHandler, Filters, MessageHandler, Updater

from app import handlers, searcher, utils
from app.handlers import set_global_provider, set_global_preferences, add_admin_id, delete_admin_id, link_handler
from strings import bot_token

app = Flask(__name__)


# Routes for the Flask web app
@app.route('/')
def index():
  return "Hey This is OMG BOT! Talk to me on Telegram: https://t.me/gc_omgbot"


def main():
  updater = Updater(token=bot_token)
  dispatcher = updater.dispatcher

  dispatcher.add_handler(CommandHandler("start", handlers.start))
  dispatcher.add_handler(CommandHandler("help", handlers.help_command))
  dispatcher.add_handler(CommandHandler("developer", handlers.developer))
  dispatcher.add_handler(
      CommandHandler("setprovider", handlers.set_provider_name))
  dispatcher.add_handler(CommandHandler("clearsession",
                                        handlers.clear_session))
  message_handler = MessageHandler(Filters.text & ~Filters.command,
                                   handlers.handle_message)
  dispatcher.add_handler(message_handler)
  dispatcher.add_handler(CommandHandler("fetch", handlers.fetch))
  dispatcher.add_handler(
      CommandHandler("search", searcher.search_command_handler))
  dispatcher.add_handler(CommandHandler("searchon", searcher.enable_search))
  dispatcher.add_handler(CommandHandler("searchoff", searcher.disable_search))

  dispatcher.add_handler(
      CommandHandler("setglobalprovider", set_global_provider))

  dispatcher.add_handler(
      CommandHandler("setglobalpreferences", set_global_preferences))

  dispatcher.add_handler(CommandHandler("addadminid", add_admin_id))

  dispatcher.add_handler(CommandHandler("deleteadminid", delete_admin_id))
  dispatcher.add_handler(CommandHandler("link", link_handler))

  updater.start_polling()

  app.run(host='0.0.0.0', port=81)


if __name__ == '__main__':
  main()
