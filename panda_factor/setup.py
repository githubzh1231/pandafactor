from setuptools import setup, find_packages

setup(
    name='panda_factor',
    version='0.1',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'pymongo',
        'redis',
        'loguru',
        'pandas',
        'panda_common',
        # 'panda_data',  # 移除循环依赖
    ],
    entry_points={
        'console_scripts': [
            'panda_factor = panda_factor.__main__:main',
        ],
    },
) 