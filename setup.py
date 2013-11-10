import os
from setuptools import setup

f = open(os.path.join(os.path.dirname(__file__), 'README.rst'))
readme = f.read()
f.close()

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
    scripts = [],
)