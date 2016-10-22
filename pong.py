#!/usr/bin/env python

# Doesn't work with Python 3.

import sys
import socket
import threading
import hashlib
import base64
import array
import time
import math
import random

# Screen data
screenW = 80
screenH = 8

# Game data
ball = list((-1, -1))
ballColor = list((255, 255, 255))
ballVector = list((0, 0))
ballInterval = 20
ballIntCounter = 0
ballTied = -1

panes = list((-1, -1))
paneWidth = 7
paneSteps = 1
paneDeflectW = 2

gameIsOn = False
gameIsOnSince = 0

def log(str):
    sys.stderr.write(str + '\n')

def turnGameOn():
    global gameIsOn
    global gameIsOnSince

    gameIsOn = True
    gameIsOnSince = int(time.time())

def turnGameOff():
    global gameIsOn

    gameIsOn = False

def recolorBall():
    global ballColor
    ballColor[0] = random.choice((0, 255))
    ballColor[1] = random.choice((0, 255))
    ballColor[2] = random.choice((0, 255))
    if (ballColor[0] == 0 and ballColor[1] == 0):
        ballColor[2] = 255

def fireBall(player, tied=False):
    '''
    Start moving the ball.
    '''
    global screenH
    global ballTied
    global ballVector
    global ballIntCounter

    ballVector[0] = 0
    ballVector[1] = 1 if player == 0 else -1
    ball[0] = int(panes[player] + math.floor(paneWidth / 2))
    ball[1] = 1 if player == 0 else screenH - 2

    if tied:
        ballTied = player

def computeDeflection(currDef, ballX, paneX):
    global paneWidth
    global paneDeflectW

    if ballX - paneX <= paneDeflectW:
        return currDef - 1
    elif paneX + paneWidth - ballX <= paneDeflectW:
        return currDef + 1
    else:
        return currDef

def computeCollision():
    '''
    Compute ball collision.
    '''
    global ball
    global panes
    global paneWidth
    global screenW
    global screenH
    global ballVector
    global ballInterval

    # pane collisions
    if panes[0] != -1 and ball[1] == 1:
        if ball[0] >= panes[0] and ball[0] < panes[0] + paneWidth:
            ballVector[0] = computeDeflection(ballVector[0], ball[0], panes[0])
            ballVector[1] = 1
            recolorBall()
        else:
            # refire from top plane.
            fireBall(0, True)
            ballInterval -= 1

    elif panes[1] != -1 and ball[1] == screenH - 2:
        if ball[0] >= panes[1] and ball[0] < panes[1] + paneWidth:
            ballVector[0] = computeDeflection(ballVector[0], ball[0], panes[1])
            ballVector[1] = -1
            recolorBall()
        else:
            # refire from bottom plane.
            fireBall(1, True)
            ballInterval -= 1

    # wall collisions
    if ball[0] == 0:
        ballVector[0] = -ballVector[0]
    elif ball[0] == screenW - 1:
        ballVector[0] = -ballVector[0]


def handleCommand(player, cmd):
    '''
    Handle player action.
    '''
    global panes
    global paneWidth
    global screenW
    global screenH
    global ballTied

    log('Received command #' + str(cmd) + ' for player #' + str(player))

    if cmd == 114 and panes[player] < screenW - paneWidth - paneSteps: # r
        panes[player] += paneSteps
        if ballTied == player:
            ball[0] += paneSteps
    elif cmd == 108 and panes[player] > 0: # l
        panes[player] -= paneSteps
        if ballTied == player:
            ball[0] -= paneSteps
    elif cmd == 102: # f
        # Only if ball is not moving or is outside the screen.
        if ballTied != -1:
            if ballTied == player:
                ballTied = -1
        elif (ballVector[0] == 0 and ballVector[1] == 0) or ((ball[0] < 0 or ball[0] > screenW) or (ball[1] < 0 or ball[1] > screenH - 1)):
            fireBall(player)
    elif cmd == 113: # q
        turnGameOff()

def renderFrame():
    '''
    Render current game.
    '''
    global screenW
    global screenH
    global panes
    global ball
    global ballInterval
    global ballIntCounter
    global ballColor

    buf = bytearray(1920)

    # Render top pane.
    if panes[0] > -1 and panes[0] < screenW - paneWidth:
        for i in range(panes[0] * 3, (panes[0] + paneWidth) * 3):
            buf[i] = 255

    # Render bottom pane.
    if panes[1] > -1 and panes[1] < screenW - paneWidth:
        for i in range((7 * 80 + panes[1]) * 3, (7 * screenW + panes[1] + paneWidth) * 3):
            buf[i] = 255

    # Displace ball.
    ballIntCounter -= 1
    if ballIntCounter <= 0 and ballTied == -1:
        ballIntCounter = ballInterval
        ball[0] += ballVector[0]
        ball[1] += ballVector[1]

        # Compute collision.
        computeCollision()

    # Render ball.
    if ball[0] > 0 and ball[0] < screenW and ball[1] > 0 and ball[1] < screenH:
        i = (ball[1] * screenW + ball[0]) * 3
        buf[i] = ballColor[0]
        buf[i + 1] = ballColor[1]
        buf[i + 2] = ballColor[2]

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
        global ballInterval

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

        # Reset game speed.
        ballInterval = 20

        # Lock player position.
        panes[player] = 0

        log('New connection: ' + ':'.join((address[0], str(address[1]))))
        maxHeaderSize = 4096
        try:
            # Do websocket handshake.
            data = client.recv(maxHeaderSize)
            if data:
                log('Received handshake:')
                lines = data.split('\r\n')  # Split in lines

                for line in lines:
                    log(line)

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
            log(str(e))

            # The client closed the connection, this also exits the thread.
            client.close()

            # Unlock player.
            panes[player] = -1

            if panes[0] == -1 and panes[1] == -1:
                turnGameOff()


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

            # Should we sleep here?
            time.sleep(0.01)

        # Regular loop
        buf = sys.stdin.read(1920)
        sys.stdout.write(buf)
        sys.stdout.flush()
