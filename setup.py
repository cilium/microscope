#!/usr/bin/env python

import io
import sys
import uuid

from setuptools import setup
try:  # for pip >= 10
    from pip._internal.req import parse_requirements
except ImportError:  # for pip <= 9.0.3
    from pip.req import parse_requirements

version = "1.1.1"


with io.open('README.rst', 'r', encoding='utf-8') as readme_file:
    readme = readme_file.read()

if sys.argv[-1] == 'readme':
    print(readme)
    sys.exit()

install_reqs = parse_requirements('requirements.txt', session=uuid.uuid1())
requirements = [str(req.req) for req in install_reqs]

setup(
    name='cilium-microscope',
    version=version,
    description=('An urwid-based interface for watching '
                 '`cilium monitor` events across your cluster'),
    long_description=readme,
    author='Maciej Kwiek',
    author_email='maciej@covalent.io',
    url='https://github.com/cilium/microscope',
    packages=[
        'microscope', 'microscope.ui', 'microscope.monitor', 'microscope.batch'
    ],
    entry_points={
        'console_scripts': [
            'microscope = microscope.__main__:main',
        ]
    },
    python_requires='>=3.5',
    include_package_data=True,
    install_requires=requirements,
    license='Apache 2.0',
    zip_safe=True,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Natural Language :: English',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: Implementation :: CPython',
        'Topic :: System :: Systems Administration',
        'Topic :: System :: Networking :: Monitoring',
    ],
    keywords='microscope, cilium, monitor, k8s, kubernetes',
)
