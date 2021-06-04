class Error(Exception):
    pass

class TweepyAuthenticationError(Error):
    def __init__(self, error=None):
        self.error = error

    def __str__(self):
        return "{0}: Failed to Authenticate with Twitter through Tweepy >> {1}".format(type(self).__name__, self.error)

class GoodreadsError(Error):
    def __init__(self, url=None, error=None):
        self.url=url
        self.error=error

    def __str__(self):
        return "{0}: Failed to scrape url '{1}' >> {2}".format(type(self).__name__, self.url, self.error)


class AmazonError(Error):
    def __init__(self, url=None, error=None):
        self.url = url
        self.error = error

    def __str__(self):
        return "{0}: Failed to scrape url '{1}' >> {2}".format(type(self).__name__, self.url, self.error)


class FindISBNError(Error):
    def __init__(self, text=None, error=None):
        self.text = text
        self.error = error

    def __str__(self):
        return "{0}: text='{1}' >> {2}".format(type(self).__name__, self.text, self.error)


class GetTweetError(Error):
    def __init__(self, id=None, error=None):
        self.id = id
        self.error = error

    def __str__(self):
        return "{0}: Failed to get tweet with ID '{1}' >> {2}".format(type(self).__name__, self.id, self.error)


class GetEditionError(Error):
    def __init__(self, isbn=None, error=None):
        self.isbn = isbn
        self.error = error

    def __str__(self):
        return "{0}: Failed to get edition with isbn '{1}' >> {2}".format(type(self).__name__, self.isbn, self.error)


class GetAvailabilityError(Error):
    def __init__(self, identifier=None, error=None):
        self.identifier = identifier
        self.error = error

    def __str__(self):
        return "{0}: Failed to get availability with identifier '{1}' >> {2}".format(type(self).__name__, self.identifier, self.error)


class FindAvailableWorkError(Error):
    def __init__(self, book=None, error=None):
        self.book = book
        self.error = error

    def __str__(self):
        return "{0}: Failed to get book '{1}' >> {2}".format(type(self).__name__, self.book, self.error)


class SendTweetError(Error):
    def __init__(self, mention=None, message=None, error=None):
        self.mention = mention
        self.message = message
        self.error = error

    def __str__(self):
        if not self.mention.user.screen_name or not self.mention.id:
            return "{0}: {1}".format(type(self).__name__, self.error)
        return "{0}: Failed to send tweet '{1}' with mention id '{2}' >> {3}".format(type(self).__name__, self.message, self.mention.id, self.error)   