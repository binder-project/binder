# Binder

A system for deploying a collection of Jupyter notebooks and their dependencies across one or more nodes of a Kubernetes cluster.

**WIP** and under very active development! Definitely reach out if you'd like to get involved!

### Goals
- Provide "one-click" deployment straight from a GitHub repo to interactive Jupyter notebooks
- Support a variety of custom dependencies with simple configuration
- Support custom external services, like databases 
- Focus on the reproducibility of science and analytics

### Overview

A typical deployment would work like this. 

A user would provide a GitHub repo and a selected set on services on a website. Given that info, we build and upload docker images for core notebook dependencies and all required services (if not already built). This can take a few minutes, but only needs to happen once per repo. It will need to be repeated if the repo is updated, but we've designed our images to be modular and hopefully make this process faster.

The above step results in a link that, when clicked, will populate template files for both services and notebooks, and launch the images associated with the binder on a cluster using Kubernetes

### Concepts
- `services` : Modular, versioned components that can be configured and added to an app, e.g. databases, Spark, etc. Services are allowed to have client-specific code that can be inserted into the notebook image at build time

- `notebooks`: This is the main entrypoint and includes Jupyter notebooks and simple dependencies that don't require separate services (e.g. requirements.txt)

- `binder` : A combination of notebooks and services in a single, deployable app

### Components
- `templates` : Parameterizable JSON that specifies the building blocks of a binder

- `proxy` : Maintains and registers routes to apps deployed on a cluster

- `modules` : Services that are independent of particular apps and configurable, for example, databases, Spark, etc.

- `binder` : Core utilities and CLI for building, managing, and deploying binders








