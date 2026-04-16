# Usage

## Sync

A demonstration of how to use the `pybvvd.TokenManager` and `pybvvd.Client` to fetch organisation data.

```python

import httpx
import pybvvd

def main():

    client_credentials = pybvvd.oauth2.ClientCredentials(
        client_id="abc123",
        client_secret="def456"
    )

    with httpx.Client() as session:
        token_manager = pybvvd.TokenManager(
            session,
            client_credentials,
            test_environment=True
        )
        token_manager.issue_access_token()
        bvvd = pybvvd.Client(session, token_manager)
        org_data = bvvd.organisationer(identitetsbeteckning="5560986878")
        print(org_data)

if __name__ == "__main__":
    main()
```

## Async

A demonstration of how to use the `pybvvd.AsyncTokenManager` and `pybvvd.AsyncClient` to fetch organisation data.

```python

import httpx
import pybvvd

def main():

    client_credentials = pybvvd.oauth2.ClientCredentials(
        client_id="abc123",
        client_secret="def456"
    )

    async with httpx.AsyncClient() as session:
        token_manager = pybvvd.AsyncTokenManager(
            session,
            client_credentials,
            test_environment=True
        )
        await token_manager.issue_access_token()
        bvvd = pybvvd.AsyncClient(session, token_manager)
        await org_data = bvvd.organisationer(identitetsbeteckning="5560986878")
        print(org_data)

if __name__ == "__main__":
    main()
```