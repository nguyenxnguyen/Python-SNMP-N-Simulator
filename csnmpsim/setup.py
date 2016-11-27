try:
    from setuptools import setup
    from setuptools import Extension
except ImportError:
    from distutils.core import setup
    from distutils.extension import Extension

setup(name='csnmpsim', version='1.0', ext_modules=[Extension('csnmpsim', ['csnmpsim.c'])])