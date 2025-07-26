from setuptools import setup, find_packages
import os

# 确保当前目录中有一个panda_data目录
if not os.path.exists('panda_data'):
    os.makedirs('panda_data')
    with open('panda_data/__init__.py', 'a'):
        pass

setup(
    name='panda_data',
    version='0.1',
    packages=['panda_data', 'panda_data.factor', 'panda_data.market_data', 'panda_data.scripts'],
    package_dir={
        'panda_data': 'panda_data',
        'panda_data.factor': 'panda_data/factor',
        'panda_data.market_data': 'panda_data/market_data',
        'panda_data.scripts': 'panda_data/scripts'
    },
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
        'pandas',
        'panda_common',
        # 'panda_factor'  # 移除循环依赖
    ],
    entry_points={
        'console_scripts': [
            'panda_data = panda_data.__main__:main',
        ],
    },
) 