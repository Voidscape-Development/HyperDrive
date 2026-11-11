"""What can go wrong asking a tournament data provider (start.gg, parry.gg),
so "it failed" can be told from "there's nothing": a provider method that
couldn't get its answer raises a ProviderError, and only returns something
empty when the provider said there's nothing. What shows the data keeps the
last it got when a request fails. Kept free of Qt.

A provider's public methods only raise inside `with RaiseProviderErrors():`,
which is how TournamentDataManager.Run and the stream queue call them.
Called directly, they log the error and return something empty, as they
always did: the web server's actions call them that way."""

import threading

from loguru import logger

# The network, the provider's servers, an answer that makes no sense: trying
# again later might work
KIND_TRANSIENT = "transient"
# The API key or token is missing, wrong, or not allowed to see this
KIND_AUTH = "auth"
# The tournament, event or set doesn't exist (anymore)
KIND_NOT_FOUND = "not_found"
# Too many requests: try again after a while
KIND_RATE_LIMITED = "rate_limited"

KINDS = (KIND_TRANSIENT, KIND_AUTH, KIND_NOT_FOUND, KIND_RATE_LIMITED)


class ProviderError(Exception):
    """A request to a provider failed. kind: one of KINDS."""

    kind = KIND_TRANSIENT

    def __init__(self, message="", kind=None, response=None):
        super().__init__(message)
        if kind is not None:
            self.kind = kind
        # What the provider answered, if anything (for the callers that
        # still read a failed answer)
        self.response = response

    @property
    def retryable(self):
        """Whether the same request might work later, without the user
        changing anything"""
        return self.kind in (KIND_TRANSIENT, KIND_RATE_LIMITED)


class TransientError(ProviderError):
    kind = KIND_TRANSIENT


class AuthError(ProviderError):
    kind = KIND_AUTH


class NotFoundError(ProviderError):
    kind = KIND_NOT_FOUND


class RateLimitedError(ProviderError):
    kind = KIND_RATE_LIMITED

    def __init__(self, message="", retryAfter=None, response=None):
        super().__init__(message, response=response)
        # Seconds the provider asked to wait, None if it didn't say
        self.retryAfter = retryAfter


def FromHttpStatus(status, message, response=None, retryAfter=None):
    """The error for an HTTP answer that isn't a success"""
    if status in (401, 403):
        return AuthError(message, response=response)
    if status == 404:
        return NotFoundError(message, response=response)
    if status == 429:
        return RateLimitedError(message, retryAfter=retryAfter, response=response)
    return TransientError(message, response=response)


def FromGrpc(error, what=""):
    """The error for a grpc.RpcError (parry.gg)"""
    import grpc

    code = error.code() if callable(getattr(error, "code", None)) else None
    details = error.details() if callable(getattr(error, "details", None)) else str(error)
    message = f"{what}: {details}" if what else str(details)
    if code in (grpc.StatusCode.UNAUTHENTICATED, grpc.StatusCode.PERMISSION_DENIED):
        return AuthError(message)
    if code == grpc.StatusCode.NOT_FOUND:
        return NotFoundError(message)
    if code == grpc.StatusCode.RESOURCE_EXHAUSTED:
        return RateLimitedError(message)
    return TransientError(message)


# =====================================================
# RAISING OR NOT
# =====================================================
_local = threading.local()


class RaiseProviderErrors:
    """with RaiseProviderErrors(): the provider methods this thread calls
    inside raise a ProviderError when they can't get their answer, instead
    of returning something empty"""

    def __enter__(self):
        _local.depth = getattr(_local, "depth", 0) + 1
        return self

    def __exit__(self, *args):
        _local.depth -= 1
        return False


def Raising():
    return getattr(_local, "depth", 0) > 0


def Failed(error, empty=None):
    """What a provider's public method does with the ProviderError that
    stopped it: raises it inside RaiseProviderErrors, else logs it and
    returns `empty`"""
    if Raising():
        raise error
    logger.error(f"{error.__class__.__name__}: {error}")
    return empty
