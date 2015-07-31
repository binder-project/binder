#!/bin/bash

start-slave.sh "$@"

# start-worker.sh launches in the background, so this foreground thread should spin 
while [ 1 ]
do
  sleep 5
done
