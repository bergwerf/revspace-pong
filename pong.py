#!/usr/bin/env python

import sys
import socket
import threading
import hashlib
import base64
import array

class ThreadedServer(object):
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))

    def listen(self):
        self.sock.listen(5)
        while True:
            client, address = self.sock.accept()
            client.settimeout(60)
            threading.Thread(target=self.listenToClient, args = (client, address)).start()

    def listenToClient(self, client, address):
        maxHeaderSize = 4096
        while True:
            data = client.recv(maxHeaderSize)
            if data:
                lines = data.split('\r\n')
                for line in lines:
                    if line.startswith('Sec-WebSocket-Key:'):
                        key = line.split(':')[1].lstrip()
                        fstr = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
                        
                        ret = base64.b64encode(hashlib.sha1(key + fstr).digest())
                        client.send(
                            'HTTP/1.1 101 Switching Protocols\r\n' +
                            'Upgrade: websocket\r\n' +
                            'Connection: Upgrade\r\n' +
                            'Sec-WebSocket-Accept: ' + ret + '\r\n' +
                            'Sec-WebSocket-Protocol: chat\r\n\r\n')

                        # We're in WebSocket land now!
                        text = client.recv(7)
                        bytes = array.array('B', text)
                        cmd = bytes[6] ^ bytes[2]
                        

                        break
            else:
                raise error('Client disconnected')

def startSocketServer():
  ThreadedServer('', 8000).listen()

if __name__ == "__main__":
  # Start socket server.
  threading.Thread(target=startSocketServer).start()

  # Keep sending pixel data.
  #while(1):
  #  buf = sys.stdin.read(1920)
  #  sys.stdout.write(buf)
  #  sys.stdout.flush()

