# -*- coding: utf-8 -*-

"""
Copyright (C) 2016, Zato Source s.r.o. https://zato.io

Licensed under LGPLv3, see LICENSE.txt for terms and conditions.
"""

from __future__ import absolute_import, division, print_function, unicode_literals

# ZeroMQ
import zmq.green as zmq

# Zato
from zato.common.ipc import IPCEndpoint, Request

# This is needed so that unpickling of requests works
Request = Request

# ################################################################################################################################

class Subscriber(IPCEndpoint):
    """ Listens for incoming IPC messages and invokes callbacks for each one received.
    """
    socket_method = 'connect'
    socket_type = 'sub'

    def __init__(self, on_message_callback, *args, **kwargs):
        self.on_message_callback = on_message_callback
        super(Subscriber, self).__init__(*args, **kwargs)

    def serve_forever(self):
        self.socket.setsockopt(zmq.SUBSCRIBE, b'')

        while self.keep_running:
            self.on_message_callback(self.socket.recv_pyobj())

# ################################################################################################################################
