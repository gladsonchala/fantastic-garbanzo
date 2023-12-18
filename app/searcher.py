import json
import logging
import time
from datetime import datetime, timedelta
from cachetools import TTLCache

import requests
import requests.exceptions
from googlesearch import search
from telegram import ChatAction

from app.utils import (
    get_search_state,
    get_user_info,
    get_user_previous_messages,
    get_user_provider_name,
    set_search_state,
    store_message,
    latest_key,
)
from strings import default_provider, endpoint_url, instruction, prompt, results, sleep_interval

logger = logging.getLogger(__name__)

# Create an in-memory cache with a time-to-live (TTL) of 1 day
cache = TTLCache(maxsize=1000, ttl=86400)  # 86400 seconds in a day

def google_search(query):
  return search(query,
                sleep_interval=sleep_interval,
                num_results=results,
                advanced=True)



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
            f"Stored message for user {user_id}: {user_message} -> {ai_response}"
        )
    except Exception as e:
        # Log any errors that occur during storage
        logger.error(f"Error storing message for user {user_id}: {e}")

# Modify the send_request function to include search results in the message
def send_request_with_search(user_message, search_results, user_id, context, update):
    user_id, user_name, username = get_user_info(update)

    # Extract search results titles
    search_resultss = [
        f"Title: {result.title}\nURL: {result.url}\nDescription: {result.description}\n"
        for result in search_results
    ]
    # Concatenate search results with the user message
    total_message = """This is User's question:{}\n\nGoogle Search Results:\n{}\nSummarize all and reply accordingly(cite if needed) include your knowledge and thoughts.""".format(
        user_message, search_resultss)
    # Call the original send_request function
    return send_request(total_message, user_id, context, update)

# Function to handle sending requests with logging
def send_request(user_message, user_id, context, update):
    user_id, user_name, username = get_user_info(update)
    provider_named = get_user_provider_name(user_id)
    provider_name = provider_named if provider_named else default_provider

    # Get user's previous messages
    previousmsg = get_user_previous_messages(user_id)

    # Add 'instruction' and 'prompt' to the request
    context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
    if previousmsg:
        total_message = "Note(this is secret): {}\n and Here's our previous chats: {}, reply to my new question: {}??. The question/message is from user with Name {} aka {} on telegram) ".format(
            prompt, previousmsg, user_message, user_name, username)
    else:
        total_message = "Your secret instruction: {} and answer this question. ->> IMPORTANT: Don't write another shits except your thoughts(1 sentence) and answer of this question. The question/message is from user with Name {} aka {} on telegram) with question:{}".format(
            instruction, user_name, username, user_message)

    # URL endpoint
    url = endpoint_url

    # Params to be sent with the request
    # params = {'user_message': total_message, 'provider_name': provider_name}
    params = {'user_message': total_message}


    # Make a POST request to the API with logging
    response = requests.post(url, params=params)
    context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
    logger.info(
        f"Request sent to API for user {user_id} with message: {user_message}")

    try:
        # Try parsing the JSON response
        response_content = response.content.decode('utf-8')
        parsed_data = json.loads(response_content)
        message = parsed_data['message']
        ai_response = message

        # Store the conversation in the cache
        store_message(user_id, user_message, ai_response)
        # Check if the response message indicates an unauthorized error
        if "Error generating response: 401 Client Error: Unauthorized" in ai_response:
            # If unauthorized error, call the retry function
            return send_request_with_retry(user_message, user_id, context, update)
        else:
            return message
    except json.JSONDecodeError:
        # If JSON decoding fails, return the response content as a string
        message = response.content.decode('utf-8')
        # Log the error
        logger.error(f"Error decoding JSON response for user {user_id}: {message}")
        return message
    except Exception as e:
        # Handle other exceptions and log the error
        logger.error(f"Error processing API response for user {user_id}: {e}")
        return "Error occurred!\nPlease send /clearsession and retry your question."

# Command handler to enable search
def enable_search(update, context):
    try:
        user_id = update.message.from_user.id
        set_search_state(user_id, True)
        update.message.reply_text("Search is now enabled. \nWarning: Please don't use this in normal chat, because ", parse_Mode="MARKDOWN")
    except Exception as e:
        logger.error(e)

# Command handler to disable search
def disable_search(update, context):
    try:
        user_id = update.message.from_user.id
        set_search_state(user_id, False)
        update.message.reply_text("Search is now disabled.")
    except Exception as e:
        logger.error(e)

# Function to handle sending requests with logging and retry mechanism
def send_request_with_retry(user_message, user_id, context, update, retries=3):
    for attempt in range(retries):
        try:
            return send_request(user_message, user_id, context, update)
        except requests.exceptions.HTTPError as e:
            if "401 Client Error: Unauthorized" in str(e):
                logger.warning(
                    f"Unauthorized error on attempt {attempt + 1}. Retrying...")
                time.sleep(1)  # Add a delay before retrying
            else:
                raise  # Re-raise other HTTP errors
    else:
        # If reached maximum retries, inform the user to try again later
        return "I'm sorry my mind is a little touched with your question.\nCan you retry it later?"

# Command handler for /search
def search_command_handler(update, context):
    user_id, user_name, username = get_user_info(update)
    user_message = update.message.text
    search_enabled = get_search_state(user_id)

    if search_enabled:
        # Extract the search query
        search_query = user_message.strip()

        if search_query:
            # Perform Google search
            context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
            search_results = google_search(search_query)

            # Send the search results to the AI request
            ai_response = send_request_with_search(user_message, search_results,
                                                         user_id, context, update)

            # Reply to the user with AI response
            try:
                update.message.reply_text(f"""{ai_response}""", parse_mode='Markdown')
            except Exception:
                update.message.reply_text(ai_response)
        else:
            # If the search query is empty, inform the user
            update.message.reply_text(
                "Please provide a search query after /search.\n\nExample: ```example /search What's the weather in London now?```",
                parse_mode='Markdown')
    else:
        if user_message.startswith("/search "):
            search_query = user_message[len("/search "):].strip()
            context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
            search_results = google_search(search_query)
            ai_response = send_request_with_search(user_message, search_results,
                                                         user_id, context, update)
            try:
                update.message.reply_text(f"""{ai_response}""", parse_mode='Markdown')
            except:
                update.message.reply_text(ai_response)
        else:
            update.message.reply_text("Please provide a search query after /search.\n\nExample: ```example /search What's the weather in London now?```",
                parse_mode='Markdown')
