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
import json
try:
    from urllib import unquote, urlencode
except ImportError:
    from urllib.parse import unquote, urlencode

import xbmc
import xbmcgui

import inputstreamhelper
from login import getCookie


def log(args, msg, lvl=xbmc.LOGDEBUG):
    xbmc.log("[PLUGIN] {0}: {1}".format(args._addonname, msg), lvl)


def errdlg(args):
    xbmcgui.Dialog().ok(args._addonname, args._addon.getLocalizedString(30044))


def parse_stream_config(s, prefix):
    """Make JSON format: quote keys, replace single quotes with double quotes
    """
    i = s.find(prefix)
    if i < 0: return {}
    i += len(prefix)
    l = len(s)
    n = 1
    r = ""
    q = False
    ms = re.compile(r"(?P<q>['\"])(.*?)(?<!\\)(?P=q)")
    while i < l and n:
        c = s[i]
        if c.isalnum():
            if not q:
                r += "\""
                q = True
            r += c
        else:
            if q:
                r += "\""
                q = False
            if c in "\"'":
                m = ms.match(s, i)
                if m:
                    r += "\"" + m.group(2) + "\""
                    i = m.end()
                    if i >= l: break
                    c = s[i]
            elif c == "{": n += 1
            elif c == "}": n -= 1
            if not c in " \t\n\r": r += c
        i += 1
    return json.loads("{" + r)


def enc(s):
    """Remove after python3 migration
    """
    try:
        return s.encode("utf-8") if isinstance(s, unicode) else s
    except NameError:
        return s


def get_stream_params_from_json(d):
    """Get stream parameters from JSON
    """
    r = {}
    r['url'] = enc(d[u'file'])
    r['proto'] = enc(d[u'type'])
    drm = d.get(u'drm', None)
    if not drm:
        r['drm'] = None
        return r
    if u'widevine' in drm:
        r['drm'] = 'widevine'
        drm = drm[u'widevine']
    else:
        r['drm'], drm = next(iter(drm.items()))
        r['drm'] = enc(r['drm'])
    r['key'] = enc(drm[u'url'])
    r['headers'] = {enc(h[u'name']): enc(h[u'value']) for h in drm.get(u'headers', [])}
    return r


def get_stream_params_fallback(s):
    """Get stream parameters from HTML
    """
    try:
        r = {}
        s = re.search(r"jwplayer\(\"jwplayer-container\"\).setup\({(.+?)}\);", s, re.DOTALL).group(1)
        r['url'] = enc(re.search(r"file:\s*(?P<q>['\"])(.+?)(?<!\\)(?P=q),", s).group(2))
        r['proto'] = enc(re.search(r"type:\s*(?P<q>['\"])(.+?)(?<!\\)(?P=q),", s).group(2))
        if re.search(r"drm:\s*{", s):
            r['drm'] = "widevine"
            r['key'] = enc(re.search(r"url:\s*(?P<q>['\"])(.+?)(?<!\\)(?P=q),", s).group(2))
            r['headers'] = {"Authorization": enc(re.search(r"value:\s*(?P<q>['\"])(.+?)(?<!\\)(?P=q)", s).group(2))}
        else:
            r['drm'] = None
        return r
    except:
        return None


def getStreamParams(args, s):
    """Get stream parameters and check with inputstreamhelper
    """
    try:
        r = get_stream_params_from_json(parse_stream_config(s.replace("autostart: (autoplay) ? \"true\" : \"false\"", "autostart: \"false\""), "jwplayer(\"jwplayer-container\").setup({"))
    except:
        log(args, "Error parsing JWPlayer config, trying old method", xbmc.LOGNOTICE)
        r = get_stream_params_fallback(s)
    if not r:
        log(args, "Invalid JWPlayer config", xbmc.LOGERROR)
        errdlg(args)
        return None
    log(args, "Stream proto '{0}' drm '{1}'".format(r['proto'], r['drm']), xbmc.LOGDEBUG)
    if not r['url'].startswith("http"): r['url'] = "https://www.wakanim.tv" + r['url']
    if r['proto'] == "hls":
        return {'legacy': True, 'url': r['url'] + getCookie(args), 'content-type': "application/vnd.apple.mpegurl", 'properties': {}}
    if r['proto'] == "dash":
        m = re.search(r"manifest=(.+?)\&", r['url'])
        if m: r['url'] = unquote(m.group(1))
        r['proto'] = "mpd"
        r['content-type'] = "application/dash+xml"
    else:
        log(args, "Unknown stream protocol '{0}'".format(r['proto']), xbmc.LOGNOTICE)
    if r['drm'] == "widevine":
        r['drm'] = "com.widevine.alpha"
    else:
        log(args, "Unknown stream license type '{0}'".format(r['drm']), xbmc.LOGNOTICE)
    try:
        if not inputstreamhelper.Helper(r['proto'], r['drm']).check_inputstream():
            log(args, "InputStreamHelper: check stream failed", xbmc.LOGERROR)
            return None
    except Exception, e:
        log(args, "InputStreamHelper: %s" % e, xbmc.LOGERROR)
        errdlg(args)
        return None
    a = "inputstream.adaptive"
    p = {'inputstreamaddon': a, a+'.stream_headers': getCookie(args)[1:], a+'.manifest_type': r['proto']}
    if r['drm']:
        p[a+'.license_type'] = r['drm']
        h = ""
        for k,v in list(r['headers'].items()): h += urlencode({k: v}) + "&"
        h += "User-Agent=Mozilla%2F5.0%20%28Windows%20NT%2010.0%3B%20Win64%3B%20x64%29%20AppleWebKit%2F537.36%20%28KHTML%2C%20like%20Gecko%29%20Chrome%2F60.0.3112.113%20Safari%2F537.36&Content-Type=text%2Fxml&SOAPAction=http%3A%2F%2Fschemas.microsoft.com%2FDRM%2F2007%2F03%2Fprotocols%2FAcquireLicense|R{SSM}|"
        p[a+'.license_key'] = r['key'] + "|" + h
    return {'legacy': False, 'url': r['url'], 'content-type': r.get('content-type', None), 'properties': p}

