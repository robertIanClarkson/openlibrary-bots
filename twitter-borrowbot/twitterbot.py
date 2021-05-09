import os
import time
import requests
import tweepy
import isbnlib
from typing import final
from dotenv import load_dotenv
import json

FILE_NAME = 'last_seen_id.txt'

# -------------------------Helper Functions-------------------------------

def print_tweet(id, name, text, isbn_list):
    print("ID: " + str(id))
    print("\tFROM: ", name)
    print("\tTWEET: ", text)
    print("\tISBN:", isbn_list)
    return

def is_a_reply_to_me(api, mention):
    if mention.in_reply_to_user_id:
        return mention.in_reply_to_user_id is api.me().id
    else:
        return False

def isbn_found(isbn_list):
    return len(isbn_list) > 0

def retrieve_last_seen_id(file_name):
    f_read = open(file_name, 'r')
    last_seen_id = int(f_read.read().strip())
    f_read.close()
    return last_seen_id

def store_last_seen_id(last_seen_id, file_name):
    f_write = open(file_name, 'w')
    f_write.write(str(last_seen_id))
    f_write.close()
    return

def send_reply(api, mention, reply):
    print("SENDING:", reply)
    try:
        api.update_status(reply, in_reply_to_status_id=mention.id, auto_populate_reply_metadata=True)
    except Exception as e:
        print("*** Failed to respond to user:", reply, e)

# ------------------------Main Logic Functions-------------------------------

def create_api():
    # parse .env file
    load_dotenv()
    consumer_key = os.environ.get('CONSUMER_KEY')
    consumer_secret = os.environ.get('CONSUMER_SECRET')
    access_token = os.environ.get('ACCESS_TOKEN')
    access_secret = os.environ.get('ACCESS_TOKEN_SECRET')

    # authenticate & create API
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_secret)
    api = tweepy.API(auth, wait_on_rate_limit=True, wait_on_rate_limit_notify=True)

    # verify API
    try:
        api.verify_credentials()
        print("Authentication OK")
    except Exception as e:
        print("*** Error during authentication")
        raise e
    return api

def get_mentions(api, last_seen_id):
    mentions = []
    
    try:
        mentions = api.mentions_timeline(last_seen_id, tweet_mode="extended")
    except Exception as e:
        print("*** Failed to get mentions: ", e)
    return mentions

def reply_to_tweets(api):
    last_seen_id = retrieve_last_seen_id(FILE_NAME)
    mentions = get_mentions(api, last_seen_id)
    if(len(mentions) == 0):
        print("*** No new mentions ***")
    for mention in reversed(mentions):
        reply_to_tweet(api, mention)

def reply_to_tweet(api, mention):
    last_seen_id = mention.id
    store_last_seen_id(last_seen_id, FILE_NAME)
    isbn_list = get_isbn_list(mention.full_text)

    if not isbn_found(isbn_list): # No ISBN in mention, lets check if there is a parent tweet
        if mention.in_reply_to_status_id: # tweet does have a parent
            parent_tweet = api.get_status(mention.in_reply_to_status_id) # get the parent tweet
            isbn_list = get_isbn_list(parent_tweet.text) # scrape ISBN off parent tweet
    
    # ---------------------PRINT-------------------------
    print_tweet(mention.id, mention.user.screen_name, mention.full_text.strip("\n"), isbn_list)
    # ---------------------------------------------------
    
    if isbn_found(isbn_list): # mention or parent tweet has ISBN
        for isbn in isbn_list:
            send_reply(api, mention, get_reply(mention, isbn))
    else: # isbn not found in mention & no isbn found in parent tweet if applicable
        if not is_a_reply_to_me(api, mention): # IGNORES REPLIES TO BOT THAT DONT HAVE AN ISBN OR AMAZON LINK
            # Let the user know we didn't find anything useful
            send_reply(api, mention, str('Hi 👋 @' + mention.user.screen_name + " Sorry, we couldn't find a book ID to look for, learn how I work here: https://github.com/internetarchive/openlibrary-bots"))    

def get_isbn_list(text):    
    words = text.split()
    isbnlike = isbnlib.get_isbnlike(text, level='normal')
    for word in words:
        if word.startswith("http") or word.startswith("https"):
            resp = requests.head(word)
            if "amazon" in resp.headers["Location"] and "/dp/" in resp.headers["Location"]:
                amazon_text = isbnlib.get_isbnlike(
                    resp.headers["Location"], level='normal')
                amazon_text = list(dict.fromkeys(amazon_text))
                for item in amazon_text:
                    if isbnlib.is_isbn10(item) or isbnlib.is_isbn13(item):
                        isbnlike.append(item)
    return isbnlike

def get_reply(mention, isbn):
    reply = ""
    print("\tCHECKING: ", isbn)
    isbn = isbnlib.canonical(isbn)
    if isbnlib.is_isbn10(isbn) or isbnlib.is_isbn13(isbn):
        reply = 'Hi 👋 @' + mention.user.screen_name + ask_archive(isbn)
    else:
        reply = 'Hi 👋 @' + mention.user.screen_name + " Sorry, the ISBN or Amazon link you gave us didn't seem to work, learn how I work here: https://github.com/internetarchive/openlibrary-bots"
    return reply

def ask_archive(isbn):
    failed_reply = " we had a technical issue on our end, please try again or learn how I work here: https://github.com/internetarchive/openlibrary-bots"
    try:
        resp = requests.get("http://openlibrary.org/isbn/"+isbn+".json").json()
    except:
        print("Failed GET request to open-library")
        return " we had an issue on our end, please try again or learn how I work here: https://github.com/internetarchive/openlibrary-bots"
    if resp.__contains__("ocaid"):
        try:
            resp_archive = requests.get("https://archive.org/services/loans/loan/?&action=availability&identifier="+resp["ocaid"]).json()
        except:
            print("Error in response continuing: Regular")
            return failed_reply
        if resp_archive and resp_archive['lending_status']['is_readable']:
            reply_text = " you're in luck. This book appears to be available to read for free from @openlibrary: https://openlibrary.org/isbn/" + isbn
        elif resp_archive and resp_archive['lending_status']['is_lendable']:
            reply_text = " you're in luck. This book appears to be available to borrow for free from @openlibrary: https://openlibrary.org/isbn/" + isbn
        elif resp_archive and resp_archive['lending_status']['is_printdisabled']:
            reply_text = " you're in luck. This book appears to be available to preview for free from @openlibrary: https://openlibrary.org/isbn/" + isbn
        else:
            reply_text = " This title doesn't appear to have a free read option yet, however you can add it to your Want To Read list here: https://openlibrary.org/isbn/" + isbn
    else:
        try:
            resp_advanced = requests.get("https://archive.org/advancedsearch.php?q=openlibrary_work:"+resp["works"][0]['key'].split("/")[-1]+"&fl[]=identifier&sort[]=&sort[]=&sort[]=&rows=50&page=1&output=json").json()
        except:
            print("Failed GET request to Internet-Archive")
            return failed_reply
        if resp_advanced and resp_advanced["response"]["numFound"] > 1:
            reply_text = " This edition doesn't appear to be available, however I've identified "+str(resp_advanced["response"]["numFound"])+" other editions which may be available here -> https://openlibrary.org" + resp["works"][0]['key']
        else:
            reply_text = " This title doesn't appear to have a free read option yet, however you can add it to your Want To Read list here: https://openlibrary.org/isbn/" + isbn
    return reply_text

if __name__ == "__main__":
    refresh_rate = 15
    api = create_api()
    while True:
        reply_to_tweets(api)
        print("Waiting", refresh_rate, "seconds")
        time.sleep(refresh_rate)