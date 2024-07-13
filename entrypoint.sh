#!/bin/sh

cleanup() {
    kill $(cat /tmp/main.pid)
}

trap cleanup EXIT

redis-server --daemonize yes

python main.py &
echo $! > /tmp/main.pid

cd app
python bot.py
