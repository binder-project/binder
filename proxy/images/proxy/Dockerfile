FROM ubuntu

MAINTAINER Andrew Osheroff <andrewosh@gmail.com>

RUN apt-get update && apt-get install -y python-dev python-pip git  && apt-get clean

# install nodejs
RUN apt-get install -y nodejs-legacy npm

# install proxy
RUN git clone https://github.com/andrewosh/configurable-http-proxy.git
RUN npm install -g configurable-http-proxy/

RUN useradd -m -s /bin/bash main

EXPOSE 8080
EXPOSE 8081

USER main
ENV HOME /home/main
ENV SHELL /bin/bash
ENV USER main
WORKDIR $HOME
