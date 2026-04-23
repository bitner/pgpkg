"""Migration graph: nodes = versions, edges = incremental files. Shortest path."""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from pathlib import Path

from .catalog import Catalog
from .errors import PlanError


@dataclass(frozen=True)
class PlanStep:
    from_version: str
    to_version: str
    file: Path


@dataclass(frozen=True)
class MigrationPlan:
    source: str | None  # None means "fresh install" — bootstrap from base
    target: str
    bootstrap_base: Path | None  # set when source is None
    steps: list[PlanStep]


def plan(
    catalog: Catalog,
    *,
    source: str | None,
    target: str,
) -> MigrationPlan:
    """Compute a deterministic plan from source to target.

    - If source is None, uses the base file for `target` (or for the highest released
      version <= target if target is 'unreleased') as bootstrap, then walks incrementals
      to `target` if needed.
    - If source == target, returns an empty plan with no bootstrap.
    - Edges are unweighted; uses BFS for deterministic shortest path. Ties are broken
      lexicographically by next-version name to keep the plan stable.
    """
    if source == target:
        return MigrationPlan(source=source, target=target, bootstrap_base=None, steps=[])

    # Bootstrap path
    if source is None:
        bootstrap_version = _choose_bootstrap_version(catalog, target)
        bootstrap_base = catalog.base_files[bootstrap_version]
        if bootstrap_version == target:
            return MigrationPlan(
                source=None, target=target, bootstrap_base=bootstrap_base, steps=[]
            )
        steps = _shortest_path(catalog, bootstrap_version, target)
        return MigrationPlan(source=None, target=target, bootstrap_base=bootstrap_base, steps=steps)

    # Incremental path
    if target not in catalog.versions:
        raise PlanError(f"Unknown target version: {target!r}")
    if source not in catalog.versions:
        raise PlanError(f"Source version {source!r} is unknown to the catalog.")
    steps = _shortest_path(catalog, source, target)
    return MigrationPlan(source=source, target=target, bootstrap_base=None, steps=steps)


def _choose_bootstrap_version(catalog: Catalog, target: str) -> str:
    """Pick a base file to bootstrap from.

    Strategy: prefer the base file that exactly matches `target`. Otherwise pick the
    highest released base file that is reachable from itself to `target` via edges.
    """
    if target in catalog.base_files:
        return target
    # No base for target — find the highest released base from which target is reachable.
    candidates = sorted(
        (v for v in catalog.base_files),
        key=lambda v: (v == "unreleased", v),
        reverse=True,
    )
    for candidate in candidates:
        try:
            _shortest_path(catalog, candidate, target)
        except PlanError:
            continue
        return candidate
    raise PlanError(
        f"No base file can reach target {target!r}. Run `pgpkg stageversion {target}` "
        "or provide a reachable bootstrap base."
    )


def _shortest_path(catalog: Catalog, source: str, target: str) -> list[PlanStep]:
    """BFS over edges. Raises PlanError if no path. Tie-broken by sorted neighbor name."""
    if source == target:
        return []

    # adjacency: from_v -> sorted list of (to_v, path) for determinism
    adj: dict[str, list[tuple[str, Path]]] = {}
    for from_v, to_v, path in catalog.edges:
        adj.setdefault(from_v, []).append((to_v, path))
    for nbrs in adj.values():
        nbrs.sort(key=lambda x: x[0])

    # Dijkstra-like with uniform weight, but using heap with (depth, neighbor_name) for stability.
    heap: list[tuple[int, str, str | None, Path | None]] = [(0, source, None, None)]
    came_from: dict[str, tuple[str, Path]] = {}
    visited: set[str] = set()

    while heap:
        depth, node, prev, edge_path = heapq.heappop(heap)
        if node in visited:
            continue
        visited.add(node)
        if prev is not None and edge_path is not None:
            came_from[node] = (prev, edge_path)
        if node == target:
            return _reconstruct(came_from, source, target)
        for nbr, path in adj.get(node, []):
            if nbr not in visited:
                heapq.heappush(heap, (depth + 1, nbr, node, path))

    raise PlanError(f"No incremental migration path from {source!r} to {target!r}.")


def _reconstruct(
    came_from: dict[str, tuple[str, Path]], source: str, target: str
) -> list[PlanStep]:
    steps: list[PlanStep] = []
    cur = target
    while cur != source:
        prev, path = came_from[cur]
        steps.append(PlanStep(from_version=prev, to_version=cur, file=path))
        cur = prev
    steps.reverse()
    return steps


def render_graph_dot(catalog: Catalog) -> str:
    """Return a Graphviz DOT representation of the version graph (for `pgpkg graph`)."""
    lines = ["digraph pgpkg {", "  rankdir=LR;"]
    for v in catalog.versions:
        marker = " [shape=box]" if v in catalog.base_files else ""
        lines.append(f'  "{v}"{marker};')
    for from_v, to_v, _ in catalog.edges:
        lines.append(f'  "{from_v}" -> "{to_v}";')
    lines.append("}")
    return "\n".join(lines) + "\n"


def render_graph_text(catalog: Catalog) -> str:
    """Return a human-readable text representation."""
    lines = ["Versions:"]
    for v in catalog.versions:
        marker = " (base)" if v in catalog.base_files else ""
        lines.append(f"  - {v}{marker}")
    lines.append("")
    lines.append("Edges:")
    if not catalog.edges:
        lines.append("  (none)")
    else:
        for from_v, to_v, path in catalog.edges:
            lines.append(f"  {from_v} -> {to_v}  [{path.name}]")
    return "\n".join(lines) + "\n"
