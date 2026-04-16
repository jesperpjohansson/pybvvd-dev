"""
Exception types used by pybvvd.

This module defines the exception hierarchy for errors raised when interacting
with the Bolagsverket Värdefulla Datamängder API.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic import AwareDatetime


class BVVDError(Exception):
    """Base exception for all pybvvd-related errors."""


class APIError(BVVDError):
    """
    Exception raised for API errors.

    This exception represents unsuccessful responses from the API endpoints
    (excluding OAuth2-related errors), such as invalid requests or server-side
    failures.
    """

    def __init__(  # noqa: PLR0913
        self,
        *,
        type_: str,
        instance: str,
        status: int,
        timestamp: AwareDatetime | None,
        requestId: str | None,  # noqa: N803
        title: str,
        detail: str | None,
    ) -> None:
        self.type_ = type_
        self.instance = instance
        self.status = status
        self.timestamp = timestamp
        self.requestId = requestId
        self.title = title
        self.detail = detail

        super().__init__(self.__str__())

    def __str__(self) -> str:
        parts = [f"{self.status} {self.title}"]

        if self.detail:
            parts.append(self.detail)

        parts.append(f"type: {self.type_}")
        parts.append(f"instance: {self.instance}")

        if self.requestId:
            parts.append(f"request ID: {self.requestId}")

        if self.timestamp:
            parts.append(f"timestamp: {self.timestamp}")

        return " | ".join(parts)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"type_={self.type_!r}, "
            f"instance={self.instance!r}, "
            f"status={self.status!r}, "
            f"timestamp={self.timestamp!r}, "
            f"requestId={self.requestId!r}, "
            f"title={self.title!r}, "
            f"detail={self.detail!r})"
        )


class OAuth2Error(BVVDError):
    """
    Exception raised for OAuth2 token endpoint errors.

    This exception is raised when the OAuth2 authorization server returns
    an error response, typically for token or revocation requests. It
    encapsulates both the HTTP status code and the structured OAuth2 error
    fields defined in RFC 6749.

    Parameters
    ----------
    status_code : int
        HTTP status code returned by the authorization server.
    error : str
        Machine-readable OAuth2 error code.
    error_description : str | None, optional
        Human-readable explanation of the error.
    error_uri : str | None, optional
        URI providing additional information about the error.
    """

    def __init__(
        self,
        *,
        status_code: int,
        error: str,
        error_description: str | None = None,
        error_uri: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.error = error
        self.error_description = error_description
        self.error_uri = error_uri

        super().__init__(self.__str__())

    def __str__(self) -> str:
        parts = [f"{self.status_code} {self.error}"]

        if self.error_description:
            parts.append(f"description: {self.error_description}")

        if self.error_uri:
            parts.append(f"URI: {self.error_uri}")

        return " | ".join(parts)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"status_code={self.status_code!r}, "
            f"error={self.error!r}, "
            f"error_description={self.error_description!r}, "
            f"error_uri={self.error_uri!r})"
        )
