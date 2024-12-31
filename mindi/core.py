from typing import Callable, Any, TypeVar, ParamSpec, overload, Type
from inspect import signature, isfunction, isclass
from functools import wraps
from dataclasses import dataclass, field


# Type variables for generic types
T = TypeVar('T')
P = ParamSpec('P')


# Unique object to represent an undefined value (instead of None).
undefined = object()


@dataclass(slots=True, frozen=True)
class Use:
    key: str


@dataclass(slots=True, frozen=True)
class Provider:
    func: Callable
    kwargs: dict[str, Any]
    uses: dict[str, Use]


@dataclass(slots=True)
class Container:
    providers: dict[str, Provider] = field(default_factory=dict)
    instances: dict[str, Any] = field(default_factory=dict)
    rebind: bool = field(default=False)

    @overload
    def bind(self, __id: None, __fn: None, **kwargs) -> Callable[[T], T]: ...

    @overload
    def bind(self, __id: Type[T], __fn: Callable[P, T] | None, **kwargs) -> Type[T]: ...

    @overload
    def bind(self, __id: str, __fn: Callable[P, T] | Type[T], **kwargs) -> None: ...

    def bind(self, __id=None, __fn=None, **kwargs):
        if __id is None:
            if __fn is not None:
                raise TypeError("bind() missing 1 required positional argument: '__id'")

            # When used as @bind(...) class Foo
            def decorator(c: T) -> T:
                if not isinstance(c, type):
                    raise TypeError("'cls' must be a type")
                self.bind(c, **kwargs)
                return c
            return decorator

        if callable(__id):
            # When used as bind(Foo, ...) or bind(Foo, factory_fn, ...) or @bind class Foo
            key = identifier(__id)
            if __fn is not None and not callable(__fn):
                raise TypeError("'__fn' must be a callable if specified")
            fn = __id if __fn is None else __fn
        elif isinstance(__id, str):
            # When used as bind("Foo", factory_fn, ...)
            if __fn is None:
                raise TypeError("bind() missing 1 required positional argument: '__fn'")
            if not callable(__fn):
                raise TypeError("'__fn' must be a callable if specified")
            key = __id
            fn = __fn
        else:
            raise TypeError("'__id' must be a type or a string")

        if not self.rebind and self.providers.get(key) is not None:
            raise KeyError(f"Provider {key!r} already exists")

        self.providers[key] = Provider(fn, kwargs, get_call_uses(fn))
        self.instances[key] = undefined

        if callable(__id):
            return __id

    def use(self, __id: Callable | str) -> Use:
        if callable(__id):
            key = identifier(__id)
        elif isinstance(__id, str):
            key = __id
        else:
            raise TypeError("__id must be a callable or a string")
        return Use(key)

    def wire(self, input: Callable[P, T] | Type[T]) -> Callable[P, T]:
        if isfunction(input) or isclass(input):
            return self.__wire_wrap(input)
        else:
            raise TypeError("input must be a function or a class")

    def __wire_wrap(self, fn):
        uses = get_call_uses(fn)
        if not uses:
            return wraps(fn)(fn)

        sig = signature(fn)

        @wraps(fn)
        def wrapper(*args, **kwargs) -> T:
            bound_args = sig.bind_partial(*args, **kwargs)
            final_kwargs = dict(bound_args.arguments)

            for name, use in uses.items():
                if final_kwargs.get(name, undefined) is undefined:
                    final_kwargs[name] = self.instantiate(use.key)

            return fn(**final_kwargs)

        return wrapper

    def instantiate(self, key: str | None = None, trace: tuple[list, set] | None = None) -> Any:
        if key is None:
            # Instantiate all
            return {key: self.instantiate(key) for key in self.providers}

        instance = self.instances.get(key, undefined)
        if instance is not undefined:
            return instance

        if trace is None:
            trace = (list(), set())
        stack, stack_set = trace

        if key in stack_set:
            cycle_path = " -> ".join(stack[stack.index(key):] + [key])
            raise RuntimeError(f"Cycle detected: {cycle_path}")

        provider = self.providers.get(key, undefined)
        if provider is undefined:
            raise KeyError(f"No provider found for {key!r}")

        stack.append(key)
        stack_set.add(key)

        kwargs = provider.kwargs.copy()
        for arg, use in provider.uses.items():
            if kwargs.get(arg, undefined) is undefined:
                kwargs[arg] = self.instantiate(use.key, trace)

        instance = self.instances[key] = provider.func(**kwargs)

        stack.pop(-1)
        stack_set.remove(key)

        return instance


def identifier(t) -> str:
    module = getattr(t, "__module__", None)
    if module is None:
        raise AttributeError(f"{t!r} does not have the __module__ attribute")
    qualname = getattr(t, "__qualname__", None)
    if qualname is None:
        raise AttributeError(f"{t!r} does not have the __qualname__ attribute")
    return f'{module}.{qualname}'


def get_call_uses(o: Callable):
    try:
        sig = signature(o)
    except ValueError:
        return {}
    
    return {
        parameter.name: parameter.default
        for parameter in sig.parameters.values()
        if isinstance(parameter.default, Use)
    }
