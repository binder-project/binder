# Add the notebooks directory
ADD {{notebooks}} $HOME/notebooks

WORKDIR $HOME/notebooks

USER root
RUN chown -R main:main /home/main/

CMD ipython notebook
