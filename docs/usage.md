# Usage

## Sync

A demonstration of how to create a synchronous client from OAuth2 client
credentials and fetch organisation data.

```python
import httpx
import pybvvd

def main() -> None:
    client_credentials: pybvvd.oauth2.ClientCredentials = {
        "client_id": "abc123",
        "client_secret": "def456",
    }

    with httpx.Client() as session:
        bvvd = pybvvd.Client.from_credentials(
            session,
            client_credentials,
            test_environment=True,
        )
        org_data = bvvd.organisationer(identitetsbeteckning="5560986878")
        print(org_data)

if __name__ == "__main__":
    main()
```

## Async

A demonstration of how to create an asynchronous client from OAuth2 client
credentials and fetch organisation data.

```python
import asyncio
import httpx
import pybvvd

async def main() -> None:
    client_credentials: pybvvd.oauth2.ClientCredentials = {
        "client_id": "abc123",
        "client_secret": "def456",
    }

    async with httpx.AsyncClient() as session:
        bvvd = await pybvvd.AsyncClient.from_credentials(
            session,
            client_credentials,
            test_environment=True,
        )
        org_data = await bvvd.organisationer(identitetsbeteckning="5560986878")
        print(org_data)

if __name__ == "__main__":
    asyncio.run(main())
```
