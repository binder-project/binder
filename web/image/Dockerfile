FROM ubuntu

MAINTAINER Andrew Osheroff <andrewosh@gmail.com>

RUN apt-get update && apt-get install -y python-dev python-pip  && apt-get clean

RUN pip install Flask cherrypy

RUN useradd -m -s /bin/bash main

EXPOSE 80

USER main
ENV HOME /home/main
ENV SHELL /bin/bash
ENV USER main
WORKDIR $HOME

ADD server/ $HOME/server

USER root

CMD ["python", "server/server.py"]





