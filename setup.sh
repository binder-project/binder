#!/bin/bash

# update
apt-get update -y
apt-get install -y git vim python-pip make wget


# setup gcloud
curl https://sdk.cloud.google.com | bash
gcloud preview
gcloud auth login
gcloud compute config-ssh

# get/install anaconda
wget https://3230d63b5fc54e62148e-c95ac804525aac4b6dba79b00b39d1d3.ssl.cf1.rackcdn.com/Anaconda-2.3.0-Linux-x86_64.sh
bash Anaconda-2.3.0-Linux-x86_64.sh

# get docker
curl -sSL https://get.docker.com/ | sh
sudo usermod -a -G docker $(whoami)

# get/build kubernetes
git clone https://www.github.com/kubernetes/kubernetes
cd kubernetes/
git checkout release-1.0
build/release.sh

# get/install binder
cd ~/binder/
make install
pip install -r requirements.txt

# configure binder environment variables
echo "export BINDER_HOME=~/binder" >> ~/.bashrc
echo "export PATH=\$PATH:\$BINDER_HOME/bin" >> ~/.bashrc
echo "export PYTHONPATH=\$PYTHONPATH:\$BINDER_HOME" >> ~/.bashrc

# configure kubernetes environment variables
echo "export KUBERNETES_HOME=~/binder/kubernetes" >> ~/.bashrc
echo "export PATH=\$PATH:/usr/local/go/bin" >> ~/.bashrc
echo "export PATH=\$PATH:\$KUBERNETES_HOME/cluster" >> ~/.bashrc


