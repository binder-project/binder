#!/bin/bash

start-master.sh

# start-master launches in the background, so this foreground thread should spin
while [ 1 ]
do
  sleep 5
done
