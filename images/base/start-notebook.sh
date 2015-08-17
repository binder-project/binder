#!/bin/bash
$OPTS=""
if [ -f $HOME/notebooks/index.ipynb ]; then
  OPTS="$OPTS --NotebookApp.default_url=/tree/index.ipynb "
fi
ipython notebook $OPTS "$@"
