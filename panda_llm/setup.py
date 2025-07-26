from setuptools import setup, find_packages
import os

# 确保当前目录中有一个panda_llm目录
if not os.path.exists('panda_llm'):
    os.makedirs('panda_llm')
    with open('panda_llm/__init__.py', 'a'):
        pass

setup(
    name='panda_llm',
    version='0.1.0',
    description='Panda AI LLM integration service',
    author='Panda AI',
    packages=find_packages(),
    include_package_data=True,
    package_data={
        'panda_llm': [
            'services/**/*',
            'models/**/*',
            'routes/**/*',
            '*.yaml',
        ],
    },
    install_requires=[
        'fastapi>=0.104.1',
        'uvicorn>=0.24.0',
        'pydantic>=2.4.2',
        'aiohttp>=3.9.1',
        'pyyaml>=6.0.1',
        'python-dotenv>=1.0.0',
        'openai>=1.0.0',
        'panda_common',
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
            'panda_llm = panda_llm.__main__:main',
        ],
    },
) 