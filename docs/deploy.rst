Deployment Instructions
#######################

Not everyone needs to understand how to configure packages deployment, but it is useful to understand how it is configured. The ``api`` repository on Github is the main source of truth for both the PyPi and documentation website. There are some Github Actions scripts that trigger on changes to the ``master`` branch both to build the package and push it to PyPi, and also to build the ``takeqontrol.github.io`` modules.

You can find these scripts under the ``.github`` directory of the repository. These are just custom configurations of standard Github Actions scripts for our particular applications.

This documentation is hosted in `takeqontrol.github.io/api <https://takeqontrol.github.io/api>`__). 