# -*- coding: utf-8 -*-
"""Support cable-less connector-to-connector connections.

Direct connections can be written in the compact form::

    connections:
      - - X1: [1, 2]
        - X2: [1, 2]

They can also carry optional rendering metadata::

    connections:
      - - X1: [1, 2]
        - direct:
            color: RD
            label: 24 V
        - X2: [1, 2]

No Cable object is created, so direct connections have no cable node and no
cable BOM entry. The ``direct`` marker exists only to describe the edge.
"""

from copy import deepcopy
from typing import Any, Dict, Optional, Set


_STYLE_KEY = "_wireviz_direct_connection_styles"


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


def _is_direct_marker(entry: Any) -> bool:
    return isinstance(entry, dict) and len(entry) == 1 and "direct" in entry


def _direct_style(entry: Any) -> Dict[str, Any]:
    """Normalize the optional ``direct`` rendering attributes."""
    if not _is_direct_marker(entry):
        return {}

    value = entry["direct"]
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TypeError("direct must be a mapping containing color and/or label")

    unknown = set(value) - {"color", "label"}
    if unknown:
        raise ValueError(
            "Unknown direct connection attribute(s): " + ", ".join(sorted(unknown))
        )

    return {
        key: value[key]
        for key in ("color", "label")
        if key in value and value[key] is not None
    }


def _new_direct_arrow(styles: Dict[str, Dict[str, Any]], style: Dict[str, Any]) -> str:
    """Create a unique arrow token that is still accepted by WireViz' parser."""
    # is_arrow() accepts trailing whitespace. This gives every generated direct
    # connection a unique token without extending the core YAML parser.
    token = "--" + (" " * (len(styles) + 1))
    styles[token] = style
    return token


def expand_direct_connections(yaml_data: Dict) -> Dict:
    """Expand cable-less/direct connection syntax for the normal WireViz parser.

    Adjacent connector columns are joined automatically. An explicit ``direct``
    marker between two connector columns may specify ``color`` and ``label``.
    Existing cable and arrow based connection sets are left unchanged.
    """
    data = deepcopy(yaml_data)
    connectors = set(data.get("connectors", {}).keys())
    separator = data.get("options", {}).get("template_separator", ".")
    styles: Dict[str, Dict[str, Any]] = {}

    expanded_sets = []
    for connection_set in data.get("connections", []):
        if not isinstance(connection_set, list) or len(connection_set) < 2:
            expanded_sets.append(connection_set)
            continue

        expanded = []
        index = 0
        while index < len(connection_set):
            current = connection_set[index]

            if _is_direct_marker(current):
                if index == 0 or index == len(connection_set) - 1:
                    raise ValueError("direct must be placed between two connectors")
                previous = connection_set[index - 1]
                following = connection_set[index + 1]
                if not (
                    _is_connector_entry(previous, connectors, separator)
                    and _is_connector_entry(following, connectors, separator)
                ):
                    raise ValueError("direct must be placed between two connectors")
                expanded.append(_new_direct_arrow(styles, _direct_style(current)))
                index += 1
                continue

            if expanded:
                previous_source = connection_set[index - 1]
                if (
                    not _is_direct_marker(previous_source)
                    and _is_connector_entry(previous_source, connectors, separator)
                    and _is_connector_entry(current, connectors, separator)
                ):
                    expanded.append(_new_direct_arrow(styles, {}))

            expanded.append(current)
            index += 1

        expanded_sets.append(expanded)

    data["connections"] = expanded_sets
    data[_STYLE_KEY] = styles
    return data


def get_direct_connection_styles(yaml_data: Dict) -> Dict[str, Dict[str, Any]]:
    """Return generated-arrow -> rendering-style metadata."""
    return yaml_data.get(_STYLE_KEY, {})
