# Base image of the IPython/Jupyter notebook, with conda
# Intended to be used in a tmpnb installation
# Customized from https://github.com/jupyter/docker-demo-images/tree/master/common

FROM debian:jessie

MAINTAINER Andrew Osheroff <andrewosh@gmail.com>

ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update -y &&\
    apt-get install -y curl git vim wget build-essential python-dev ca-certificates bzip2 libsm6\
      nodejs-legacy npm python-virtualenv python-pip gcc gfortran libglib2.0-0 python-qt4 &&\
    apt-get clean &&\
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*tmp

# We run our docker images with a non-root user as a security precaution.
# main is our user
RUN useradd -m -s /bin/bash main

EXPOSE 8888

USER main
ENV HOME /home/main
ENV SHELL /bin/bash
ENV USER main
WORKDIR $HOME

# Add helper script
ADD start-notebook.sh /home/main/
ADD templates/ /srv/templates/

USER root
RUN chmod a+rX /srv/templates
RUN chown -R main:main /home/main

RUN pip install --upgrade setuptools pip

USER main

# Install Anaconda and Jupyter
RUN wget https://3230d63b5fc54e62148e-c95ac804525aac4b6dba79b00b39d1d3.ssl.cf1.rackcdn.com/Anaconda-2.3.0-Linux-x86_64.sh
RUN bash Anaconda-2.3.0-Linux-x86_64.sh -b &&\
    rm Anaconda-2.3.0-Linux-x86_64.sh
ENV PATH $HOME/anaconda/bin:$PATH
RUN conda create -n python3 python=3.3 anaconda
RUN /bin/bash -c "source activate python3 && ipython kernelspec install-self --user"

# Convert notebooks to the current format
# RUN find . -name '*.ipynb' -exec ipython nbconvert --to notebook {} --output {} \;
# RUN find . -name '*.ipynb' -exec ipython trust {} \;

ENV SHELL /bin/bash
