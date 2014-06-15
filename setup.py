import os
from setuptools import setup, Extension
import sys
import platform

f = open(os.path.join(os.path.dirname(__file__), 'README.rst'))
readme = f.read()
f.close()

extensions = []
if platform.python_implementation() == 'CPython' and sys.version_info[0] == 2:
    extensions = [Extension('pvectorc', sources=['pvectorcmodule.c'])]

setup(
    name='pyrsistent',
    version="0.1.0",
    description='Persistent data structures',
    long_description=readme,
    author='Tobias Gustafsson',
    author_email='tobias.l.gustafsson@gmail.com',
    url='http://github.com/tobgu/pyrsistent/',
    license='LICENSE.mit',
    packages=['tests'],
    py_modules=['pyrsistent'],
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
    ],
    test_suite='tests',
    scripts=[],
    ext_modules=extensions,
)
