# -*- coding: utf-8 -*-
# Akibapass - Watch videos from the german anime platform Akibapass.de on Kodi.
# Copyright (C) 2016 - 2017 MrKrabat
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

import time
import socket

import xbmc


header = "HTTP/1.1 200 OK\nContent-Type: application/vnd.apple.mpegurl; charset=utf-8\n\n"

def streamprovider(m3u8):
    """Server returning manifest to kodi
    """
    try:
        # create listening socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 10147))
        sock.listen(1)
        sock.setblocking(0)
    except socket.error:
        # unable to listen on port
        xbmc.log("[SERVICE] Akibapass: Failed listening on port 10147", xbmc.LOGFATAL)
        return

    timer   = time.time() + 10
    counter = 0
    while (time.time() < timer) and (counter < 3):
        xbmc.sleep(30)
        try:
            # wait for connection
            connection, client_address = sock.accept()
            try:
                # wait for request
                connection.settimeout(10.0)
                data = connection.recv(4096).rstrip()

                # send m3u8
                connection.sendall(header + m3u8 + "\n")
                counter = counter + 1
            finally:
                # close connection
                connection.close()
        except socket.error:
            # continue if no connection
            pass

    # close socket
    sock.close()
