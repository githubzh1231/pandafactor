from setuptools import setup, find_packages

setup(
    name="panda_common",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        'panda_common': [
            'handlers/**/*',
            'models/**/*',
            'utils/**/*',
            '*.yaml',
        ],
    },
    install_requires=[
        "loguru>=0.6.0",
        "PyYAML>=6.0",
        "pymongo",
        "redis"
    ],
    python_requires=">=3.9",
) 