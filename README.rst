|logo|

Cilium Microscope
=================

Cilium microscope allows you to see ``cilium monitor`` output from all your cilium nodes.
This allows you to have one simple to use command to interact with your cilium nodes
within k8s cluster.


Running microscope in your Kubernetes cluster
---------------------------------------------

``kubectl run -i --tty microscope --image cilium/microscope --restart=Never -- sh`` will run a shell inside a pod in your cluster.

``python microscope.py -h`` inside this shell will show ``microscope`` help.


Running microscope locally
--------------------------

To run ``microscope`` locally, you need to have Python 3 installed. Using virtualenv is recommended, but not necessary.

To install all dependencies run ``pip install -r requirements.txt``.
After dependencies are installed you should be able to run ``python3 microscope/microscope.py``

Alternatively you can run ``make`` to build self-contained Python archive which will container all dependencies and requires only Python to run.

The archive will be located in ``dist/microscope.pyz``, and should be executable directly.


.. |logo| image:: https://cdn.rawgit.com/cilium/microscope/master/docs/logo.svg
    :alt: Cilium Microscope Logo
