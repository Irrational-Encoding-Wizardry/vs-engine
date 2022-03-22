import logging
import typing as t
import threading
import contextlib
import contextvars
from vapoursynth import EnvironmentPolicy, EnvironmentPolicyAPI
from vapoursynth import Environment, EnvironmentData
from vapoursynth import register_policy
import vapoursynth as vs


__all__ = [
    "GlobalStore", "ThreadLocalStore", "ContextVarStore",
    "Policy", "ManagedEnvironment"
]


logger = logging.getLogger(__name__)


class EnvironmentStore(t.Protocol):
    """
    Environment Stores manage which environment is currently active.
    """
    def set_current_environment(self, environment: EnvironmentData|None):
        """
        Set the current environment in the store.
        """
        ...

    def get_current_environment(self) -> EnvironmentData|None:
        """
        Retrieve the current environment from the store (if any)
        """
        ...


class GlobalStore(EnvironmentStore):
    """
    This is the simplest store: It just stores the environment in a variable.
    """
    _current: EnvironmentData|None
    __slots__ = ("_current",)

    def __init__(self) -> None:
        self._current = None
    
    def set_current_environment(self, environment: EnvironmentData | None):
        self._current = environment

    def get_current_environment(self) -> EnvironmentData | None:
        return self._current


class ThreadLocalStore(EnvironmentStore):
    """
    For simple threaded applications, use this store.

    It will store the environment in a thread-local variable.
    """

    _current: threading.local

    def __init__(self) -> None:
        self._current = threading.local()

    def set_current_environment(self, environment: EnvironmentData | None):
        self._current.environment = environment

    def get_current_environment(self) -> EnvironmentData | None:
        return getattr(self._current, "environment", None)


class ContextVarStore(EnvironmentStore):
    """
    If you are using AsyncIO or similar frameworks, use this store.
    """
    _current: contextvars.ContextVar[EnvironmentData|None]

    def __init__(self, name: str="vapoursynth") -> None:
        self._current = contextvars.ContextVar(name)

    def set_current_environment(self, environment: EnvironmentData | None):
        self._current.set(environment)

    def get_current_environment(self) -> EnvironmentData | None:
        return self._current.get(None)


class _ManagedPolicy(EnvironmentPolicy):
    """
    This class directly interfaces with VapourSynth.
    """

    _api: EnvironmentPolicyAPI|None
    _store: EnvironmentStore
    _mutex: threading.Lock

    __slots__ = ("_api", "_store", "_mutex")

    def __init__(self, store: EnvironmentStore) -> None:
        self._store = store
        self._mutex = threading.Lock()
        self._api = None

    @property
    def api(self):
        if self._api is None:
            raise RuntimeError("Invalid state: No access to the current API")
        return self._api

    def on_policy_registered(self, special_api: EnvironmentPolicyAPI) -> None:
        logger.debug("Successfully registered policy with VapourSynth.")
        self._api = special_api

    def on_policy_cleared(self) -> None:
        self._api = None
        logger.debug("Policy cleared.")

    def get_current_environment(self) -> EnvironmentData|None:
        # We wrap everything in a mutex to make sure
        # no context-switch can reliably happen in this section.
        with self._mutex:
            current_environment = self._store.get_current_environment()
            if current_environment is None:
                return None

            if not self.is_alive(current_environment):
                logger.warn(f"Got dead environment: {current_environment!r}")
                # Remove the environment.
                self._store.set_current_environment(None)
                return None

            return current_environment

    def set_environment(self, environment: EnvironmentData) -> None:
        with self._mutex:
            if not self.is_alive(environment):
                logger.warn(f"Got dead environment: {environment!r}")
                self._store.set_current_environment(None)
            else:
                logger.debug(f"Setting environment: {environment!r}")
                self._store.set_current_environment(environment)


class ManagedEnvironment:
    _environment: Environment
    _data: EnvironmentData
    _policy: 'Policy'
    __slots__ = ("_environment", "_data", "_policy")

    def __init__(self, environment: Environment, data: EnvironmentData, policy: 'Policy') -> None:
        self._environment = environment
        self._data = data
        self._policy = policy

    @property
    def vs_environment(self):
        return self._environment

    @property
    def outputs(self) -> t.Mapping[int, vs.VideoOutputTuple]:
        with self.use():
            return vs.get_outputs()

    @contextlib.contextmanager
    def use(self) -> t.Generator[None, None, None]:
        """
        Switches to this environment within a block.
        """
        with self._environment.use():
            yield

    def dispose(self):
        if self._data is None:
            return

        logger.debug(f"Disposing environment {self._data!r}.")
        self._policy.api.destroy_environment(self._data)
        self._data = None

    def __enter__(self):
        return self

    def __exit__(self, _, __, ___):
        self.dispose()

    def __del__(self):
        if self._data is None:
            return

        logger.warning(f"Disposing environment {self._data!r} on __del__. This is not recommended.")
        self.dispose()


class Policy:
    """
    A managed policy is a very simple policy that just stores the environment
    data within the given store.

    For convenience (especially for testing), this is a context manager that
    makes sure policies are being unregistered when leaving a block.
    """
    _managed: _ManagedPolicy

    def __init__(self, store: EnvironmentStore) -> None:
        self._managed = _ManagedPolicy(store)

    def register(self):
        """
        Registers the policy with VapourSynth.
        """
        register_policy(self._managed)
    
    def unregister(self):
        """
        Unregisters the policy from VapourSynth.
        """
        self._managed.api.unregister_policy()

    def __enter__(self):
        self.register()
        return self

    def __exit__(self, _, __, ___):
        self.unregister()

    def new_environment(self) -> ManagedEnvironment:
        """
        Creates a new VapourSynth core.

        You need to call `dispose()` on this environment when you are done
        using the new environment.

        For convenience, a managed environment will also serve as a
        context-manager that disposes the environment automatically.
        """
        data = self.api.create_environment()
        env = self.api.wrap_environment(data)
        logger.debug("Created new environment")
        return ManagedEnvironment(env, data, self)

    @property
    def api(self):
        """
        Returns the API instance for more complex interactions.

        You will rarely need to use this directly.
        """
        return self._managed.api

    @property
    def managed(self):
        """
        Returns the actual policy within VapourSynth.

        You will rarely need to use this directly.
        """
        return self._managed
