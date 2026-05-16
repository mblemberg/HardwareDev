"""Content-addressed hashing for DAG nodes.

A node's hash is sha256(framework_version + function_source + sorted_ancestor_hashes).
Leaf inputs are hashed from their canonical representation. Two runs produce
the same hash for a node iff:

- the framework version is unchanged, AND
- the function source bytes are unchanged, AND
- every transitive ancestor produced the same hash — which recursively means
  every input leaf serialized to the same bytes and every function up the
  chain has the same source.

Pickle is *not* used for the hash key — it's not stable across Python
versions. The hash key is derived from a deterministic string serialization
(:func:`canonical_repr`); pickle is used elsewhere only for *value* storage,
where stability across Python versions doesn't matter for the same machine.
"""
from __future__ import annotations

import hashlib
import inspect
import types
from typing import Any

import pint
from pydantic import BaseModel

from framework.quantity import Quantity


def canonical_repr(value: Any) -> str:
    """Deterministic string representation for hashing.

    Stable across processes, sorts dict keys, normalizes Pint quantities and
    framework values into a recursive form. Two values that should hash the
    same must produce identical strings here.
    """
    if value is None:
        return "None"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return f"int({value})"
    if isinstance(value, float):
        # repr is stable for floats across CPython versions; covers nan/inf.
        return f"float({value!r})"
    if isinstance(value, str):
        return f"str({value!r})"
    if isinstance(value, bytes):
        return f"bytes({value.hex()})"

    if isinstance(value, Quantity):
        return (
            "Quantity("
            f"unit={value.unit!s},"
            f"nominal={canonical_repr(value.nominal)},"
            f"by_scenario={canonical_repr(value.by_scenario)},"
            f"by_mode={canonical_repr(value.by_mode)}"
            ")"
        )
    if isinstance(value, pint.Quantity):
        return f"pq({canonical_repr(float(value.magnitude))},{value.units!s})"
    if isinstance(value, pint.Unit):
        return f"pu({value!s})"

    if isinstance(value, BaseModel):
        # Pydantic's model_dump_json sorts keys at the top level but not
        # nested -- so go through model_dump and serialize ourselves.
        return f"{type(value).__name__}({canonical_repr(value.model_dump(mode='python'))})"

    if isinstance(value, tuple):
        return "(" + ",".join(canonical_repr(v) for v in value) + ")"
    if isinstance(value, list):
        return "[" + ",".join(canonical_repr(v) for v in value) + "]"
    if isinstance(value, (set, frozenset)):
        return "{" + ",".join(sorted(canonical_repr(v) for v in value)) + "}"
    if isinstance(value, dict):
        items = sorted(value.items(), key=lambda kv: canonical_repr(kv[0]))
        return "{" + ",".join(f"{canonical_repr(k)}:{canonical_repr(v)}" for k, v in items) + "}"

    # Last-resort fallback for unknown types. repr is *usually* stable for
    # well-behaved objects; if a user's leaf returns something exotic and
    # gets spurious cache misses, they'll notice and ask.
    return f"<{type(value).__module__}.{type(value).__name__}>({value!r})"


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def collect_module_functions(
    modules: list[types.ModuleType],
) -> dict[str, tuple[types.FunctionType, list[str], str]]:
    """For each user-defined top-level function in the given modules, return:

    ``{name: (function_object, parameter_names, source_bytes)}``.

    Skips dunders, callables defined elsewhere (re-exports), and non-functions.
    Source comes from :func:`inspect.getsource` — captures decorators and the
    full def block.
    """
    out: dict[str, tuple[types.FunctionType, list[str], str]] = {}
    for module in modules:
        for attr in dir(module):
            if attr.startswith("_"):
                continue
            obj = getattr(module, attr, None)
            if not inspect.isfunction(obj):
                continue
            if obj.__module__ != module.__name__:
                continue  # re-export from elsewhere
            sig = inspect.signature(obj)
            params = list(sig.parameters.keys())
            try:
                src = inspect.getsource(obj)
            except (OSError, TypeError):
                src = repr(obj)  # interactive / generated functions
            if attr in out:
                # Two modules declaring the same node name. Hamilton would also
                # complain, but flag it precisely from us first.
                raise ValueError(
                    f"duplicate DAG node name {attr!r} found in modules "
                    f"{out[attr][0].__module__!r} and {module.__name__!r}"
                )
            out[attr] = (obj, params, src)
    return out


def compute_node_hashes(
    modules: list[types.ModuleType],
    inputs: dict[str, Any],
    framework_version: str,
) -> dict[str, str]:
    """Compute content-addressed hashes for every node reachable from ``modules``.

    Returns ``{node_name: sha256_hex}``. Function nodes' hashes depend on
    ``framework_version`` + their source bytes + sorted ancestor hashes
    (computed in topological order). Input nodes are hashed from their
    canonical representation.

    Nodes whose dependencies aren't satisfied by either another function or
    an input are omitted — Hamilton will raise at execute-time with a clearer
    error than we could produce here.
    """
    fn_table = collect_module_functions(modules)

    hashes: dict[str, str] = {}
    for name, value in inputs.items():
        hashes[name] = sha256_hex(f"input:{name}\n{canonical_repr(value)}")

    # Topological pass: keep resolving functions whose deps are all hashed.
    remaining = dict(fn_table)
    while remaining:
        progress = False
        for name, (_fn, deps, src) in list(remaining.items()):
            if all(d in hashes for d in deps):
                ancestor_hashes = sorted(hashes[d] for d in deps)
                content = (
                    f"framework={framework_version}\n"
                    f"node={name}\n"
                    f"src={src}\n"
                    f"ancestors={','.join(ancestor_hashes)}"
                )
                hashes[name] = sha256_hex(content)
                del remaining[name]
                progress = True
        if not progress:
            # One or more functions have an unsatisfied dependency.
            # Don't error — let Hamilton report it. We just skip hashing them.
            break
    return hashes


__all__ = [
    "canonical_repr",
    "collect_module_functions",
    "compute_node_hashes",
    "sha256_hex",
]
