# Base image of the IPython/Jupyter notebook, with conda
# Intended to be used in a tmpnb installation
# Customized from https://github.com/jupyter/docker-demo-images/tree/master/common

FROM debian:jessie

MAINTAINER CodeNeuro <info@codeneuro.org>

ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update

RUN apt-get update && apt-get install -y git vim wget build-essential python2.7-dev ca-certificates bzip2 libsm6 && apt-get clean

# We run our docker images with a non-root user as a security precaution.
# codeneuro is our user
RUN useradd -m -s /bin/bash codeneuro

EXPOSE 8888

USER codeneuro
ENV HOME /home/codeneuro
ENV SHELL /bin/bash
ENV USER codeneuro
WORKDIR $HOME

USER codeneuro

RUN apt-get install -y python-pip ipython gcc
RUN pip install --yes ipython 
RUN pip install ipython-notebook 

RUN ipython profile create

# Workaround for issue with ADD permissions
USER root
ADD profile_default /home/codeneuro/.ipython/profile_default
ADD templates/ /srv/templates/
RUN chmod a+rX /srv/templates
RUN chown codeneuro:codeneuro /home/codeneuro -R
USER codeneuro

# Convert notebooks to the current format
RUN find . -name '*.ipynb' -exec ipython nbconvert --to notebook {} --output {} \;
RUN find . -name '*.ipynb' -exec ipython trust {} \;

ENV SHELL /bin/bash

CMD ipython notebook
