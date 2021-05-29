import isbnlib
import re
import requests
import datetime
from TwitterBotErrors import FindISBNError, GoodreadsError, AmazonError, GetEditionError, GetAvailabilityError, FindAvailableWorkError
import traceback

ERROR_LOGS = "./logs/error_logs.txt"

class ISBNFinder:

    SERVICES = ("amazon", "goodreads")

    @staticmethod
    def amazon(url):
        try:
            return (
                re.findall("/dp/([0-9X]{10})/?", url) or
                re.findall("/product/([0-9X]{10})/?", url)
            )
        except Exception as e:
            raise AmazonError(url=url, error=e)

    @staticmethod
    def goodreads(url):
        try:
            if re.findall("/book/show/([0-9]+)", url):
                return re.findall("ISBN13.*>([0-9X-]+)", requests.get(url).text)
            return []
        except Exception as e:
            raise GoodreadsError(url=url, error=e)

    @classmethod
    def find_isbns(cls, text):
        try:
            isbns = []
            for token in text.split():
                try:
                    if token.startswith("http"):
                        # this needs to be recursive to get root url
                        try:
                            url = requests.head(token).headers.get("Location") # if is redirect url such as bitly
                            if not url: 
                                url = token
                        except:
                            url = token

                        for service_name in cls.SERVICES:
                            try:
                                _isbns = getattr(cls, service_name)(url)
                                isbns.extend(_isbns)
                            except (GoodreadsError, AmazonError) as custom_err:
                                Logger.log_error(filename=ERROR_LOGS, message=custom_err)
                                continue
                            except Exception:
                                Logger.log_error(filename=ERROR_LOGS, message=traceback.format_exc())
                                continue
                    else:
                        isbns.extend(isbnlib.get_isbnlike(token, level="normal"))
                except Exception as e:
                    raise e
            return [isbnlib.canonical(isbn) for isbn in isbns
                    if isbnlib.is_isbn10(isbn) or isbnlib.is_isbn13(isbn)]    
        except Exception as e:
            raise FindISBNError(text=text, error=e)


class InternetArchive:

    IA_URL = "https://archive.org"
    OL_URL = "https://openlibrary.org"
    OL_DEV = "https://dev.openlibrary.org"
    MODES = ["is_readable", "is_lendable", "is_printdisabled"]

    @classmethod
    def get_edition(cls, isbn):
        try:
            ed = requests.get("%s/isbn/%s.json" % (cls.OL_URL, isbn)).json()
            ed["availability"] = ed and ed.get("ocaid") and cls.get_availability(ed["ocaid"])
            ed["isbn"] = ed and isbn
            return ed
        except Exception as e:
            raise GetEditionError(isbn=isbn, error=e)

    @classmethod
    def get_availability(cls, identifier):
        try:
            url = "%s/services/loans/loan/" % cls.IA_URL
            status = requests.get("%s?&action=availability&identifier=%s" % (
                url, identifier)).json().get("lending_status")
            for mode in cls.MODES:
                if status.get(mode):
                    return mode
        except Exception as e:
            raise GetAvailabilityError(identifier=identifier, error=e)

    @classmethod
    def find_available_work(cls, book):
        try:
            url = "%s/advancedsearch.php" % cls.IA_URL
            work_id = book["works"][0]["key"].split("/")[-1]
            query = (
                "openlibrary_work:%s AND" % work_id +
                "(lending___is_lendable:true OR" +
                " lending___is_readable:true OR" +
                " lending___is_printdisabled:true" +
                ")"
            )
            params = [
                ("q", query),
                ("fl[]", "identifier"),
                ("fl[]", "openlibrary_work"),
                ("fl[]", "lending___is_lendable"),
                ("fl[]", "lending___is_readable"),
                ("fl[]", "lending___is_printdisabled"),
                ("rows", "50"),
                ("page", "1"),
                ("output", "json")
            ]
            matches = requests.get(url, params=params).json()
            if matches and matches["response"]["docs"]:
                books = matches["response"]["docs"]
                return next(book for book in books if book.get("openlibrary_work"))
        except Exception as e:
            raise FindAvailableWorkError(book=book, error=e)


class Logger:

    @staticmethod
    def log_tweet(filename, original_mention, tweet):
        f = open(filename, "a")
        f.write(str(datetime.datetime.now()) + " | ")
        f.write(str(original_mention.replace("\n", " ")) + " | ")
        f.write(str(tweet.replace("\n", " ")) + "\n")
        f.close()
        
    @staticmethod
    def log_error(filename, message):
        f = open(filename, "a")
        f.write(str(datetime.datetime.now()) + " | ")
        f.write(str(message) + "\n")
        f.close()
