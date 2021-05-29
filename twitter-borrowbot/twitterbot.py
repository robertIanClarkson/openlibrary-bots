#-*- encoding: utf-8 -*-
import os
import time
import tweepy
from dotenv import load_dotenv

from services import InternetArchive, ISBNFinder, Logger
from TwitterBotErrors import TweepyAuthenticationError, FileIOError, LastSeenIDError, GetMentionsError, TooManyMentionsError, FindISBNError, GetTweetError, GetEditionError, FindAvailableWorkError, SendTweetError

ACTIONS = ('read', 'borrow', 'preview')
READ_OPTIONS = dict(zip(InternetArchive.MODES, ACTIONS))
BOT_NAME = None
BOT_ID = None
STATE_FILE = 'last_seen_id.txt'
SLEEP_TIME = 15 # in seconds 
MENTION_LIMIT = 128 

LOGGER = Logger("./logs/tweet_logs.txt", "./logs/error_logs.txt")

API = None

def authenticate():
    load_dotenv()
    if not os.environ.get('CONSUMER_KEY') or not os.environ.get('CONSUMER_SECRET') or not os.environ.get('ACCESS_TOKEN') or not os.environ.get('ACCESS_TOKEN_SECRET'):
        raise TweepyAuthenticationError(error="Missing .env file or missing necessary keys for authentication")
    try:
        # Authenticate
        auth = tweepy.OAuthHandler(
            os.environ.get('CONSUMER_KEY'),
            os.environ.get('CONSUMER_SECRET')
        )
        auth.set_access_token(
            os.environ.get('ACCESS_TOKEN'),
            os.environ.get('ACCESS_TOKEN_SECRET')
        )
        global API
        API = tweepy.API(auth, wait_on_rate_limit=True)
        global BOT_NAME
        BOT_NAME = '@' + API.me().screen_name # test authentication & set BOT_NAME
        global BOT_ID
        BOT_ID = API.me().id
    except Exception as e:
        raise TweepyAuthenticationError(error=e)

class Tweet:
    @staticmethod
    def _tweet(mention, message, debug=False):
        if not mention.user.screen_name or not mention.id:
            raise SendTweetError(mention=mention, error="Given mention is missing either a screen name or a status ID")
        msg = "Hi 👋 @%s %s" % (mention.user.screen_name, message)
        if not debug:               
            try:
                API.update_status(
                    msg,
                    in_reply_to_status_id=mention.id,
                    auto_populate_reply_metadata=True
                )
            except Exception as e:
                raise SendTweetError(mention=mention, msg=msg, error=e)
        else:
            print(msg)
        LOGGER.log_tweet(msg)

    @classmethod
    def edition_available(cls, mention, edition):
        action = READ_OPTIONS[edition.get("availability")]
        print('Replying: Edition %sable' % action)
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
        # print('Replying: Book Not found')
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

def get_last_seen_id():
    try:
        with open(STATE_FILE, 'r') as fin:
            last_seen_id = fin.read().strip()
    except Exception as e:
        raise FileIOError(file=STATE_FILE, error=e)
    else:
        if len(last_seen_id) < 19 or not last_seen_id.isdecimal():
            raise LastSeenIDError(file=STATE_FILE, id=last_seen_id)
        return int(last_seen_id)

def set_last_seen_id(mention):
    try:
        with open(STATE_FILE, 'w') as fout:
            fout.write(str(mention.id))
    except Exception as e:
        raise FileIOError(file=STATE_FILE, write=mention.id, error=e)

def get_tweet(status_id):
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

def get_latest_mentions(since=None):
    try:
        since = since or get_last_seen_id()
        mentions = API.mentions_timeline(since, tweet_mode="extended")
        if len(mentions) >= MENTION_LIMIT:
            raise TooManyMentionsError(since=since, length=len(mentions), limit=MENTION_LIMIT)
    except (FileIOError, LastSeenIDError) as e:
        # don't proceed. We don't want to end up replying to the same tweet twice
        raise e
    except TooManyMentionsError as e:
        # Possibly DOS type attack. Handle what we can
        LOGGER.log_error(e)
        return mentions[MENTION_LIMIT:] # MIGHT BE mentions[MENTION_LIMIT:] FIFO vs LIFO
    except Exception as e:
        raise GetMentionsError(since=since, error=e)

def is_reply_to_me(mention):
    return mention.in_reply_to_status_id == BOT_ID

def handle_isbn(mention, isbn):
    try:
        edition = InternetArchive.get_edition(isbn)
        if edition:
            if edition.get("availability"):
                return Tweet.edition_available(mention, edition)

            work = InternetArchive.find_available_work(edition)
            if work:
                return Tweet.work_available(mention, work)
            return Tweet.edition_unavailable(mention, edition)
    except GetEditionError:
        pass #failed to get the edition
    except FindAvailableWorkError:
        pass #failed to find available work
    except SendTweetError:
        pass #failed to send tweet

def reply_to_tweets():
    try:
        mentions = get_latest_mentions()
        
        for mention in reversed(mentions):
            try:
                print(str(mention.id) + ': ' + mention.full_text)
                # print(json.dumps(mention._json, indent=2))

                set_last_seen_id(mention)
                
                isbns = ISBNFinder.find_isbns(mention.full_text)
                if not isbns and mention.in_reply_to_status_id: # no isbn found in tweet. Check the parent tweet
                    parent_status_id = mention.in_reply_to_status_id
                    parent_tweet = get_tweet(parent_status_id)
                    isbns = ISBNFinder.find_isbns(parent_tweet.full_text)
                    if not isbns and parent_tweet.user.id == API.me().id: # reply to me
                        print("is reply to me")
                        continue
                if isbns:
                    for isbn in isbns:
                        try:
                            handle_isbn(mention, isbn)
                        except:
                            pass 
                    continue
                Tweet.edition_not_found(mention)
            except FileIOError:
                pass # failed to set last seen id - try again or skip mention
            except FindISBNError:
                pass # ISBN finder failed - try again or skip mention
            except GetTweetError:
                pass # Failed to get the parent tweet - try again or skip mention
    except FileIOError:
        pass # failed to read the last seen ID - Retry
    except LastSeenIDError as e:
        pass # Last seen id doesnt make sense - STOP
    except GetMentionsError:
        pass # Failed to get mentions through Tweepy - Retry


if __name__ == "__main__":
    # authenticate()
    # print("BOT: {0} running...".format(BOT_NAME))
    # print(get_tweet("4.0"))
    # while True:
    #     reply_to_tweets()
    #     time.sleep(SLEEP_TIME)

    print("ISBNS:", ISBNFinder.find_isbns("https://www.goodreads.com/book/show/foobar"))

