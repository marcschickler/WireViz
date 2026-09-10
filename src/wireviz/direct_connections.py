# -*- coding: utf-8 -*-
"""Support cable-less connector-to-connector connections.

Direct connections can be written in the normal ``connections`` section::

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

For very compact 1:1 wiring, this fork additionally supports a top-level
``direct`` section::

    direct:
      X1-X2: [BN, BK, GR, YE]

This is expanded to pin 1 -> 1, 2 -> 2, ... and uses the listed color for each
individual wire. No Cable object is created, so direct connections have no
cable node and no cable BOM entry.
"""

from copy import deepcopy
from typing import Any, Dict, List, Optional, Set, Tuple


_STYLE_KEY = "_wireviz_direct_connection_styles"
_COLOR_ALIASES = {
    "GR": "GY",  # grey: convenient alias for German-oriented wiring descriptions
}


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
    """Normalize the optional scalar ``direct`` rendering attributes."""
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

    style = {
        key: value[key]
        for key in ("color", "label")
        if key in value and value[key] is not None
    }
    if "color" in style and isinstance(style["color"], str):
        color = style["color"].strip().upper()
        style["color"] = _COLOR_ALIASES.get(color, color)
    return style


def _new_direct_arrow(styles: Dict[str, Dict[str, Any]], style: Dict[str, Any]) -> str:
    """Create a unique arrow token that is still accepted by WireViz' parser."""
    # is_arrow() accepts trailing whitespace. This gives every generated direct
    # connection a unique token without extending the core YAML parser.
    token = "--" + (" " * (len(styles) + 1))
    styles[token] = style
    return token


def _resolve_direct_pair(name: str, connectors: Set[str]) -> Tuple[str, str]:
    """Resolve ``A-B`` (or ``A->B``) without breaking connector names containing '-'."""
    if "->" in name:
        left, right = (part.strip() for part in name.split("->", 1))
        if left in connectors and right in connectors:
            return left, right
        raise ValueError(f"Unknown connector in direct connection '{name}'")

    matches: List[Tuple[str, str]] = []
    for left in connectors:
        for right in connectors:
            if left != right and name == f"{left}-{right}":
                matches.append((left, right))

    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ValueError(
            f"Cannot resolve direct connection '{name}'. Use 'Connector1-Connector2' "
            "or 'Connector1 -> Connector2'."
        )
    raise ValueError(
        f"Ambiguous direct connection '{name}'. Use the explicit 'Connector1 -> Connector2' syntax."
    )


def _expand_top_level_direct(
    data: Dict, styles: Dict[str, Dict[str, Any]], connectors: Set[str]
) -> List[list]:
    """Convert compact top-level direct mappings into normal connection sets."""
    direct = data.get("direct")
    if direct is None:
        return []
    if not isinstance(direct, dict):
        raise TypeError("top-level direct must be a mapping, e.g. X1-X2: [BN, BK]")

    result: List[list] = []
    for pair_name, colors in direct.items():
        if not isinstance(pair_name, str):
            raise TypeError("direct connection names must be strings")
        if not isinstance(colors, list) or not colors:
            raise TypeError(f"direct '{pair_name}' must contain a non-empty color list")
        if not all(isinstance(color, str) and color.strip() for color in colors):
            raise TypeError(f"direct '{pair_name}' contains an invalid color code")

        left, right = _resolve_direct_pair(pair_name, connectors)
        pins = list(range(1, len(colors) + 1))
        normalized_colors = []
        for color in colors:
            code = color.strip().upper()
            normalized_colors.append(_COLOR_ALIASES.get(code, code))
        arrows = [
            _new_direct_arrow(styles, {"color": color}) for color in normalized_colors
        ]
        result.append([{left: pins}, arrows, {right: pins}])

    return result


def expand_direct_connections(yaml_data: Dict) -> Dict:
    """Expand cable-less/direct connection syntax for the normal WireViz parser.

    Adjacent connector columns are joined automatically. An explicit ``direct``
    marker between two connector columns may specify ``color`` and ``label``.
    A top-level ``direct`` mapping provides the compact colored 1:1 syntax.
    Existing cable and arrow based connection sets are left unchanged.
    """
    data = deepcopy(yaml_data)
    connectors = set(data.get("connectors", {}).keys())
    separator = data.get("options", {}).get("template_separator", ".")
    styles: Dict[str, Dict[str, Any]] = {}

    # Compact fork-specific syntax, e.g.:
    # direct:
    #   Geraete1-Geraete2: [BN, BK, GR, YE]
    compact_sets = _expand_top_level_direct(data, styles, connectors)

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

    data["connections"] = expanded_sets + compact_sets
    data.pop("direct", None)
    data[_STYLE_KEY] = styles
    return data


def get_direct_connection_styles(yaml_data: Dict) -> Dict[str, Dict[str, Any]]:
    """Return generated-arrow -> rendering-style metadata."""
    return yaml_data.get(_STYLE_KEY, {})
