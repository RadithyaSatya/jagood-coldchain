class LLMError(Exception):
    """Base error for inference failures."""


class LLMTimeoutError(LLMError):
    """Raised when the inference server does not respond in time."""


class LLMServiceError(LLMError):
    """Raised when the inference server returns an invalid or failed response."""

