# Better News
A tool that uses locally-running LLMs to classify news articles from public sources

## Setup

Make sure you have pyenv installed. To install pyenv:

- Windows: `choco install pyenv-win`
- MacOS: `brew install pyenv`

Make sure pyenv is up to date with `pyenv update`.

This project has been tested with Python 3.13.2.
It can be installed with pyenv via `pyenv install 3.13.2`.

Once installed, set the local Python installation with `pyenv local 3.13.2`.

### Create a virtual environment

```
python -m venv .venv
```

### Activate the virtual environment

Windows: `.venv\Scripts\activate.bat`
MacOS and Linux: `./venv/Scripts/activate`

### Install pip-tools

```
pip install pip-tools
```

### Compile and install the requirements

```
pip-compile && pip-sync
```