# -*- coding: utf-8 -*-
# Wakanim - Watch videos from the german anime platform Wakanim.tv on Kodi.
# Copyright (C) 2017 MrKrabat
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import cgi
try:
    from urllib import urlencode, quote_plus
except ImportError:
    from urllib.parse import urlencode, quote_plus
try:
    from urllib2 import urlopen, build_opener, HTTPCookieProcessor, install_opener
except ImportError:
    from urllib.request import urlopen, build_opener, HTTPCookieProcessor, install_opener
try:
    from cookielib import LWPCookieJar
except ImportError:
    from http.cookiejar import LWPCookieJar

import xbmc
import xbmcgui

def get_cookie_path(args):
    """Get cookie file path
    """
    profile_path = xbmc.translatePath(args._addon.getAddonInfo("profile"))
    try:
        # python2
        return os.path.join(profile_path.decode("utf-8"), u"cookies.lwp")
    except AttributeError:
        # python3
        return os.path.join(profile_path, "cookies.lwp")

def loadCookies(args):
    """Load cookies and install urllib2 opener
    """
    # create cookiejar
    cj = LWPCookieJar()
    args._cj = cj

    # lets urllib2 handle cookies
    opener = build_opener(HTTPCookieProcessor(cj))
    opener.addheaders = [("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36")]
    opener.addheaders = [("Accept-Charset", "utf-8")]
    install_opener(opener)

    # load cookies
    try:
        cj.load(get_cookie_path(args), ignore_discard=True)
    except IOError:
        # cookie file does not exist
        pass

def saveCookies(args):
    """Save cookies
    """
    args._cj.save(get_cookie_path(args), ignore_discard=True)


def check_loggedin(html):
    """Check if user logged in
    """
    return u'header-main_user_name' in html


def get_html_charset(r):
    """response.headers.get_content_charset() replacement to work on python2 and python3
    """
    _, p = cgi.parse_header(r.headers.get("Content-Type", ""))
    return p.get("charset", "utf-8")

def get_html(r):
    """Load HTML in Unicode
    """
    return r.read().decode(get_html_charset(r))


def getHTML(args, url, data=None):
    """Load HTML and login if necessary
    """
    response = urlopen(url, data)
    html = get_html(response)

    if check_loggedin(html):
        return html

    login_url = "https://www.wakanim.tv/" + args._country + "/v2/account/login?ReturnUrl=" + quote_plus(url.replace("https://www.wakanim.tv", ''))
    username = args._addon.getSetting("wakanim_username")
    password = args._addon.getSetting("wakanim_password")

    # build POST data
    post_data = urlencode({"username": username,
                           "password": password,
                           "remember": "1"})

    # POST to login page
    response = urlopen(login_url, post_data.encode(get_html_charset(response)))

    if data:
        response = urlopen(url, data)
    # check for login string
    html = get_html(response)

    if check_loggedin(html):
        # save session to disk
        saveCookies(args)
        return html
    else:
        xbmc.log("[PLUGIN] %s: Login failed" % args._addonname, xbmc.LOGERROR)
        xbmcgui.Dialog().ok(args._addonname, args._addon.getLocalizedString(30040))
        return ""


def getCookie(args):
    """Returns all cookies as string and urlencoded
    """
    # save session to disk
    saveCookies(args)

    ret = ""
    for cookie in args._cj:
        ret += urlencode({cookie.name: cookie.value}) + ";"

    return "|User-Agent=Mozilla%2F5.0%20%28Windows%20NT%2010.0%3B%20Win64%3B%20x64%29%20AppleWebKit%2F537.36%20%28KHTML%2C%20like%20Gecko%29%20Chrome%2F60.0.3112.113%20Safari%2F537.36&Cookie=" + ret[:-1]
