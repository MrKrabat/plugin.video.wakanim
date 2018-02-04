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
import cookielib
import urllib
import urllib2

import xbmc
import xbmcgui

def loadCookies(args):
    """Load cookies and install urllib2 opener
    """
    # create cookie path
    cookiepath = os.path.join(
        xbmc.translatePath(args._addon.getAddonInfo("profile")).decode("utf-8"),
        "cookies.lwp")

    # create cookiejar
    cj = cookielib.LWPCookieJar()
    args._cj = cj

    # lets urllib2 handle cookies
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
    opener.addheaders = [("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36")]
    opener.addheaders = [("Accept-Charset", "utf-8")]
    urllib2.install_opener(opener)

    # load cookies
    try:
        cj.load(cookiepath, ignore_discard=True)
    except IOError:
        # cookie file does not exist
        pass

def saveCookies(args):
    args._cj.save(os.path.join(xbmc.translatePath(args._addon.getAddonInfo("profile")).decode("utf-8"), "cookies.lwp"), ignore_discard=True)


def check_loggedin(html):
    return 'header-main_user_name' in html


def getHTML(args, url, data=None):
    """Load HTML and login if necessary
    """
    response = urllib2.urlopen(url, data)
    html = response.read()

    if check_loggedin(html):
        return html

    login_url = "https://www.wakanim.tv/" + args._country + "/v2/account/login?ReturnUrl=" + urllib.quote_plus(url.replace("https://www.wakanim.tv", ''))
    username = args._addon.getSetting("wakanim_username")
    password = args._addon.getSetting("wakanim_password")

    # build POST data
    post_data = urllib.urlencode({"username": username,
                                  "password": password,
                                  "remember": "1"})

    # POST to login page
    response = urllib2.urlopen(login_url, post_data)

    if data:
        response = urllib2.urlopen(url, data)
    # check for login string
    html = response.read()

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
    # create cookie path
    cookiepath = os.path.join(
        xbmc.translatePath(args._addon.getAddonInfo("profile")).decode("utf-8"),
        "cookies.lwp")
    # save session to disk
    args._cj.save(cookiepath, ignore_discard=True)

    ret = ""
    for cookie in args._cj:
        ret += urllib.urlencode({cookie.name: cookie.value}) + ";"

    return "|User-Agent=Mozilla%2F5.0%20%28Windows%20NT%2010.0%3B%20Win64%3B%20x64%29%20AppleWebKit%2F537.36%20%28KHTML%2C%20like%20Gecko%29%20Chrome%2F60.0.3112.113%20Safari%2F537.36&Cookie=" + ret[:-1]
