from setuptools import setup, find_packages

setup(
    name='scopetree',
    packages=find_packages(),
    install_requires=[
        'click>=8.1.0',
        'rich>=13.0.0',
        'pyyaml>=6.0',
        'aiohttp>=3.9.0',
    ],
    entry_points={
        'console_scripts': [
            'scopetree=scopetree.cli:cli',
        ],
    },
)