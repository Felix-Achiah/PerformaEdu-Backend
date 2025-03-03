from setuptools import setup, find_packages

setup(
    name="user_auth",  # Name of the package
    version="0.1.0",   # Version of the package
    packages=find_packages(),  # Automatically find all Python packages in the directory
    install_requires=[],
    description="A reusable user authentication app for Django projects.",
    author="Achiah Ekow Felix",
    author_email="felixachiah@gmail.com",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Framework :: Django",
        "Operating System :: OS Independent",
    ],
)