# pybvvd
![PyPI](https://img.shields.io/badge/PyPI-not%20available-red.svg)
![Python](https://img.shields.io/badge/Python-3.12%20%7C%203.13-blue.svg)
[![License](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://github.com/jesperpjohansson/pybvvd-dev/blob/main/LICENSE)

Python SDK for Bolagsverket's *Värdefulla Datamängder* API.

!!! note
    The API is functional, documented, and tested. However, `pybvvd` is still in the **late stages of development**; hence:
    
    - The package is not published on PyPI.
    - The API is not guaranteed to be stable.
    - Breaking changes may occur without prior notice or semantic versioning.
    - Documentation may be incomplete or contain inaccuracies.

!!! warning
    `pybvvd` is an independent project and **is not affiliated with, endorsed by, or
    sponsored by Bolagsverket**. Use responsibly and comply with Bolagsverket's terms of service.
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

## Install

### PyPI

!!! note
    Not available at the moment.
```bash
pip install pybvvd
```

### Source

```bash
git clone https://github.com/jesperpjohansson/pybvvd-dev.git
cd pybvvd-dev
pip install .
```

## License

This project is licensed under the [BSD 3-Clause License](https://github.com/jesperpjohansson/pybvvd-dev/blob/main/LICENSE).