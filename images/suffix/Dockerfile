USER root
RUN chown -R main:main $HOME/notebooks
USER main

# Convert notebooks to the current format
RUN find $HOME/notebooks -name '*.ipynb' -exec ipython nbconvert --to notebook {} --output {} \;
RUN find $HOME/notebooks -name '*.ipynb' -exec ipython trust {} \;

WORKDIR $HOME/notebooks
