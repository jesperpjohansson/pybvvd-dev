# pybvvd
![PyPI](https://img.shields.io/badge/PyPI-not%20available-red.svg)
![Python](https://img.shields.io/badge/Python-3.12%20%7C%203.13%20%7C%203.14-blue.svg)
[![License](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://github.com/jesperpjohansson/pybvvd-dev/blob/main/LICENSE)
[![CI](https://github.com/jesperpjohansson/pybvvd-dev/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/jesperpjohansson/pybvvd-dev/actions/workflows/ci.yml?branch=main)
[![Coverage](https://coveralls.io/repos/github/jesperpjohansson/pybvvd-dev/badge.svg?branch=main)](https://coveralls.io/github/jesperpjohansson/pybvvd-dev?branch=main)
[![Documentation](https://readthedocs.org/projects/pybvvd/badge/?version=latest)](https://pybvvd.readthedocs.io/en/latest/)


Python SDK for Bolagsverket's *Värdefulla Datamängder* API.

> [!IMPORTANT]
> `pybvvd` is an independent project and **is not affiliated with, endorsed by, or
> sponsored by Bolagsverket**. Use responsibly and comply with Bolagsverket's terms of 
> service.
---

## Features

- **Synchronous and asynchronous clients**
  - Built on top of `httpx.Client` and `httpx.AsyncClient`

- **Integrated OAuth2 (Client Credentials Grant) support**
  - Token issuance and revocation
  - Thread-safe and async-safe token management
  - Configurable token expiry handling
  - Optional single-token mode

- **Typed request and response models**
  - Implemented using `pydantic`
  - Validation of API responses

- **Robust error handling**
  - Structured API errors mapped to Python exceptions
  - OAuth2 errors handled explicitly
  - Graceful fallback when error payloads cannot be parsed

- **Environment support**
  - Seamless switching between production and test environments

## Documentation

User-oriented documentation is available [here](https://pybvvd.readthedocs.io/en/latest/).

## License

This project is licensed under the [BSD 3-Clause License](https://github.com/jesperpjohansson/pybvvd-dev/blob/main/LICENSE).
