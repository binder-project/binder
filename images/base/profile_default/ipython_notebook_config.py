#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Configuration file for ipython-notebook.

c = get_config()
c.NotebookApp.ip = '*'
c.NotebookApp.open_browser = False
c.NotebookApp.port = 8888

# Whether to trust or not X-Scheme/X-Forwarded-Proto and X-Real-Ip/X-Forwarded-
# For headerssent by the upstream reverse proxy. Necessary if the proxy handles
# SSL
c.NotebookApp.trust_xheaders = True

# Include our extra templates
c.NotebookApp.extra_template_paths = ['/srv/templates/']

# Supply overrides for the tornado.web.Application that the IPython notebook
# uses.
c.NotebookApp.tornado_settings = {
    'headers': {
        'Content-Security-Policy': "frame-ancestors 'self' https://*.jupyter.org https://jupyter.github.io https://*.tmpnb.org"
    }
}