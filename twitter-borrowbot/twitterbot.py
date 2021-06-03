import tweepy
import os
import threading
import dotenv
import traceback
import logging

from services import ISBNFinder, InternetArchive
from TwitterBotErrors import *

ACTIONS = ('read', 'borrow', 'preview')
READ_OPTIONS = dict(zip(InternetArchive.MODES, ACTIONS))

LOG_FILE = "twitterbot.log"

TWITTER_BOT_NAME = "@applesauce_bob"

LOCK = threading.Lock()

class BorrowBot(tweepy.StreamListener):
    def on_status(self, mention):
        logging.info("MENTION FROM: " + mention.user.screen_name + " --> " + mention.text.replace("\n", " "))
        thread = MentionHandler(mention)
        # thread.daemon = True
        thread.start()

    def on_error(self, status_code):
        logging.critical(str(status_code))
class MentionHandler(threading.Thread):
    def __init__(self, mention):
        threading.Thread.__init__(self)
        self.mention = mention
    
    def __get_tweet(self, status_id):
        if not isinstance(status_id, int) and not isinstance(status_id, str):
            raise GetTweetError(id=status_id, error="Status ID needs to be an integer or a string")
        if isinstance(status_id, str) and not status_id.isdecimal():
            raise GetTweetError(id=status_id, error="String status ID must be in integer form")
        try:
            return API.get_status(
                id=status_id,
                tweet_mode="extended")
        except Exception as e:
            raise GetTweetError(id=status_id, error=e)

    def __is_reply_to_me(self, user_id):
        return user_id == API.me().id

    def __handle_isbn(self, isbn):
        edition = InternetArchive.get_edition(isbn)
        if edition:
            if edition.get("availability"):
                return Tweet.edition_available(self.mention, edition)

            work = InternetArchive.find_available_work(edition)
            if work:
                return Tweet.work_available(self.mention, work)
            return Tweet.edition_unavailable(self.mention, edition)

    def run(self):
        try:
            isbns = ISBNFinder.find_isbns(self.mention.text)
            if not isbns and self.mention.in_reply_to_status_id: # no isbn found in tweet. Check the parent tweet
                parent_status_id = self.mention.in_reply_to_status_id
                parent_tweet = self.__get_tweet(parent_status_id)
                logging.info("PARENT: " + parent_tweet.full_text.replace("\n", " "))
                isbns = ISBNFinder.find_isbns(parent_tweet.full_text) # for some reason there is a ".text" and ".full_text" within tweepy Status obj
                if not isbns and self.__is_reply_to_me(parent_tweet.user.id):
                    # is a reply to me, don't answer
                    logging.info("RESPONSE: not replying")
                    return
            if isbns:
                logging.info("ISBN: " + str(isbns))
                for isbn in isbns:
                    try:
                        self.__handle_isbn(isbn)
                    except (GetEditionError, FindAvailableWorkError, SendTweetError) as custom_err:
                        logging.warning(custom_err)
                        continue 
                    except Exception as e:
                        logging.exception(e)
                        continue
            else:
                Tweet.edition_not_found(self.mention)
        except (FindISBNError, GetTweetError) as custom_err:
            logging.critical(custom_err)
            try:
                Tweet.internal_error(self.mention)
            except SendTweetError as send_tweet_error:
                logging.critical(send_tweet_error)


class Tweet:
    @staticmethod
    def _tweet(mention, message, debug=False):
        if not mention.user.screen_name or not mention.id:
            raise SendTweetError(mention=mention, error="Given mention is missing either a screen name or a status ID")
        msg = "Hi 👋 @%s %s" % (mention.user.screen_name, message)
        logging.info("RESPONSE: " + msg.replace("\n", " "))
        if not debug:     
            try:
                LOCK.acquire()
                API.update_status(
                    msg,
                    in_reply_to_status_id=mention.id,
                    auto_populate_reply_metadata=True
                )
                LOCK.release()
            except Exception as e:
                raise SendTweetError(mention=mention, message=msg, error=e)
        else:
            LOCK.acquire()
            print(msg.replace("\n", " "))
            LOCK.release()

    @classmethod
    def edition_available(cls, mention, edition):
        action = READ_OPTIONS[edition.get("availability")]
        cls._tweet(
            mention,
            "you're in luck. " +
            "This book appears to be %sable " % action +
            "on @openlibrary: " +
            "%s/isbn/%s" % (InternetArchive.OL_URL, edition.get("isbn"))
        )

    @classmethod
    def work_available(cls, mention, work):
        cls._tweet(
            mention,
            "this exact edition doesn't appear to be available, "
            "however it seems a similar edition may be: " +
            "https://openlibrary.org/work/" + work.get('openlibrary_work')
        )

    @classmethod
    def edition_unavailable(cls, mention, edition):
        cls._tweet(
            mention,
            "this book doesn't appear to have a readable option yet, " +
            "however you can still add it to your " +
            "Want To Read list here: " +
            "%s/isbn/%s" % (InternetArchive.OL_URL, edition.get("isbn"))
        )

    @classmethod
    def edition_not_found(cls, mention):
        cls._tweet(
            mention,
            "sorry, I was unable to spot any books! " +
            "Learn more about how I work here: " +
            "https://github.com/internetarchive/openlibrary-bots" +
            "\nIn short, I need an ISBN10, ISBN13, or Amazon link"
        )

    @classmethod
    def internal_error(cls, mention):
        cls._tweet(
            mention,
            "Woops, something broke over here! " +
            "Learn more about how I work here: " +
            "https://github.com/internetarchive/openlibrary-bots" +
            "\nIn short, I need an ISBN10, ISBN13, or Amazon Link"
        )

if __name__ == "__main__":
    print("(*) Authenticating...")
    dotenv.load_dotenv()
    if not os.environ.get('CONSUMER_KEY') or not os.environ.get('CONSUMER_SECRET') or not os.environ.get('ACCESS_TOKEN') or not os.environ.get('ACCESS_TOKEN_SECRET'):
        raise TweepyAuthenticationError(error="Missing .env file or missing necessary keys for authentication")
    auth = tweepy.OAuthHandler(
        os.environ.get('CONSUMER_KEY'),
        os.environ.get('CONSUMER_SECRET')
    )
    auth.set_access_token(
        os.environ.get('ACCESS_TOKEN'),
        os.environ.get('ACCESS_TOKEN_SECRET')
    )
    API = tweepy.API(auth, wait_on_rate_limit=True)
    print("(*) Authenticated!")
    print("(*) Setting up logger")
    logging.basicConfig(filename=LOG_FILE, filemode='a', level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')   
    print("(*) Listening...")
    bot = tweepy.Stream(auth = API.auth, listener=BorrowBot()) 
    bot.filter(track=[TWITTER_BOT_NAME])


