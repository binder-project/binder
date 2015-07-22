FROM ubuntu

MAINTAINER untitled <untitled@untitled.org>

RUN apt-get update

# Java setup
RUN apt-get install -y default-jre

EXPOSE {{web-ui-port}}
EXPOSE {{app-ui-port}}
EXPOSE {{master-port}}

# Spark setup
RUN apt-get install -y wget
RUN wget http://d3kbcqa49mib13.cloudfront.net/spark-1.3.1-bin-hadoop1.tgz
RUN tar -xzf spark-1.3.1-bin-hadoop1.tgz
ENV SPARK_HOME $HOME/spark-1.3.1-bin-hadoop1
ENV PATH $PATH:$SPARK_HOME/bin
ENV PATH $PATH:$SPARK_HOME/sbin
RUN sed 's/log4j.rootCategory=INFO/log4j.rootCategory=ERROR/g' $SPARK_HOME/conf/log4j.properties.template > $SPARK_HOME/conf/log4j.properties
ENV _JAVA_OPTIONS "-Xms512m -Xmx2g"

ENV SPARK_MASTER_PORT {{master-port}}
ENV SPARK_MASTER_WEBUI_PORT {{web-ui-port}}

CMD ["start-master.sh"]
