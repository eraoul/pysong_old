
import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="pysong",
    version="1.0.0",
    author="Eric Nichols",
    author_email="epnichols@gmail.com",
    description="A package providing data structures for representing symbolic musical scores",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="http://github.com/eraoul/pysong",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
) 
