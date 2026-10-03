"""Safe, structured errors: never include credential-bearing request URLs."""


class ConnectorError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool = False) -> None:
        self.code = code
        self.retryable = retryable
        super().__init__(code)


class UnavailableError(ConnectorError):
    def __init__(self) -> None:
        super().__init__("unavailable")
