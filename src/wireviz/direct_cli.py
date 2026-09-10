# -*- coding: utf-8 -*-
"""WireViz CLI with support for styled direct connector connections."""

from pathlib import Path

import wireviz.wireviz as _core
from wireviz import wv_colors
from wireviz.DataClasses import MatePin
from wireviz.Harness import Harness
from wireviz.direct_connections import (
    expand_direct_connections,
    get_direct_connection_styles,
)

_original_parse = _core.parse
_original_create_graph = Harness.create_graph


def _direct_edge_codes(harness, mate):
    """Build the same GraphViz endpoint strings used by Harness.create_graph."""
    from_connector = harness.connectors[mate.from_name]
    to_connector = harness.connectors[mate.to_name]

    if from_connector.style != "simple":
        from_pin_index = from_connector.pins.index(mate.from_pin)
        from_port_str = ":p{}r".format(from_pin_index + 1)
    else:
        from_port_str = ""

    if to_connector.style != "simple":
        to_pin_index = to_connector.pins.index(mate.to_pin)
        to_port_str = ":p{}l".format(to_pin_index + 1)
    else:
        to_port_str = ""

    return (
        "{}{}:e".format(mate.from_name, from_port_str),
        "{}{}:w".format(mate.to_name, to_port_str),
    )


def _create_graph_with_direct_styles(self):
    """Render generated direct mates as solid, optionally colored/labeled edges."""
    direct_edges = {}
    for mate in self.mates:
        style = getattr(mate, "_direct_style", None)
        if style is None or not isinstance(mate, MatePin):
            continue
        direct_edges[_direct_edge_codes(self, mate)] = style

    if not direct_edges:
        return _original_create_graph(self)

    # Harness.create_graph creates a graphviz.Graph internally. Intercept only
    # Graph.edge while it runs, so normal WireViz graph generation stays intact.
    from graphviz import Graph

    original_edge = Graph.edge

    def styled_edge(graph, tail_name, head_name, label=None, _attributes=None, **attrs):
        style = direct_edges.get((tail_name, head_name))
        if style is not None:
            attrs["style"] = "solid"
            attrs["color"] = (
                wv_colors.translate_color(style["color"], "HEX")
                if style.get("color")
                else "#000000"
            )
            attrs["dir"] = "none"
            if style.get("label") is not None:
                label = str(style["label"])
        return original_edge(
            graph,
            tail_name,
            head_name,
            label=label,
            _attributes=_attributes,
            **attrs
        )

    Graph.edge = styled_edge
    try:
        return _original_create_graph(self)
    finally:
        Graph.edge = original_edge


Harness.create_graph = _create_graph_with_direct_styles


def _parse_with_direct_connections(
    inp,
    return_types=None,
    output_formats=None,
    output_dir=None,
    output_name=None,
    image_paths=[],
):
    """Preprocess cable-less connections, apply styles, then render normally."""
    if not output_formats and not return_types:
        raise Exception("No output formats or return types specified")

    yaml_data, yaml_file = _core._get_yaml_data_and_path(inp)
    if not isinstance(yaml_data, dict):
        return _original_parse(
            inp,
            return_types=return_types,
            output_formats=output_formats,
            output_dir=output_dir,
            output_name=output_name,
            image_paths=image_paths,
        )

    yaml_data = expand_direct_connections(yaml_data)
    direct_styles = get_direct_connection_styles(yaml_data)

    # Preserve file based defaults after converting the input to a dict.
    paths = list(image_paths)
    if yaml_file:
        resolved_parent = yaml_file.parent.resolve()
        if resolved_parent not in [Path(p).resolve() for p in paths]:
            paths.append(resolved_parent)
        if output_name is None:
            output_name = yaml_file.stem

    # Parse first without rendering. This lets us attach style information to
    # the generated MatePin objects before GraphViz output is created.
    harness = _original_parse(
        yaml_data,
        return_types="harness",
        output_formats=None,
        output_name=output_name,
        image_paths=paths,
    )

    for mate in harness.mates:
        if isinstance(mate, MatePin) and mate.shape in direct_styles:
            mate._direct_style = direct_styles[mate.shape]

    if output_formats:
        if yaml_file:
            final_output_dir = _core._get_output_dir(yaml_file, output_dir)
            final_output_name = _core._get_output_name(yaml_file, output_name)
        else:
            final_output_dir = _core._get_output_dir(None, output_dir)
            final_output_name = _core._get_output_name(None, output_name)
        harness.output(
            filename=final_output_dir / final_output_name,
            fmt=output_formats,
            view=False,
        )

    if not return_types:
        return None

    requested = [return_types] if isinstance(return_types, str) else list(return_types)
    returns = []
    for return_type in [item.lower() for item in requested]:
        if return_type == "png":
            returns.append(harness.png)
        elif return_type == "svg":
            returns.append(harness.svg)
        elif return_type == "harness":
            returns.append(harness)

    return tuple(returns) if len(returns) != 1 else returns[0]


# wv_cli imports wireviz.wireviz as a module and calls wv.parse at execution
# time. Replacing the function before importing the Click command keeps all
# existing command-line options and behaviour intact.
_core.parse = _parse_with_direct_connections

from wireviz.wv_cli import wireviz  # noqa: E402,F401
