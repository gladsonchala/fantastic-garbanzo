from telegram import ChatAction, Update
from telegram.ext import CallbackContext

from app.searcher import google_search, send_request, send_request_with_search
from app.utils import link_from_text, get_search_state, latest_key, logger, get_user_info
from strings import default_provider, helpmsg, admin_id, admin_ids, user_provider_preferences
from WebScrape import WebScraper
from cachetools import TTLCache

# Create an in-memory cache with a time-to-live (TTL) of 1 day
cache = TTLCache(maxsize=1000, ttl=86400)  # 86400 seconds in a day

# Function to get user's previous messages from the cache
def get_user_previous_messages(user_id):
    user_key = str(user_id)
    messages = [cache[key] for key in cache.keys() if key.startswith(user_key)]
    return "\n".join(messages)

# Function to store user messages and AI responses in the cache with logging
def store_message(user_id, user_message, ai_response):
    try:
        key = f"{user_id}_{latest_key() + 1}"
        cache[key] = f"User: {user_message}\nYou: {ai_response}"

        # Log the stored message
        logger.info(
            f"Stored message for user {user_id}: {user_message} -> {ai_response}")
    except Exception as e:
        # Log any errors that occur during storage
        logger.error(f"Error storing message for user {user_id}: {e}")


# Command handler for the /help command
def help_command(update: Update, context: CallbackContext):
  help_message = helpmsg
  update.message.reply_text(help_message, parse_mode='Markdown')


# Command handler for the /developer command
def developer(update: Update, context: CallbackContext):
  update.message.reply_text("```Developer: Gemechis Chala```\n@ScorpiDev",
                            parse_mode='Markdown')


# Handler to log messages to the cache
def log(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    user_message = update.message.text
    store_message(user_id, user_message, "")

# Handler to fetch the latest message
def fetch(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    latest_message = cache.get(str(latest_key()), 'No Messages yet.')
    update.message.reply_text(latest_message)
    user_message = update.message.text
    update.message.reply_text(send_request(user_message, user_id, context, update))

# Message handler to check search preference and use appropriate method
def handle_message(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    user_message = "User: " + update.message.text
    context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)

    # Check if search is enabled
    search_enabled = get_search_state(user_id)

    # Choose the appropriate method based on search preference
    if search_enabled:
        search_results = google_search(update.message.text)
        response = send_request_with_search(user_message, search_results, user_id, context, update)
    else:
        response = send_request(user_message, user_id, context, update)

    if response.strip() == "":
        response = "Try again, please. I don't get it...\nIf I send this one more times, use /clearsession to clear my brain filled with your conversations."
        update.message.reply_text(response)
    else:
        try:
            update.message.reply_text(response, parse_mode='Markdown')
        except Exception as e:
            update.message.reply_text(response)

# Command handler to clear session
def clear_session(update, context):
    try:
        user_id = update.message.from_user.id
        keys_copy = list(cache.keys())

        for key in keys_copy:
            if str(user_id) in key:
                del cache[key]

        update.message.reply_text("Session cleared successfully.")
    except Exception as e:
        logger.error(e)

# Command handler for /start command
def start(update: Update, context: CallbackContext):
    user_id, user_name, username = get_user_info(update)

    try:
        user_message = "Hey OMG, you're talking with user with username {} and his user ID: {}. Say Welcome to OMG Bot to him/her!".format(
            user_name, user_id)

        response = send_request(user_message, user_id, context, update)

        if response.strip() == "":
            update.message.reply_text(
                "Hurray, I'm OMG bot!\n```Welcome!```\nAsk me whatever you want.\nUse /help command for more!",
                parse_mode='Markdown')
        else:
            try:
                update.message.reply_text(response, parse_mode='Markdown')
            except Exception as e:
                update.message.reply_text(response)
    except Exception as e:
        logger.error(e)
        update.message.reply_text(
            "Hurray, I'm OMG bot!\n```Welcome!```\nAsk me whatever you want.\nUse /help command for more!",
            parse_mode='Markdown')
        
# Command handler to add a user ID to the admin_ids list
def add_admin_id(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id in admin_ids:
        # Check if at least one argument is provided
        if not context.args:
            update.message.reply_text(
                "Please provide a user ID to add to admin_ids.")
            return

        # Get the user ID from the argument
        new_admin_id = int(context.args[0])

        # Add the new user ID to admin_ids if not already present
        if new_admin_id not in admin_ids:
            admin_ids.append(new_admin_id)
            update.message.reply_text(
                f"User ID {new_admin_id} added to admin_ids.")
        else:
            update.message.reply_text(
                f"User ID {new_admin_id} is already in admin_ids.")
    else:
        update.message.reply_text(
            "You don't have permission to use this command.")



def link_handler(update, context):
  # Extract user information
  user_id, user_name, username = get_user_info(update)

  # Extract the link from the user's message
  user_message = update.message.text
  url = link_from_text(user_message)
  if url:
    # Perform link scraping using WebScraper
    context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
    link_scraper = WebScraper(url)
    scraped_text = link_scraper.scrape_visible_text()
    urlScrapedData = "Link: " + url + "\nThe Webpage Data" + scraped_text

    # Send the scraped text to the AI request
    ai_response = send_request(urlScrapedData, user_id, context, update)

    # Reply to the user with AI response
    try:
      update.message.reply_text(f"{ai_response}", parse_mode='Markdown')
    except Exception:
      update.message.reply_text(ai_response)
  else:
    update.message.reply_text(
        "Invalid command format. Please use '/link <url>'.")




# Command handler to set provider globally
def set_global_provider(update: Update, context: CallbackContext):
  user_id = update.message.from_user.id
  if user_id == admin_id:
    provider_name = context.args[0] if context.args else default_provider
    # Update the global provider in strings.py
    update_global_provider(provider_name)
    update.message.reply_text(f"Global provider set to: {provider_name}")
  else:
    update.message.reply_text("You don't have permission to use this command.")


# Function to update the global provider in strings.py
def update_global_provider(provider_name):
  with open("strings.py", "r") as file:
    data = file.readlines()

  for i, line in enumerate(data):
    if "default_provider" in line:
      data[i] = f'default_provider = "{provider_name}"\n'

  with open("strings.py", "w") as file:
    file.writelines(data)


#############################


# Command handler to set preferences globally
def set_global_preferences(update: Update, context: CallbackContext):
  user_id = update.message.from_user.id
  if user_id in admin_ids:
    # Check if at least one argument is provided
    if not context.args:
      update.message.reply_text(
          "Please provide at least one preference to update.")
      return

    # Get preference name and value from arguments
    preference_name = context.args[0].lower()
    preference_value = " ".join(context.args[1:])

    # Update the global preference in strings.py
    update_global_preference(preference_name, preference_value)
    update.message.reply_text(
        f"Global {preference_name} set to: {preference_value}")
  else:
    update.message.reply_text("You don't have permission to use this command.")


# Function to update the global preference in strings.py
def update_global_preference(preference_name, preference_value):
  with open("strings.py", "r") as file:
    data = file.readlines()

  for i, line in enumerate(data):
    if f"{preference_name} =" in line:
      data[i] = f'{preference_name} = "{preference_value}"\n'

  with open("strings.py", "w") as file:
    file.writelines(data)


######################################


# Command handler to add a user ID to the admin_ids list
def add_admin_id(update: Update, context: CallbackContext):
  user_id = update.message.from_user.id
  if user_id in admin_ids:
    # Check if at least one argument is provided
    if not context.args:
      update.message.reply_text(
          "Please provide a user ID to add to admin_ids.")
      return

    # Get the user ID from the argument
    new_admin_id = int(context.args[0])

    # Add the new user ID to admin_ids if not already present
    if new_admin_id not in admin_ids:
      admin_ids.append(new_admin_id)
      update.message.reply_text(f"User ID {new_admin_id} added to admin_ids.")
    else:
      update.message.reply_text(
          f"User ID {new_admin_id} is already in admin_ids.")
  else:
    update.message.reply_text("You don't have permission to use this command.")


# Command handler to delete a user ID from the admin_ids list
def delete_admin_id(update: Update, context: CallbackContext):
  user_id = update.message.from_user.id
  if user_id in admin_ids:
    # Check if at least one argument is provided
    if not context.args:
      update.message.reply_text(
          "Please provide a user ID to delete from admin_ids.")
      return

    # Get the user ID from the argument
    del_admin_id = int(context.args[0])

    # Delete the user ID from admin_ids if present
    if del_admin_id in admin_ids:
      admin_ids.remove(del_admin_id)
      update.message.reply_text(
          f"User ID {del_admin_id} deleted from admin_ids.")
    else:
      update.message.reply_text(f"User ID {del_admin_id} is not in admin_ids.")
  else:
    update.message.reply_text("You don't have permission to use this command.")



# Command to set provider name
def set_provider_name(update: Update, context: CallbackContext):
  user_id = update.message.from_user.id
  message_text = update.message.text.strip()

  if message_text == '/setprovider':
    # User wants to reset to the default provider
    user_provider_preferences[user_id] = default_provider
    update.message.reply_text(f"Provider name set to the default!")
  else:
    # User wants to set a custom provider
    custom_provider = message_text[len('/setprovider '):]
    user_provider_preferences[user_id] = custom_provider
    update.message.reply_text(
        f"Provider name set to: {custom_provider} for this chat session.\nNote: If you don't know what it is, please click on this: /setprovider to change to default."
    )

