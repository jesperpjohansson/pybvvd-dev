"""
OAuth2 data models for Client Credentials Grant (RFC 6749).

The models reflect Bolagsverket's implementation and may be more restrictive than
the specifications in RFC 6749.
"""

from enum import StrEnum
from typing import Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field


class ClientCredentials(TypedDict):
    """
    OAuth2 client credentials used to request access tokens.

    Attributes
    ----------
    client_id : str
        OAuth2 client identifier issued by the API provider.
    client_secret : str
        Secret associated with the client identifier.
    """

    client_id: str
    client_secret: str


class ErrorCode(StrEnum):
    """
    Standard OAuth2 error codes returned by the authorization server.

    These values correspond to the error identifiers defined in RFC 6749
    and are included in error responses from the token and revocation
    endpoints.
    """

    INVALID_CLIENT = "invalid_client"
    INVALID_REQUEST = "invalid_request"
    INVALID_GRANT = "invalid_grant"
    UNAUTHORIZED_CLIENT = "unauthorized_client"
    UNSUPPORTED_GRANT_TYPE = "unsupported_grant_type"
    INVALID_SCOPE = "invalid_scope"


class AccessTokenResponse(BaseModel):
    """
    OAuth2 access token response.

    This model represents a successful response from the OAuth2 token
    endpoint when requesting an access token using a supported grant
    type (e.g. ``client_credentials``).
    """

    model_config = ConfigDict(
        extra="forbid",
    )
    access_token: str = Field(..., description="Access token")
    token_type: Literal["Bearer"] = Field(..., description="Token type")
    expires_in: int = Field(..., description="Lifetime in seconds")
    scope: str = Field(..., description="Granted scopes")


class ErrorResponse(BaseModel):
    """
    OAuth2 error response.

    This model represents an error response returned by the OAuth2
    authorization server when a request to the token or revocation
    endpoint fails.
    """

    model_config = ConfigDict(
        extra="forbid",
    )
    error: ErrorCode = Field(..., description="OAuth2 error code")
    error_description: str | None = Field(
        None,
        description="Human-readable explanation",
    )
    error_uri: str | None = Field(None, description="URL with more information")
