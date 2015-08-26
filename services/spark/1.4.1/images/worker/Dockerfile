FROM ubuntu

MAINTAINER untitled <untitled@untitled.org>

RUN apt-get update -y &&\
    apt-get install -y default-jre wget  &&\
    apt-get clean &&\
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*tmp

EXPOSE {{app-ui-port}}
EXPOSE 8080

# Spark setup
RUN wget http://d3kbcqa49mib13.cloudfront.net/spark-1.4.1-bin-hadoop1.tgz &&\
    tar -xzf spark-1.4.1-bin-hadoop1.tgz &&\
    rm spark-1.4.1-bin-hadoop1.tgz
ENV SPARK_HOME $HOME/spark-1.4.1-bin-hadoop1
ENV PATH $PATH:$SPARK_HOME/bin
ENV PATH $PATH:$SPARK_HOME/sbin
ENV PYTHONPATH $SPARK_HOME/python/lib/py4j-0.8.2.1-src.zip:$PYTHONPATH

ADD start.sh $HOME/
