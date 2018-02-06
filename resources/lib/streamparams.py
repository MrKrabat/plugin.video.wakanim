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

import re
import urllib
import json

import xbmc
import xbmcgui

import inputstreamhelper
from login import getCookie


def log(args, msg, lvl=xbmc.LOGDEBUG):
    """Log msg to Kodi journal
    """
    xbmc.log("[PLUGIN] %s: %s" % (args._addonname, msg), lvl)


def errdlg(args):
    """Display dialog with "Failed to play video" message
    """
    xbmcgui.Dialog().ok(args._addonname, args._addon.getLocalizedString(30044))


def parse_stream_config(html, prefix):
    """Make JSON from JWPlayer config contents in HTML
       * quote keys: file: "xxx" -> "file": "xxx"
       * replace single quotes with double quotes: "type": 'dash' -> "type": "dash"
       * remove whitespaces
       * parse with json.loads()
       Parameters:
         html: HTML page content
         prefix: text preceeding to JWPlayer config
       Returns JSON object with JWPlayer config
    """
    i = html.find(prefix)
    if i < 0: return {}
    i += len(prefix)
    l = len(html)
    brace_count = 1
    result = ""
    quote_key = False
    # regex to string with single or double quotes
    ms = re.compile(r"(?P<q>['\"])(.*?)(?<!\\)(?P=q)")
    while i < l and brace_count:
        c = html[i]
        if c.isalnum():
            # key: first quote
            if not quote_key:
                result += "\""
                quote_key = True
            result += c
        else:
            # key: second quote
            if quote_key:
                result += "\""
                quote_key = False
            # replace single quotes with double quotes
            if c in "\"'":
                m = ms.match(html, i)
                if m:
                    result += "\"" + m.group(2) + "\""
                    i = m.end()
                    if i >= l:
                        break
                    c = html[i]
            # count braces and stop on last '}'
            elif c == "{":
                brace_count += 1
            elif c == "}":
                brace_count -= 1
            # skip whitespaces
            if not c in " \t\n\r":
                result += c
        i += 1
    return json.loads("{" + result)


def get_stream_params_from_json(data):
    """Get stream parameters from JSON format
       Parameters:
         data: JSON object with JWPlayer config
       Returns dict with following keys:
         'url': stream url
         'proto': stream manifest type - 'hls', 'dash'
         'drm': license type - None, 'widevine', 'playready'
       if drm present:
         'key': license server url
         'headers': additional headers to pass to license server
    """
    result = {}
    result['url'] = data[u'file'].encode("utf-8")
    result['proto'] = data[u'type'].encode("utf-8")
    drm = data.get(u'drm', None)
    if not drm:
        result['drm'] = None
        return result
    if u'widevine' in drm:
        result['drm'] = 'widevine'
        drm = drm[u'widevine']
    else:
        # if no 'widewine' get first license type from drm list
        result['drm'], drm = next(drm.iteritems())
        result['drm'] = result['drm'].encode("utf-8")
    result['key'] = drm[u'url'].encode("utf-8")
    result['headers'] = {h['name'].encode("utf-8"): h['value'].encode("utf-8") for h in drm.get(u'headers', [])}
    return result


def get_stream_params_fallback(html):
    """Get stream parameters from HTML - old method
       Parameters:
         html: HTML page content with JWPlayer config
       Returns the same as get_stream_params_from_json()
    """
    try:
        result = {}
        # get JWPlayer config and search params only in it
        html = re.search(r"jwplayer\(\"jwplayer-container\"\).setup\({(.+?)}\);", html, re.DOTALL).group(1)
        # regex 'key: "value", can process single or double quotes
        result['url'] = re.search(r"file:\s*(?P<q>['\"])(.+?)(?<!\\)(?P=q),", html).group(2)
        result['proto'] = re.search(r"type:\s*(?P<q>['\"])(.+?)(?<!\\)(?P=q),", html).group(2)
        if re.search(r"drm:\s*{", html):
            result['drm'] = "widevine"
            result['key'] = re.search(r"url:\s*(?P<q>['\"])(.+?)(?<!\\)(?P=q),", html).group(2)
            result['headers'] = {"Authorization": re.search(r"value:\s*(?P<q>['\"])(.+?)(?<!\\)(?P=q)", html).group(2)}
        else:
            result['drm'] = None
        return result
    except AttributeError:
        return None


def getStreamParams(args, html):
    """Get stream parameters and check with InputStreamHelper:
       * Parse JWPlayer config using JSON and get stream parameters, fallback to old method in case of parsing errors
       * Check stream parameters with InputStreamHelper
       * Prepare parameters for xbmcgui.ListItem
       Parameters:
         args: plugin args class
         html: HTML page content with JWPlayer config
       Returns dict with following keys:
         'legacy': use Kodi buildin playback (e.g. for HLS streams)
         'url': stream url
         'content-type': Content type (e.g. application/vnd.apple.mpegurl)
         'properties': dict with parameters to pass to xbmcgui.ListItem.setProperty(key, value)
    """
    try:
        # remove stuff that cannot be parsed by JSON parser
        html = html.replace("autostart: (autoplay) ? \"true\" : \"false\"", "autostart: \"false\"")
        # try parse with JSON
        result = get_stream_params_from_json(parse_stream_config(html, "jwplayer(\"jwplayer-container\").setup({"))
    except (ValueError, KeyError):
        log(args, "Error parsing JWPlayer config, trying old method", xbmc.LOGNOTICE)
        # fallback to old method
        result = get_stream_params_fallback(html)
    if not result:
        log(args, "Invalid JWPlayer config", xbmc.LOGERROR)
        errdlg(args)
        return None

    log(args, "Stream proto '%s' drm '%s'" % (result['proto'], result['drm']), xbmc.LOGDEBUG)

    # prepare stream parameters
    if not result['url'].startswith("http"):
        result['url'] = "https://www.wakanim.tv" + result['url']
    if result['proto'] == "hls":
        # play HLS with Kodi buildin playback
        return {'legacy': True, 'url': result['url'] + getCookie(args), 'content-type': "application/vnd.apple.mpegurl", 'properties': {}}
    if result['proto'] == "dash":
        m = re.search(r"manifest=(.+?)\&", result['url'])
        if m: result['url'] = urllib.unquote(m.group(1))
        result['proto'] = "mpd"
        result['content-type'] = "application/dash+xml"
    else:
        log(args, "Unknown stream protocol '%s'" % result['proto'], xbmc.LOGNOTICE)
    if result['drm'] == "widevine":
        result['drm'] = "com.widevine.alpha"
    else:
        log(args, "Unknown stream license type '%s'" % result['drm'], xbmc.LOGNOTICE)

    # check stream parameters with InputStreamHelper
    try:
        if not inputstreamhelper.Helper(result['proto'], result['drm']).check_inputstream():
            log(args, "InputStreamHelper: check stream failed", xbmc.LOGERROR)
            return None
    except inputstreamhelper.Helper.InputStreamException, e:
        log(args, "InputStreamHelper: %s" % e, xbmc.LOGERROR)
        errdlg(args)
        return None

    # prepare parameters for InputStream Adaptive
    a = "inputstream.adaptive"
    params = {'inputstreamaddon': a, a+'.stream_headers': getCookie(args)[1:], a+'.manifest_type': result['proto']}
    if result['drm']:
        params[a+'.license_type'] = result['drm']
        headers = ""
        for k,v in result['headers'].iteritems():
            headers += urllib.urlencode({k: v}) + "&"
        headers += "User-Agent=Mozilla%2F5.0%20%28Windows%20NT%2010.0%3B%20Win64%3B%20x64%29%20AppleWebKit%2F537.36%20%28KHTML%2C%20like%20Gecko%29%20Chrome%2F60.0.3112.113%20Safari%2F537.36&Content-Type=text%2Fxml&SOAPAction=http%3A%2F%2Fschemas.microsoft.com%2FDRM%2F2007%2F03%2Fprotocols%2FAcquireLicense|R{SSM}|"
        params[a+'.license_key'] = result['key'] + "|" + headers
    return {'legacy': False, 'url': result['url'], 'content-type': result.get('content-type', None), 'properties': params}

