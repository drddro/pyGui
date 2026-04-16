from typing import Concatenate, TypeAlias, Callable, ParamSpec, TypeVar
from functools import wraps

SelfT = TypeVar("SelfT")
P = ParamSpec('P')
R = TypeVar('R')

Method: TypeAlias = Callable[Concatenate[SelfT, P], R]
Decorator: TypeAlias = Callable[[Method[SelfT, P, R]], Method[SelfT, P, R]]

#region Lock Decorator
Lock: TypeAlias = Callable[[SelfT], bool]
Check: TypeAlias = Lock[SelfT]

class LockError(RuntimeError):

    def __init__(self, lock_name: str, method_name: str):
        super().__init__(f'Lock {lock_name} failed for method {method_name}.')

    @staticmethod
    def from_lock_message(lock_fail_message: str, method_name: str) -> 'LockError':
        return LockError(lock_fail_message, method_name)


def locks(*locks: Check[SelfT], error_message: str | None = None) -> Decorator[SelfT, P, R]:
    def decorator(method: Method[SelfT, P, R]) -> Method[SelfT, P, R]:
        @wraps(method)
        def wrapper(self: SelfT, *args: P.args, **kwargs: P.kwargs) -> R:
            for lock in locks:
                if lock(self):
                    continue
                raise PermissionError(error_message or f"{lock.__name__} check failed")
            return method(self, *args, **kwargs)
        return wrapper
    return decorator

#endregion


