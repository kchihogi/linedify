from setuptools import setup, find_packages

setup(
    name="linedify-kchihogi",
    version="0.3.1-fork",
    url="https://github.com/kchihogi/linedify",
    author="uezo",
    author_email="uezo@uezo.net",
    maintainer="kchihogi",
    maintainer_email="kchihogi@gmail.com",
    description="Forked version of linedify@0.3.1",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    packages=find_packages(exclude=["examples*", "tests*"]),
    install_requires=["aiohttp==3.9.5", "line-bot-sdk==3.11.0", "fastapi==0.111.0", "uvicorn==0.30.1", "SQLAlchemy==2.0.31"],
    license="Apache v2",
    classifiers=[
        "Programming Language :: Python :: 3"
    ]
)
