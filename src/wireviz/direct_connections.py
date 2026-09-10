# -*- coding: utf-8 -*-
"""Support cable-less connector-to-connector connections.

A direct connection is written exactly like a normal connection set, but without
an intermediate cable or mating arrow::

    connections:
      - - X1: [1, 2]
        - X2: [1, 2]

Internally this module expands such adjacent connector entries to WireViz' pin
mate representation (``--``). No Cable object is created, so the connection
has no cable node and no cable BOM entry.
"""

from copy import deepcopy
from typing import Any, Dict, Optional, Set


def _entry_designator(entry: Any) -> Optional[str]:
    """Return the designator/template token used by a connection-set entry."""
    if isinstance(entry, dict) and len(entry) == 1:
        return next(iter(entry))
    if isinstance(entry, str):
        return entry
    if isinstance(entry, list) and entry and all(isinstance(x, str) for x in entry):
        return entry[0]
    return None


def _template_name(token: str, separator: str) -> str:
    return token.split(separator, 1)[0] if separator in token else token


def _is_connector_entry(
    entry: Any, connector_templates: Set[str], separator: str
) -> bool:
    token = _entry_designator(entry)
    return token is not None and _template_name(token, separator) in connector_templates


def expand_direct_connections(yaml_data: Dict) -> Dict:
    """Return YAML data with adjacent connector columns joined by ``--``.

    Existing cable and arrow based connection sets are left unchanged. The
    transformation is deliberately performed before the regular WireViz parser
    so all existing validation, pin expansion and GraphViz generation continue
    to be used.
    """
    data = deepcopy(yaml_data)
    connectors = set(data.get("connectors", {}).keys())
    separator = data.get("options", {}).get("template_separator", ".")

    expanded_sets = []
    for connection_set in data.get("connections", []):
        if not isinstance(connection_set, list) or len(connection_set) < 2:
            expanded_sets.append(connection_set)
            continue

        expanded = [connection_set[0]]
        for current in connection_set[1:]:
            previous = expanded[-1]
            if (
                _is_connector_entry(previous, connectors, separator)
                and _is_connector_entry(current, connectors, separator)
            ):
                # ``--`` is WireViz' pin-by-pin mate. It creates no Cable and
                # therefore no cable node/BOM item.
                expanded.append("--")
            expanded.append(current)
        expanded_sets.append(expanded)

    data["connections"] = expanded_sets
    return data
