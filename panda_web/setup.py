from setuptools import setup, find_packages

setup(
    name="panda_web",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.68.0",
        "uvicorn>=0.15.0",
        "python-multipart>=0.0.5",
        "aiofiles>=0.7.0",
        "panda_common"
    ],
    entry_points={
        "console_scripts": [
            "panda_web=panda_web.main:main",
        ],
    },
    author="PandaAI Team",
    author_email="team@pandaai.com",
    description="Web interface service for PandaAI platform",
    keywords="web,vue,fastapi",
    python_requires=">=3.8",
) 