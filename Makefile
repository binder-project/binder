# Change this to the group of the standard binder user
GROUP = andrew

install:
	wget https://github.com/jwilder/docker-squash/releases/download/v0.1.0/docker-squash-linux-amd64-v0.1.0.tar.gz
	tar -C /usr/local/bin -xzvf docker-squash-linux-amd64-v0.1.0.tar.gz
	rm docker-squash-linux-amd64-v0.1.0.tar.gz
	echo "$(GROUP) ALL=(ALL) NOPASSWD: /usr/local/bin/docker-squash" >> /etc/sudoers
	service sudo restart
