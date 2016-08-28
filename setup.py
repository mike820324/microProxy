from setuptools import setup, find_packages
from codecs import open
from microproxy.version import VERSION
import os

here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

with open(os.path.join(here, './requirements/proxy.txt')) as f:
    proxy_deps = [dep for dep in f.read().split("\n") if dep]

with open(os.path.join(here, './requirements/viewer.txt')) as f:
    viewer_deps = [dep for dep in f.read().split("\n") if dep]

with open(os.path.join(here, './requirements/development.txt')) as f:
    dev_deps = [dep for dep in f.read().split("\n") if dep and "-r" not in dep]

setup(
    name="microProxy",
    version=VERSION,
    description="A http/https interceptor proxy written in python inspired by mitmproxy",
    long_description=long_description,
    url="https://github.com/mike820324/microProxy",
    author="MicroMike",
    author_email="mike820324@gmail.com",
    license="MIT",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Environment :: Console",
        "Environment :: Console :: Curses",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: POSIX",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Topic :: Security",
        "Topic :: Internet",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: Proxy Servers",
        "Topic :: Software Development :: Testing"
    ],
    packages=find_packages(include=[
        "microproxy", "microproxy.*",
    ]),
    include_package_data=True,
    entry_points={
        'console_scripts': [
            "microproxy=microproxy.command_line:main",
        ]
    },
    install_requires=proxy_deps,
    extras_require={
        'viewer': viewer_deps,
        'develop': dev_deps
    }
)
