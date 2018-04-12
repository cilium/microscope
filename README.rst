|logo|

Cilium Microscope
=================

Cilium microscope allows you to see ``cilium monitor`` output from all your cilium nodes.
This allows you to have one simple to use command to interact with your cilium nodes
within k8s cluster.


Running microscope in your Kubernetes cluster
---------------------------------------------

``kubectl create -f docs/microscope.yaml`` will create a pod in your kube-system namespace to which you can connect to run ``microscope`` with ``kubectl exec -it -n kube-system microscope sh``. This will also create RBAC objects which ``microscope`` needs in order to do its work.

Alternatively, you can use ``kubectl run -i --tty microscope --image cilium/microscope --restart=Never -- sh``. This won't work if you have RBAC enabled in your cluster.

In any case you will end up with a shell inside ``microscope`` pod.
``microscope -h`` inside this shell will show ``microscope`` help.


Running microscope locally
--------------------------

To run ``microscope`` locally, you need to have Python 3.5 or newer installed. Using virtualenv is recommended, but not necessary.

``microscope`` is available as a package in PyPI, so all you need to do is run ``pip install cilium-microscope``. ``microscope`` executable should be available in your path.

Alternatively you can run ``make`` to build self-contained Python archive which will container all dependencies and requires only Python to run.

The archive will be located in ``dist/microscope.pyz``, and should be executable directly.


.. |logo| image:: https://cdn.rawgit.com/cilium/microscope/master/docs/logo.svg
    :alt: Cilium Microscope Logo
