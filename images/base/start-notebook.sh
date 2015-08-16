#!/bin/bash
$OPTS=""
if [ -f index.ipynb ]; then
  OPTS="$OPTS --NotebookApp.default_url=/tree/index.ipynb "
fi
ipython notebook $OPTS "$@"
