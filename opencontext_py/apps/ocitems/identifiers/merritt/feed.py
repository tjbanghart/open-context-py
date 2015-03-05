import feedparser
import requests
from time import sleep
from time import mktime
from datetime import datetime
from django.conf import settings
from opencontext_py.libs.general import LastUpdatedOrderedDict
from opencontext_py.libs.generalapi import GeneralAPI


class MerrittFeed():
    """ Interacts with the tDAR API
        First use-case is to relate DINAA trinomials with
        tDAR keywords
    """
    ATOM_BASE_URL = 'https://merritt.cdlib.org/object/recent.atom?collection=ark:/13030/m5wd3xhm'
    SLEEP_TIME = .5

    def __init__(self):
        self.request_error = False
        self.next_page = False
        self.delay_before_request = self.SLEEP_TIME

    def get_ids_from_merritt_feed(self, feed_url=False):
        """ gets a merritt feed, parses it,
            and returns a list of identifiers
        """
        if feed_url is False:
            feed_url = self.ATOM_BASE_URL
        feed = self.get_merritt_feed(feed_url)
        identifiers = self.get_ids(feed)
        return identifiers

    def get_ids(self, feed):
        """ gets identifiers from a Merritt feed """
        output = []
        if feed is not False:
            for entry in feed.entries:
                ids = {'stable_id': entry.id,
                       'archived': datetime.fromtimestamp(mktime(entry.updated_parsed))}
                if len(entry.links) > 0:
                    for link in entry.links:
                        if link['rel'] == 'alternate' \
                           and settings.CANONICAL_HOST in link['href']:
                            ids['id'] = link['href']
                            output.append(ids)
                            break
        return output

    def get_merritt_feed(self, feed_url=False):
        """ gets a feed from Merritt """
        if feed_url is False:
            feed_url = self.ATOM_BASE_URL
        if self.delay_before_request > 0:
            # default to sleep BEFORE a request is sent, to
            # give the remote service a break.
            sleep(self.delay_before_request)
        feed = feedparser.parse(feed_url)
        if feed.bozo == 1 \
           or feed.status >= 400:
            feed = False
        else:
            if len(feed.feed.links) > 0:
                for link in feed.feed.links:
                    if link['rel'] == 'next' \
                       and link['type'] == 'application/atom+xml':
                        self.next_page = link['href']
                        break
        return feed
