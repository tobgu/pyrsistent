import os
from setuptools import setup, Extension
import sys
import platform
import warnings
from distutils.command.build_ext import build_ext
from distutils.errors import CCompilerError
from distutils.errors import DistutilsPlatformError, DistutilsExecError
from _pyrsistent_version import __version__


f = open(os.path.join(os.path.dirname(__file__), 'README.rst'))
readme = f.read()
f.close()

extensions = []
if platform.python_implementation() == 'CPython':
    extensions = [Extension('pvectorc', sources=['pvectorcmodule.c'])]


class custom_build_ext(build_ext):
    """Allow C extension building to fail."""

    warning_message = """
********************************************************************************
WARNING: Could not build the %s. 
         
         Pyrsistent will still work but performance may be degraded.
         
         %s
********************************************************************************
"""

    def run(self):
        try:
            build_ext.run(self)
        except (CCompilerError, DistutilsExecError, DistutilsPlatformError):
            e = sys.exc_info()[1]
            sys.stdout.write('%s\n' % str(e))
            warnings.warn(self.warning_message % ("Extension modules",
                                                  "There was an issue with "
                                                  "your platform configuration"
                                                  " - see above."))

    def build_extension(self, ext):
        name = ext.name
        try:
            build_ext.build_extension(self, ext)
        except (CCompilerError, DistutilsExecError, DistutilsPlatformError):
            e = sys.exc_info()[1]
            sys.stdout.write('%s\n' % str(e))
            warnings.warn(self.warning_message % ("The %s extension "
                                                  "module" % (name,),
                                                  "The output above "
                                                  "this warning shows how "
                                                  "the compilation "
                                                  "failed."))

setup(
    name='pyrsistent',
    version=__version__,
    description='Persistent/Functional/Immutable data structures',
    long_description=readme,
    author='Tobias Gustafsson',
    author_email='tobias.l.gustafsson@gmail.com',
    url='http://github.com/tobgu/pyrsistent/',
    license='LICENSE.mit',
    py_modules=['_pyrsistent_version'],
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
    ],
    test_suite='tests',
    scripts=[],
    ext_modules=extensions,
    cmdclass={"build_ext": custom_build_ext},
    install_requires=['six'],
    packages=['pyrsistent']
)
