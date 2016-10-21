#!/usr/bin/env python

# Doesn't work with Python 3.

import sys
import socket
import threading
import hashlib
import base64
import array
import time

# Game data
ball = list((4, 40))
ballVector = list((0, 0))
ballInterval = 200
ballPrevTime = 0

panes = list((-1, -1))
paneWidth = 8

gameIsOn = False
gameIsOnSince = 0

def turnGameOn():
    global gameIsOn
    global gameIsOnSince

    gameIsOn = True
    gameIsOnSince = int(time.time())

def turnGameOff():
    global gameIsOn

    gameIsOn = False

def fireBall():


def handleCommand(player, cmd):
    '''
    Handle player action.
    '''
    global panes
    global paneWidth

    print('Received command #' + str(cmd) + ' for player #' + str(player))

    if cmd == 114 and panes[player] > 0:
        panes[player] += 1
    elif cmd == 108 and panes[player] < 80 - paneWidth - 1:
        panes[player] -= 1
    elif cmd == 102:
        fireBall()

def renderFrame():
    '''
    Render current game.
    '''
    buf = bytearray(1920)

    # Render top pane.
    if panes[0] > -1 and panes[0] < 80 - paneWidth:
        for i in range(panes[0] * 3, (panes[0] + paneWidth) * 3):
            buf[i] = 255

    # Render bottom pane.
    if panes[1] > -1 and panes[1] < 80 - paneWidth:
        for i in range((7 * 80 + panes[1]) * 3, (7 * 80 + panes[1] + paneWidth) * 3):
            buf[i] = 255

    # render ball.
    if ball[0] > 0 and ball[0] < 80 and ball[1] > 0 and ball[1] < 8:
        i = (ball[1] * 80 + ball[0]) * 3
        buf[i] = 255
        buf[i + 1] = 255
        buf[i + 2] = 255

    return buf


# WebSocket server
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
            client.settimeout(600) # timeout = 10min
            thread = threading.Thread(
                target=self.listenToClient,
                args=(client, address))
            thread.start()

    def listenToClient(self, client, address):
        global panes
        global handleCommand

        # Try to find available player position.
        player = 0
        if panes[0] != -1:
            if panes[1] == -1:
                player = 1
            else:
                client.close()
                return

        # Turn game on.
        turnGameOn()

        # Lock player position.
        panes[player] = 0

        print('New connection: ' + ':'.join((address[0], str(address[1]))))
        maxHeaderSize = 4096
        try:
            # Do websocket handshake.
            data = client.recv(maxHeaderSize)
            if data:
                print('Received handshake:')
                lines = data.split('\r\n')  # Split in lines

                for line in lines:
                    print(line)

                    # If the line starts with 'Sec-WebSocket-Key:' we can read
                    # the ws key.
                    if line.startswith('Sec-WebSocket-Key:'):
                        key = line.split(':')[1].lstrip()
                        fixed_string = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
                        combined = key + fixed_string

                        # Compute hasked response key.
                        ret = base64.b64encode(hashlib.sha1(combined).digest())

                        # Send handshake response.
                        client.send(
                            'HTTP/1.1 101 Switching Protocols\r\n' +
                            'Upgrade: websocket\r\n' +
                            'Connection: Upgrade\r\n' +
                            'Sec-WebSocket-Accept: ' + ret + '\r\n' +
                            'Sec-WebSocket-Protocol: chat\r\n\r\n')

                        # We're in WebSocket land now!
                        while True:
                            data = client.recv(7)
                            if data:
                                arr = array.array('B', data)
                                cmd = arr[6] ^ arr[2]

                                # Wake up game.
                                turnGameOn()

                                # Handle command.
                                handleCommand(player, cmd)
                            else:
                                raise error('Client disconnected')
            else:
                raise error('Client disconnected')
        except Exception as e:
            print(str(e))

            # The client closed the connection, this also exits the thread.
            client.close()

            # Unlock player.
            panes[player] = -1


def startSocketServer():
    ThreadedServer('', 8000).listen()

if __name__ == "__main__":
    # Start socket server.
    thread = threading.Thread(target=startSocketServer)
    thread.start()

    # Keep sending pixel data.
    # Pixel data: RGB*80*8=1920
    while True:
        # Game loop
        while gameIsOn:
            # Render a frame and write to stdout.
            buf = renderFrame()
            sys.stdout.write(buf)
            sys.stdout.flush()

            # If there has not been any activity for 10 seconds, the game will
            # turn off.
            if int(time.time()) - gameIsOnSince > 10000:
                turnGameOff()

            # Should we sleep here?

        # Regular loop
        buf = sys.stdin.read(1920)
        sys.stdout.write(buf)
        sys.stdout.flush()
