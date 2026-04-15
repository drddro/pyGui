from typing import Concatenate, TypeAlias, Callable, ParamSpec, TypeVar

SelfT = TypeVar("SelfT")
P = ParamSpec('P')
R = TypeVar('R')

Check: TypeAlias = Callable[[SelfT], bool]
Method: TypeAlias = Callable[Concatenate[SelfT, P], R]

Decorator: TypeAlias = Callable[[Method[SelfT, P, R]], Method[SelfT, P, R]]


def requires_checks(*required_checks: Check[SelfT], error_message: str | None = None) -> Decorator[SelfT, P, R]:
    def decorator(method: Method[SelfT, P, R]) -> Method[SelfT, P, R]:
        def wrapper(self: SelfT, *args: P.args, **kwargs: P.kwargs) -> R:
            for check in required_checks:
                if not check(self):
                    if error_message is not None:
                        raise RuntimeError(error_message)
                    else:
                        raise RuntimeError(f'Check {check.__name__} failed for method {method.__name__}.')
            return method(self, *args, **kwargs)
        return wrapper
    return decorator




    