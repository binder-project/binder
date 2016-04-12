FROM ubuntu

MAINTAINER Andrew Osheroff <andrewosh@gmail.com>

RUN apt-get update && apt-get install -y python-dev python-pip git curl  && apt-get clean

# install nodejs (taken from http://stackoverflow.com/questions/25899912/install-nvm-in-docker)
ENV NVM_DIR /usr/local/nvm
ENV NODE_VERSION 5.7.0
RUN rm /bin/sh && ln -sf /bin/bash /bin/sh

# Install nvm with node and npm
RUN curl -LNk https://raw.githubusercontent.com/creationix/nvm/v0.31.0/install.sh | bash 
RUN source $NVM_DIR/nvm.sh \
    && nvm install $NODE_VERSION \
    && nvm alias default $NODE_VERSION \
    && nvm use default

ENV PATH $NVM_DIR/versions/node/v$NODE_VERSION/bin:$PATH

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

ADD error_pages/ $HOME/error_pages

WORKDIR $HOME
