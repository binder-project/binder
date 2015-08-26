FROM ubuntu

MAINTAINER untitled <untitled@untitled.org>

# Java setup
RUN apt-get update -y &&\
    apt-get install -y default-jre wget  &&\
    apt-get clean &&\
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*tmp
     

EXPOSE {{web-ui-port}}
EXPOSE {{app-ui-port}}
EXPOSE {{master-port}}

# Spark setup
RUN wget http://d3kbcqa49mib13.cloudfront.net/spark-1.4.1-bin-hadoop1.tgz &&\
    tar -xzf spark-1.4.1-bin-hadoop1.tgz &&\
    rm spark-1.4.1-bin-hadoop1.tgz
ENV SPARK_HOME $HOME/spark-1.4.1-bin-hadoop1
ENV PATH $PATH:$SPARK_HOME/bin
ENV PATH $PATH:$SPARK_HOME/sbin
ENV PYTHONPATH $SPARK_HOME/python/lib/py4j-0.8.2.1-src.zip:$PYTHONPATH

ENV SPARK_MASTER_PORT {{master-port}}
ENV SPARK_MASTER_WEBUI_PORT {{web-ui-port}}

ADD start.sh $HOME/
