# Base image of the IPython/Jupyter notebook, with conda
# Intended to be used in a tmpnb installation
# Customized from https://github.com/jupyter/docker-demo-images/tree/master/common

FROM debian:jessie

MAINTAINER Andrew Osheroff <andrewosh@gmail.com>

ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update && apt-get install -y curl git vim wget build-essential python-dev ca-certificates bzip2 libsm6 && apt-get clean

# We run our docker images with a non-root user as a security precaution.
# main is our user
RUN useradd -m -s /bin/bash main

EXPOSE 8888

USER main
ENV HOME /home/main
ENV SHELL /bin/bash
ENV USER main
WORKDIR $HOME

USER root

# Install node.js and python dependencies
RUN apt-get install -y nodejs-legacy npm python-virtualenv python-pip gcc
RUN pip install --upgrade setuptools pip

# Build jupyter notebooks code from source
RUN git clone https://github.com/jupyter/notebook jupyter-notebook
RUN pip install --pre -e jupyter-notebook/

USER main

ADD profile_default /home/main/.ipython/profile_default
ADD templates/ /srv/templates/

# Add helper script
ADD start-notebook.sh /home/main/

USER root
RUN chmod a+rX /srv/templates
RUN chown -R main:main /home/main
USER main

RUN ipython profile create

# Convert notebooks to the current format
RUN find . -name '*.ipynb' -exec ipython nbconvert --to notebook {} --output {} \;
RUN find . -name '*.ipynb' -exec ipython trust {} \;

ENV SHELL /bin/bash
