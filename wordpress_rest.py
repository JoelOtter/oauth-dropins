"""WordPress.com OAuth drop-in.

API docs:
https://developer.wordpress.com/docs/api/
https://developer.wordpress.com/docs/oauth2/

Note that unlike Blogger and Tumblr, WordPress.com's OAuth tokens are *per
blog*. It asks you which blog to use on its authorization page.
"""

import json
import logging
import urllib
import urllib2

import appengine_config
import handlers
from webutil import util

from google.appengine.ext import db
import webapp2


assert (appengine_config.WORDPRESS_CLIENT_ID and
        appengine_config.WORDPRESS_CLIENT_SECRET), (
        "Please fill in the wordpress_client_id and wordpress_client_secret "
        "files in your app's root directory.")


# URL templates. Can't (easily) use urllib.urlencode() because I want to keep
# the %(...)s placeholders as is and fill them in later in code.
GET_AUTH_CODE_URL = str('&'.join((
    'https://public-api.wordpress.com/oauth2/authorize?',
    'scope=',  # wordpress doesn't seem to use scope
    'client_id=%(client_id)s',
    # redirect_uri here must be the same in the access token request!
    'redirect_uri=%(host_url)s%(callback_path)s',
    'response_type=code',
    )))
GET_ACCESS_TOKEN_URL = 'https://public-api.wordpress.com/oauth2/token'


class WordPressAuth(db.Model):
  """An authenticated WordPress user or page.

  Provides methods that return information about this user (or page) and make
  OAuth-signed requests to the WordPress REST API. Stores OAuth credentials in
  the datastore. See models.BaseAuth for usage details.

  WordPress-specific details: implements urlopen() but not http() or api(). The
  key name is the blog hostname.
  """
  blog_id = db.StringProperty(required=True)
  access_token = db.StringProperty(required=True)

  def site_name(self):
    return 'WordPress'

  def user_display_name(self):
    """Returns the blog hostname.
    """
    return self.key().name()

  def urlopen(self, url, **kwargs):
    """Wraps urllib2.urlopen() and adds OAuth credentials to the request.
    """
    return BaseAuth.urlopen_access_token(url, self.access_token, **kwargs)


class StartHandler(handlers.StartHandler):
  """Starts WordPress auth. Requests an auth code and expects a redirect back.
  """

  def redirect_url(self, state=''):
    # wordpress.com doesn't let you use an oauth redirect URL with "local" or
    # "localhost" anywhere in it. :/ had to use my.dev.com and put this in
    # /etc/hosts:   127.0.0.1 my.dev.com
    host = 'http://my.dev.com:8080' if appengine_config.DEBUG else self.host_url

    # TODO: CSRF protection
    return GET_AUTH_CODE_URL % {
      'client_id': appengine_config.WORDPRESS_CLIENT_ID,
      'host_url': host,
      'callback_path': self.to_path,
      }


class CallbackHandler(handlers.CallbackHandler):
  """The OAuth callback. Fetches an access token and stores it.
  """

  def get(self):
    auth_code = self.request.get('code')
    assert auth_code

    host = 'http://my.dev.com:8080' if appengine_config.DEBUG else self.host_url
    data = {
      'code': auth_code,
      'client_id': appengine_config.WORDPRESS_CLIENT_ID,
      'client_secret': appengine_config.WORDPRESS_CLIENT_SECRET,
      # redirect_uri here must be the same in the oauth code request!
      # (the value here doesn't actually matter since it's requested server side.)
      'redirect_uri': self.request.path_url,
      'grant_type': 'authorization_code',
      }
    logging.debug('Fetching %s with %r', GET_ACCESS_TOKEN_URL, data)
    resp = urllib2.urlopen(GET_ACCESS_TOKEN_URL,
                           data=urllib.urlencode(data)).read()
    logging.debug('Access token response: %s', resp)

    try:
      resp = json.loads(resp)
      blog_id = resp['blog_id']
      blog_domain = util.domain_from_link(resp['blog_url'])
      access_token = resp['access_token']
    except:
      logging.exception('Could not decode JSON')
      raise

    auth = WordPressAuth(key_name=blog_domain,
                         blog_id=blog_id,
                         access_token=access_token)
    auth.save()
    self.finish(auth, state=self.request.get('state'))
