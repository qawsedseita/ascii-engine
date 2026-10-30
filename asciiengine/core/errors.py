"""Explanatory errors: every EngineError carries a human/AI readable ``hint``."""


class EngineError(Exception):
    def __init__(self, message: str, hint: str = "", code: str = "error"):
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.code = code

    def __str__(self):
        return f"{self.message}" + (f" (hint: {self.hint})" if self.hint else "")

    def to_dict(self):
        return {"ok": False, "code": self.code, "error": self.message, "hint": self.hint}
