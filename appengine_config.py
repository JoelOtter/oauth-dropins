from oauth_dropins.appengine_config import *

# Suppress warnings. These are duplicated in granary and bridgy; keep them in sync!
import warnings
warnings.filterwarnings('ignore', module='bs4',
                        message='No parser was explicitly specified')
warnings.filterwarnings('ignore',
                        message='URLFetch does not support granular timeout')

# Use lxml for BeautifulSoup explicitly.
from .webutil import util
util.beautifulsoup_parser = 'lxml'

# NDB client
# https://googleapis.dev/python/python-ndb/latest/
# TODO: make thread local?
# https://googleapis.dev/python/python-ndb/latest/migrating.html#setting-up-a-connection
from google.cloud import ndb
ndb_client = ndb.Client()

if DEBUG:
  # HACK! work around that the python 3 ndb lib doesn't support dev_appserver.py
  # https://github.com/googleapis/python-ndb/issues/238
  ndb_client.host = 'localhost:8089'
  ndb_client.secure = False
