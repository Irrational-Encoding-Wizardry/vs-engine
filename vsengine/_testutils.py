"""
This allows test-cases to forcefully unregister a policy, e.g.
in case of test-failures.

This should ensure that failing tests can safely clean up the currently
running policy.

It works by implementing a proxy policy and monkey-patching
vapoursynth.register_policy.
"""
import typing as t

from vapoursynth import EnvironmentPolicyAPI, EnvironmentPolicy
from vapoursynth import EnvironmentData

import vapoursynth as vs


class ProxyPolicy(EnvironmentPolicy):
    _api: EnvironmentPolicyAPI|None
    _policy: EnvironmentPolicy|None

    __slots__ = ("_api", "_policy")

    def __init__(self) -> None:
        self._api = None
        self._policy = None

    def attach_policy_to_proxy(self, policy: EnvironmentPolicy):
        if self._api is None:
            raise RuntimeError("This proxy is not active")
        if self._policy is not None:
            orig_register_policy(policy)
            raise SystemError("Unreachable code")

        self._policy = policy
        try:
            policy.on_policy_registered(EnvironmentPolicyAPIWrapper(self._api, self))
        except:
            self._policy = None
            raise

    def forcefully_unregister_policy(self):
        if self._policy is None:
            return
        if self._api is None:
            return

        self._api.unregister_policy()
        orig_register_policy(self)


    def on_policy_registered(self, special_api: EnvironmentPolicyAPI) -> None:
        self._api = special_api
        vs.register_policy = self.attach_policy_to_proxy

    def on_policy_cleared(self) -> None:
        try:
            if self._policy is not None:
                self._policy.on_policy_cleared()
        finally:
            self._policy = None
            self._api = None
            vs.register_policy = orig_register_policy

    def get_current_environment(self) -> EnvironmentData|None:
        if self._policy is None:
            raise RuntimeError("This proxy is not attached to a policy.")
        return self._policy.get_current_environment()

    def set_environment(self, environment: EnvironmentData|None) -> None:
        if self._policy is None:
            raise RuntimeError("This proxy is not attached to a policy.")
        return self._policy.set_environment(environment)

    def is_alive(self, environment: EnvironmentData) -> bool:
        if self._policy is None:
            raise RuntimeError("This proxy is not attached to a policy.")
        return self._policy.is_alive(environment)


CURRENT_PROXY: ProxyPolicy|None = None
orig_register_policy = vs.register_policy


class EnvironmentPolicyAPIWrapper:
    _api: EnvironmentPolicyAPI
    _proxy: ProxyPolicy

    __slots__ = ("_api", "_proxy")

    def __init__(self, api, proxy) -> None:
        self._api = api
        self._proxy = proxy

    def __getattr__(self, __name: str) -> t.Any:
        return getattr(self._api, __name)

    def unregister_policy(self):
        self._proxy.forcefully_unregister_policy()


_policy = ProxyPolicy()
orig_register_policy(_policy)

forcefully_unregister_policy = _policy.forcefully_unregister_policy
