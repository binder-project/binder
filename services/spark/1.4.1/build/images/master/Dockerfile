FROM ubuntu

MAINTAINER untitled <untitled@untitled.org>

# Java setup
RUN apt-get update -y &&\
    apt-get install -y default-jre wget  &&\
    apt-get clean &&\
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*tmp
     

EXPOSE 8080
EXPOSE 4040
EXPOSE 7077

# Spark setup
RUN wget http://d3kbcqa49mib13.cloudfront.net/spark-1.4.1-bin-hadoop1.tgz &&\
    tar -xzf spark-1.4.1-bin-hadoop1.tgz &&\
    rm spark-1.4.1-bin-hadoop1.tgz
ENV SPARK_HOME $HOME/spark-1.4.1-bin-hadoop1
ENV PATH $PATH:$SPARK_HOME/bin
ENV PATH $PATH:$SPARK_HOME/sbin
ENV _JAVA_OPTIONS "-Xms512m -Xmx2g"

ENV SPARK_MASTER_PORT 7077
ENV SPARK_MASTER_WEBUI_PORT 8080

ADD start.sh $HOME/
