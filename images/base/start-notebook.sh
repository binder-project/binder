#!/bin/bash
OPTS=""
echo "$HOME/notebooks/index.ipynb: " $HOME/notebooks/index.ipynb
if [ -e $HOME/notebooks/index.ipynb ]; then
  OPTS="$OPTS --NotebookApp.default_url=/tree/index.ipynb "
fi
CMD="$OPTS $@"
echo "CMD: " $CMD
ipython notebook $CMD
