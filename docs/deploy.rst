Deployment Instructions
#######################

Not everyone needs to understand how to configure packages deployment, but it is useful to understand how it is configured. The ``api`` repository on Github is the main source of truth for both the PyPi and documentation website. There are some Github Actions scripts that trigger on changes to the ``master`` branch both to build the package and push it to PyPi, and also to build the ``takeqontrol.github.io`` modules.

You can find these scripts under the ``.github`` directory of the repository. These are just custom configurations of standard Github Actions scripts for our particular applications.

This documentation is hosted in `takeqontrol.github.io/api <https://takeqontrol.github.io/api>`__). 


What is Github Actions
----------------------

    GitHub Actions is a continuous integration and continuous delivery (CI/CD) platform that allows you to automate your build, test, and deployment pipeline. You can create workflows that build and test every pull request to your repository, or deploy merged pull requests to production.


    GitHub provides Linux, Windows, and macOS virtual machines to run your workflows, or you can host your own self-hosted runners in your own data center or cloud infrastructure.


The scripts we provide are a set of commands in a configured environment that allow us to automate building and deploying the package both to PyPi and Github Pages.


Example with ``gh-pages``
^^^^^^^^^^^^^^^^^^^^^^^^^^^

This `Sphinx docs to gh-pages` action gets deployed on a push to the master branch.

.. code::

    name: Sphinx docs to gh-pages

    on:
        push:
            branches:
            - master

Now we configure an ubuntu environment, that creates a conda environment that we have configured with the `.github/environment/sphinx_conda.yaml` environment that is just a standard conda environment definition file for our program.

.. code::

    jobs:
        sphinx_docs_to_gh-pages:
            runs-on: ubuntu-latest
            name: Sphinx docs to gh-pages
            steps:
            - uses: actions/checkout@v3
                with:
                fetch-depth: 0
            - name: Make conda environment
                uses: conda-incubator/setup-miniconda@v2
                with:
                python-version: 3.9    # Python version to build the html sphinx documentation
                environment-file: .github/environment/sphinx_conda.yaml    # Path to the documentation conda environment
                auto-update-conda: false
                auto-activate-base: false
                show-channel-urls: true


In the next step we install the qontrol library into this environment.

.. code::

    - name: Installing the library
        shell: bash -l {0}
        run: |
          python setup.py install


Now we use the custom sphinx-build action script detailed `here <https://github.com/uibcdf/action-sphinx-docs-to-gh-pages>`__ to build and deploy the sphinx output to the github pages.

.. code::

    - name: Running the Sphinx to gh-pages Action
        uses: uibcdf/action-sphinx-docs-to-gh-pages@v1.1.0
        with:
          branch: master
          dir_docs: docs
          sphinxapiopts: '--separate -o . ../'
          sphinxapiexclude: '../*setup*'
          sphinxopts: ''

You can learn how to setup the github pages configuration easily by reading `this tutorial <https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site>`__


Note that the pages output is inside the ``gh-pages`` branch.


Example on PyPi deployment
^^^^^^^^^^^^^^^^^^^^^^^^^^

You can see that the following steps just involve the command of building the package in your standard shell.

.. code::

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip setuptools wheel twine
        if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
        pip install build

    - name: Build package
      run: python setup.py sdist


We use the `pypi-publish` script to upload the built package to PyPi. We authenticate using our PyPi API token. You can read about setting tokens as secrets available to github actions `here <https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions>`__

.. code::

    - name: Publish package
      uses: pypa/gh-action-pypi-publish@release/v1
      with:
        user: __token__
        password: ${{ secrets.PYPI_API_TOKEN }}



Further reading:
----------------

-   `Quick start with Github Actions <https://docs.github.com/en/actions/quickstart>`__
-   `Viewing workflow results <https://docs.github.com/en/actions/quickstart#viewing-your-workflow-results>`__
-   `Get started with Sphinx <https://www.sphinx-doc.org/en/master/usage/quickstart.html>`__ 