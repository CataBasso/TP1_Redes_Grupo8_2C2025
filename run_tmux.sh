#!/bin/bash

tmux new-session -d -s tp1 'python3 src/start-server.py -H 127.0.0.1 -p 5000'
tmux split-window -v -t tp1 'python3 src/download.py -H 127.0.0.1 -p 5000'
tmux split-window -h -t tp1:0.1 'python3 src/upload.py -H 127.0.0.1 -p 5000'
tmux select-layout -t tp1 tiled
tmux attach -t tp1