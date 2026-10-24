#!/usr/bin/env python3
"""Send one QMP command to a running VM and print the result as JSON.

Usage: qmp.py SOCKET COMMAND [JSON_ARGUMENTS]
Example: qmp.py vm/qmp.sock screendump '{"filename": "/tmp/s.png", "format": "png"}'
"""
import json
import socket
import sys


def call(sock_path, command, arguments=None):
    with socket.socket(socket.AF_UNIX) as s:
        s.connect(sock_path)
        f = s.makefile('rw')
        json.loads(f.readline())  # greeting
        for msg in ({'execute': 'qmp_capabilities'},
                    {'execute': command, **({'arguments': arguments} if arguments else {})}):
            f.write(json.dumps(msg) + '\n')
            f.flush()
            while True:
                reply = json.loads(f.readline())
                if 'event' not in reply:
                    break
            if 'error' in reply:
                sys.exit(f"qmp {msg['execute']}: {reply['error'].get('desc', reply['error'])}")
        return reply.get('return')


if __name__ == '__main__':
    if len(sys.argv) not in (3, 4):
        sys.exit(__doc__)
    args = json.loads(sys.argv[3]) if len(sys.argv) == 4 else None
    print(json.dumps(call(sys.argv[1], sys.argv[2], args)))
