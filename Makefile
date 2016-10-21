deploy:
	scp pong.py root@10.42.76.66:pong.py

kill:
	./killpong.sh
