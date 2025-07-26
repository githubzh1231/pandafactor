from setuptools import setup, find_packages

setup(
    name='panda_factor_server',
    version='0.1',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'fastapi',
        'uvicorn',
        'pymongo',
        'panda_common',
        'panda_data',
        'panda_factor',
        'pydantic',
        'tqsdk',
        'rqdatac',
        'tqdm',
        'redis',
        'apscheduler>=3.10.1',
    ],
    extras_require={
        'test': [
            'pytest',
            'pytest-asyncio',
            'httpx',
        ],
    },
    entry_points={
        'console_scripts': [
            'panda_factor_server = panda_factor_server.__main__:app',
        ],
    },
) 