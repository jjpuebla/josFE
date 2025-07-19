from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().splitlines()

setup(
    name='josfe',
    version='0.0.1',
    description='Tu app para facturación electrónica',
    author='Tu Nombre',
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires
)
