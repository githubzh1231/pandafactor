from setuptools import setup, find_packages
import os

setup(
    name='panda_data',
    version='0.1',
    packages=find_packages(),  # 这会自动找到所有包
    include_package_data=True,
    package_data={
        'panda_data': [
            'factor/**/*',
            'market_data/**/*',
            'scripts/**/*',
            '*.yaml',
        ],
    },
    install_requires=[
        'flask',
        'pymongo',
        'redis',
        'loguru',
        'panda_common',
        # 'ta-lib',  # Temporarily commented out
    ],
    entry_points={
        'console_scripts': [
            'panda_data = panda_data.__main__:main',
        ],
    },
) 