from setuptools import setup
from setuptools_rust import Binding, RustExtension

setup(
    name='Elo-MMR-python-bindings',
    version='1.0',
    rust_extensions=[
        RustExtension('elo_mmr_py_bindings', binding=Binding.PyO3),
    ],
    packages=['elo_mmr_py'],
    zip_safe=False,
    install_requires=[
        'setuptools_rust>=1.2.0',
        'pydantic>=1.9.0',
    ],
)
