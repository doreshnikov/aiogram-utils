from setuptools import setup

setup(
    name='aiogram-utils',
    version='0.1.0',
    author='Daniel Oreshnikov',
    author_email='dan.io.oreshnikov@gmail.com',

    description='aiogram library utils',
    long_description=open('README.md').read(),
    url='https://github.com/doreshnikov/aiogram-utils',

    packages=['tgutils'],

    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.12',
    install_requires=[
        'aiogram>=3.13.1',
        'emoji>=2.13.2',
    ]
)
