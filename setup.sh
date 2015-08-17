#!/bin/bash

# update
apt-get update -y
apt-get install -y git vim python-pip

# get/install anaconda
wget https://3230d63b5fc54e62148e-c95ac804525aac4b6dba79b00b39d1d3.ssl.cf1.rackcdn.com/Anaconda-2.3.0-Linux-x86_64.sh
bash Anaconda-2.3.0-Linux-x86_64.sh

# get/build kubernetes
git clone https://www.github.com/kubernetes/kubernetes
cd kubernetes/
git checkout release-1.0
build/release.sh
cd

# get/install binder
git clone https://www.github.com/binder-project/binder
cd binder/
make install

# configure environment variables
echo "BINDER_HOME=~/binder" >> ~/.bashrc
echo "PATH=$PATH:$BINDER_HOME/bin" >> ~/.bashrc
echo "PYTHONPATH=$PYTHONPATH:$BINDER_HOME" >> ~/.bashrc
