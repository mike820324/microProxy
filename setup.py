from setuptools import setup, find_packages
from codecs import open
import os

here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name="microProxy",
    version="0.2.0",
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
    install_requires=[
        "tornado==4.3",
        "pyzmq==15.2.0",
        "blinker==1.4",
        "ipaddress==1.0.16",
        "watchdog==0.8.3",
        "pyOpenSSL==16.0.0",
        "service-identity==16.0.0",
        "h2==2.4.0"
    ],
    extras_require={
        'viewer': [
            "colored==1.2.2",
            "urwid==1.3.1",
            "gviewer==1.1.0"
        ],
        'develop': [
            "mock==2.0.0",
            "coverage==4.0.3",
            "coveralls==1.1"
        ]
    }
)
