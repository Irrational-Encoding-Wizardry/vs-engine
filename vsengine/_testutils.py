# vs-engine
# Copyright (C) 2022  cid-chan
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
This allows test-cases to forcefully unregister a policy,
e.g. in case of test-failures.

This should ensure that failing tests can safely clean up the current policy.

It works by implementing a proxy policy 
and monkey-patching vapoursynth.register_policy.

This policy is transparent to subsequent policies registering themselves.

To unregister a policy, run forcefully_unregister_policy.

As an addition,
it prevents VapourSynth from creating a vapoursynth.StandalonePolicy.
This ensures that no misbehaving test can accidentally prevent policy-based
tests from registering their own policies.

For policy-unrelated tests, use the function use_standalone_policy.
This function will build a policy which only ever uses one environment.
"""

import typing as t
from vapoursynth import EnvironmentPolicyAPI, EnvironmentPolicy
from vapoursynth import EnvironmentData

import vapoursynth as vs


__all__ = [
    "forcefully_unregister_policy",
    "use_standalone_policy"
]


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


class StandalonePolicy:
    _current: EnvironmentData|None
    _api: EnvironmentPolicyAPI|None
    __slots__ = ("_current", "_api")

    def __init__(self) -> None:
        self._current = None
        self._api = None

    def on_policy_registered(self, special_api: EnvironmentPolicyAPI) -> None:
        self._api = special_api
        self._current = special_api.create_environment()

    def on_policy_cleared(self):
        assert self._api is not None
        self._api.destroy_environment(self._current)
        self._current = None

    def get_current_environment(self):
        return self._current

    def set_environment(self, environment: EnvironmentData|None):
        if environment is not None and environment is not self._current:
            raise RuntimeError("No other environments should exist.")

    def is_alive(self, environment: EnvironmentData):
        return self._current is environment


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


def use_standalone_policy():
    _policy.attach_policy_to_proxy(StandalonePolicy())
