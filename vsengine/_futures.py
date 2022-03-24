import inspect
import functools
import typing as t
from concurrent.futures import Future, CancelledError
from vsengine.loops import get_loop


T = t.TypeVar("T")

UnifiedRunner = t.Callable[..., Future[T]|t.Iterable[Future[T]]]
UnifiedCallable = t.Callable[..., t.Union['UnifiedFuture', 'UnifiedIterable']]


class UnifiedFuture(Future[T]):

    @classmethod
    def from_call(cls, func: UnifiedRunner[T], *args: t.Any, **kwargs: t.Any) -> 'UnifiedFuture[T]':
        try:
            future = func(*args, **kwargs)
        except Exception as e:
            future = Future()
            future.set_exception(e)
        future.__class__ = cls
        return t.cast(UnifiedFuture[T], future)

    def __enter__(self):
        obj = self.result()
        if hasattr(obj, "__enter__"):
            return t.cast(t.ContextManager[t.Any], obj).__enter__()
        else:
            raise NotImplementedError("(async) with is not implemented for this object.")

    def __exit__(self, exc, val, tb):
        obj = self.result()
        if hasattr(obj, "__exit__"):
            return t.cast(t.ContextManager[t.Any], obj).__exit__(exc, val, tb)
        else:
            raise NotImplementedError("(async) with is not implemented for this object.")

    def add_loop_callback(self, func: t.Callable[['UnifiedFuture[T]'], None]) -> None:
        def _wrapper(future):
            get_loop().from_thread(func, future)
        self.add_done_callback(_wrapper)

    async def awaitable(self):
        return await get_loop().await_future(self)

    def __await__(self):
        return self.awaitable().__await__()

    async def __aenter__(self):
        result = await self.awaitable()
        if hasattr(result, "__aenter__"):
            return await t.cast(t.AsyncContextManager[t.Any], result).__aenter__()
        elif hasattr(result, "__enter__"):
            return t.cast(t.ContextManager[t.Any], result).__enter__()
        else:
            raise NotImplementedError("(async) with is not implemented for this object.")

    async def __aexit__(self, exc, val, tb):
        result = await self.awaitable()
        if hasattr(result, "__aexit__"):
            return await t.cast(t.AsyncContextManager[t.Any], result).__aexit__(exc, val, tb)
        elif hasattr(result, "__exit__"):
            return t.cast(t.ContextManager[t.Any], result).__exit__(exc, val, tb)
        else:
            raise NotImplementedError("(async) with is not implemented for this object.")


class UnifiedIterable(t.Generic[T]):

    def __init__(self, future_iterable: t.Iterable[Future[T]]) -> None:
        self.future_iterable = future_iterable

    @classmethod
    def from_call(cls, func: UnifiedRunner[T], *args: t.Any, **kwargs: t.Any) -> 'UnifiedIterable[T]':
        return cls(func(*args, **kwargs))

    def __iter__(self):
        return self

    @property
    def futures(self):
        return self.future_iterable

    def __next__(self) -> T:
        fut = self.future_iterable.__next__()
        return fut.result()

    def __aiter__(self):
        return self

    async def __anext__(self) -> T:
        try:
            fut = self.future_iterable.__next__()
        except StopIteration:
            raise StopAsyncIteration
        return await get_loop().await_future(fut)


def unified(
        type: t.Literal["auto","generator","future"] = "auto",
        future_class: t.Type[UnifiedFuture[T]] = UnifiedFuture,
        iterable_class: t.Type[UnifiedIterable[T]] = UnifiedIterable,
) -> t.Callable[[UnifiedRunner[T]], UnifiedCallable]:
    def _wrap_generator(func: UnifiedRunner[T]) -> UnifiedCallable:
        @functools.wraps(func)
        def _wrapped(*args, **kwargs):
            return iterable_class.from_call(func, *args, **kwargs)
        return _wrapped

    def _wrap_future(func: UnifiedRunner[T]) -> UnifiedCallable:
        @functools.wraps(func)
        def _wrapped(*args, **kwargs):
            return future_class.from_call(func, *args, **kwargs)
        return _wrapped

    def _wrapper(func: UnifiedRunner[T]) -> UnifiedCallable:
        if type == "auto":
            if inspect.isgeneratorfunction(func):
                return _wrap_generator(func)
            else:
                return _wrap_future(func)
        elif type == "generator":
            return _wrap_generator(func)
        else:
            return _wrap_future(func)

    return _wrapper

