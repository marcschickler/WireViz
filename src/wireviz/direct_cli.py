# -*- coding: utf-8 -*-
"""WireViz CLI with support for direct connector-to-connector connections."""

from pathlib import Path
from typing import Dict

import wireviz.wireviz as _core
from wireviz.direct_connections import expand_direct_connections

_original_parse = _core.parse


def _parse_with_direct_connections(
    inp,
    return_types=None,
    output_formats=None,
    output_dir=None,
    output_name=None,
    image_paths=[],
):
    """Preprocess cable-less connections and delegate to the normal parser."""
    yaml_data, yaml_file = _core._get_yaml_data_and_path(inp)
    if not isinstance(yaml_data, Dict):
        return _original_parse(
            inp,
            return_types=return_types,
            output_formats=output_formats,
            output_dir=output_dir,
            output_name=output_name,
            image_paths=image_paths,
        )

    yaml_data = expand_direct_connections(yaml_data)

    # Preserve the original path-dependent defaults after converting the input
    # to a dict for the regular parser.
    paths = list(image_paths)
    if yaml_file:
        if output_dir is None:
            output_dir = yaml_file.parent
        if output_name is None:
            output_name = yaml_file.stem
        if yaml_file.parent not in [Path(p) for p in paths]:
            paths.append(yaml_file.parent)

    return _original_parse(
        yaml_data,
        return_types=return_types,
        output_formats=output_formats,
        output_dir=output_dir,
        output_name=output_name,
        image_paths=paths,
    )


# wv_cli imports wireviz.wireviz as a module and calls wv.parse at execution
# time. Replacing the function before importing the Click command keeps all
# existing command-line options and behaviour intact.
_core.parse = _parse_with_direct_connections

from wireviz.wv_cli import wireviz  # noqa: E402,F401
