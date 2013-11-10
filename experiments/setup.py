'''
Created on Jun 20, 2013

@author: tobias
'''


from distutils.core import setup, Extension


module1 = Extension('pyrsistentc', sources = ['pyrsistentmodule.c'], include_dirs=['/home/tobias/Development/python/source275/Python-2.7.5/Include'])

setup(name = 'Temp',
      version = '0.1',
      description = 'Test',
      ext_modules = [module1])
