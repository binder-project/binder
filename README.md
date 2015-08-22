# Binder

[![Join the chat at https://gitter.im/binder-project/binder](https://badges.gitter.im/Join%20Chat.svg)](https://gitter.im/binder-project/binder?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)

A system for deploying a collection of Jupyter notebooks and their dependencies as live, interactive notebooks, straight from GitHub repositories, across one or more nodes of a Kubernetes cluster. 

See discussion on the [Jupyter mailing list](https://groups.google.com/forum/#!topic/jupyter/2DjI5sZa8tI).

Live demo at http://mybinder.org. Still under very active development! Definitely reach out if you'd like to get involved, take a look at the current issues for contribution ideas.

### Goals
- Provide "one-click" deployment straight from a GitHub repo to interactive Jupyter notebooks
- Support a variety of custom dependencies with simple configuration
- Support custom external services, like databases 
- Focused on the reproducibility of science and analytics

### Overview

A typical deployment works like this. 

A user provides a GitHub repo, services, and dependencies at http://mybinder.org. Given that info, we build and upload docker images for core notebook dependencies and all required services (if not already built). This can take a few minutes, but only needs to happen once per repo. It will need to be repeated if the repo is updated, but the modularity of our images will make this process faster.

The above step results in a link to an endpoint (of the form `http://mybinder.org/repo/user/project`) that will populate template files for both services and notebooks, and launch the images associated with the binder on a cluster using Kubernetes

### Concepts
- `services` : Modular, versioned components that can be configured and added to an app, e.g. databases, Spark, etc. Services are allowed to have client-specific code that can be inserted into the notebook image at build time

- `notebooks`: This is the main entrypoint and includes Jupyter notebooks and simple dependencies that don't require separate services (e.g. `requirements.txt` for `pip` installable dependencies)

- `binder` : A combination of notebooks and services in a single, deployable app

### Components
- `templates` : Parameterizable JSON that specifies the building blocks of a binder

- `proxy` : Maintains and registers routes to apps deployed on a cluster

- `services` : Services that are independent of particular apps and configurable, for example, databases, Spark, etc.

- `binder` : Core utilities and CLI for building, managing, and deploying binders








