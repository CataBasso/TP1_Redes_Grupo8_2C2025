run:
	gnome-terminal -- bash -c "python3 src/start-server.py -H 127.0.0.1 -p 5000; exec bash" &
	gnome-terminal -- bash -c "python3 src/download.py -H 127.0.0.1 -p 5000; exec bash" &
	gnome-terminal -- bash -c "python3 src/upload.py -H 127.0.0.1 -p 5000; exec bash" &