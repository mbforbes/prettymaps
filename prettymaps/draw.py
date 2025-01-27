"""
Prettymaps - A minimal Python library to draw pretty maps from OpenStreetMap Data
Copyright (C) 2021 Marcelo Prates

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import code
import copy
import hashlib
import json
import os
import pickle
import re
from collections.abc import Iterable

import osmnx as ox
import pandas as pd
from geopandas import GeoDataFrame
import numpy as np
from numpy.random import choice
from shapely.errors import TopologicalError
from shapely.geometry import box, Polygon, MultiLineString, GeometryCollection
from shapely.affinity import translate, scale, rotate
from descartes import PolygonPatch
from tabulate import tabulate
from rich.console import Console

# from p_tqdm import p_map  # not working
from tqdm import tqdm

from .fetch import get_perimeter, get_layer

C = Console()
LAYER_CACHE_DIR = "cache/layers/"

# Plot a single shape
def plot_shape(shape, ax, vsketch=None, **kwargs):
    """
    Plot shapely object
    """
    if isinstance(shape, Iterable) and type(shape) != MultiLineString:
        for shape_ in shape:
            plot_shape(shape_, ax, vsketch=vsketch, **kwargs)
    else:
        if not shape.is_empty:

            if vsketch is None:
                ax.add_patch(PolygonPatch(shape, **kwargs))
            else:
                if ("draw" not in kwargs) or kwargs["draw"]:

                    if "stroke" in kwargs:
                        vsketch.stroke(kwargs["stroke"])
                    else:
                        vsketch.stroke(1)

                    if "penWidth" in kwargs:
                        vsketch.penWidth(kwargs["penWidth"])
                    else:
                        vsketch.penWidth(0.3)

                    if "fill" in kwargs:
                        vsketch.fill(kwargs["fill"])
                    else:
                        vsketch.noFill()

                    vsketch.geometry(shape)


# Plot a collection of shapes
def plot_shapes(shapes, ax, vsketch=None, palette=None, **kwargs):
    """
    Plot collection of shapely objects (optionally, use a color palette)
    """
    if not isinstance(shapes, Iterable):
        shapes = [shapes]

    for shape in shapes:
        if palette is None:
            plot_shape(shape, ax, vsketch=vsketch, **kwargs)
        else:
            plot_shape(shape, ax, vsketch=vsketch, fc=choice(palette), **kwargs)


# Parse query (by coordinates, OSMId or name)
def parse_query(query):
    if isinstance(query, GeoDataFrame):
        return "polygon"
    elif isinstance(query, tuple):
        return "coordinates"
    elif re.match("""[A-Z][0-9]+""", query):
        return "osmid"
    else:
        return "address"


# Apply transformation (translation & scale) to layers
def transform(layers, x, y, scale_x, scale_y, rotation):
    # Transform layers (translate & scale)
    k, v = zip(*layers.items())
    v = GeometryCollection(v)
    if (x is not None) and (y is not None):
        v = translate(v, *(np.array([x, y]) - np.concatenate(v.centroid.xy)))
    if scale_x is not None:
        v = scale(v, scale_x, 1)
    if scale_y is not None:
        v = scale(v, 1, scale_y)
    if rotation is not None:
        v = rotate(v, rotation)
    layers = dict(zip(k, v))
    return layers


def draw_text(ax, text, x, y, **kwargs):
    if "bbox" in kwargs:
        bbox_kwargs = kwargs.pop("bbox")
        text = ax.text(x, y, text, **kwargs)
        text.set_bbox(**bbox_kwargs)
    else:
        text = ax.text(x, y, text, **kwargs)


def fetch_layer(query, query_mode, radius, layer, kwargs):
    # C.log(f"- want layer '{layer}'")

    # get from cache if can
    os.makedirs(LAYER_CACHE_DIR, exist_ok=True)
    key = {
        "query": query,
        "query_mode": query_mode,
        "radius": radius,
        "layer": layer,
        "kwargs": copy.deepcopy(kwargs),
    }
    key_str = json.dumps(key, sort_keys=True)
    key_hash = hashlib.md5(key_str.encode("utf-8")).hexdigest()
    cache_path = os.path.join(LAYER_CACHE_DIR, key_hash + ".pickle")
    if os.path.isfile(cache_path):
        C.log(f"- Cache found for layer '{layer}'")
        with open(cache_path, "rb") as fr:
            obj = pickle.load(fr)
        if obj["key_str"] == key_str:
            # C.log(f"- returning cache of layer '{layer}'")
            return obj["layer"]

    C.log(f"- Fetching layer '{layer}'")
    # Define base kwargs
    if radius:
        base_kwargs = {
            "point": query if query_mode == "coordinates" else ox.geocode(query),
            "radius": radius,
        }
    else:
        base_kwargs = {
            "perimeter": query
            if query_mode == "polygon"
            else get_perimeter(query, by_osmid=query_mode == "osmid")
        }

    # Fetch layer.
    # We account for certain failures and just continue, but don't write to cache (for
    # now).
    layer_res = get_layer(
        layer, **base_kwargs, **(kwargs if type(kwargs) == dict else {})
    )
    # write to cache
    C.log(f"- writing layer '{layer}' to cache at '{cache_path}'")
    with open(cache_path, "wb") as fw:
        pickle.dump(
            {
                "key_str": key_str,
                "layer": layer_res,
            },
            fw,
        )
    return layer_res


def fetch_parallel(input_layers, output_layers, query, query_mode, radius):
    """Not really working. May need to switch to different multiproc impl."""
    # build inputs to parallel fetch
    # could build this with big comprehension and partials, but whatever
    queries, query_modes, radii, layer_names, all_kwargs = [], [], [], [], []
    for layer, kwargs in tqdm(input_layers.items()):
        if layer in output_layers:
            continue
        queries.append(query)
        query_modes.append(query_mode)
        radii.append(radius)
        layer_names.append(layer)
        all_kwargs.append(kwargs)

    # fetch in parallel
    layer_results = p_map(
        fetch_layer, queries, query_modes, radii, layer_names, all_kwargs
    )
    # save
    new_output_layers = {}
    for i, layer_res in enumerate(layer_results):
        new_output_layers[layer_names[i]] = layer_res

    return new_output_layers


def fetch_sequential(input_layers, output_layers, query, query_mode, radius):
    new_output_layers = {}
    for layer, kwargs in tqdm(input_layers.items()):
        if layer in output_layers:
            continue
        try:
            new_output_layers[layer] = fetch_layer(
                query, query_mode, radius, layer, kwargs
            )
        except TopologicalError:
            C.log(f"Got exception trying to fetch layer '{layer}'")
            C.print_exception()
            C.log("Going to continue without it...")

    return new_output_layers


# Plot
def plot(
    # Address
    query,
    # Whether to use a backup for the layers
    backup=None,
    # Custom postprocessing function on layers
    postprocessing=None,
    # Radius (in case of circular plot)
    radius=None,
    # Which layers to plot
    layers={"perimeter": {}},
    # Drawing params for each layer (matplotlib params such as 'fc', 'ec', 'fill', etc.)
    drawing_kwargs={},
    # OSM Caption parameters
    osm_credit={},
    # Figure parameters
    figsize=(10, 10),
    ax=None,
    title=None,
    # Vsketch parameters
    vsketch=None,
    # Transform (translation & scale) params
    x=None,
    y=None,
    scale_x=None,
    scale_y=None,
    rotation=None,
):
    """

    Draw a map from OpenStreetMap data.

    Parameters
    ----------
    query : string
        The address to geocode and use as the central point around which to get the geometries
    backup : dict
        (Optional) feed the output from a previous 'plot()' run to save time
    postprocessing: function
        (Optional) Apply a postprocessing step to the 'output_layers' dict
    radius
        (Optional) If not None, draw the map centered around the address with this radius (in meters)
    input_layers: dict
        Specify the name of each layer and the OpenStreetMap tags to fetch
    drawing_kwargs: dict
        Drawing params for each layer (matplotlib params such as 'fc', 'ec', 'fill', etc.)
    osm_credit: dict
        OSM Caption parameters
    figsize: Tuple
        (Optional) Width and Height (in inches) for the Matplotlib figure. Defaults to (10, 10)
    ax: axes
        Matplotlib axes
    title: String
        (Optional) Title for the Matplotlib figure
    vsketch: Vsketch
        (Optional) Vsketch object for pen plotting
    x: float
        (Optional) Horizontal displacement
    y: float
        (Optional) Vertical displacement
    scale_x: float
        (Optional) Horizontal scale factor
    scale_y: float
        (Optional) Vertical scale factor
    rotation: float
        (Optional) Rotation in angles (0-360)

    Returns
    -------
    output_layers: dict
        Dictionary of layers (each layer is a Shapely MultiPolygon)

    Notes
    -----

    """
    input_layers = layers  # keeping arg name for compatibility

    # Interpret query
    query_mode = parse_query(query)

    # Save maximum dilation for later use
    dilations = [
        kwargs["dilate"] for kwargs in input_layers.values() if "dilate" in kwargs
    ]
    max_dilation = max(dilations) if len(dilations) > 0 else 0

    ####################
    ### Fetch Layers ###
    ####################

    C.log("Fetching layers")

    # Use backup if provided
    output_layers = {}
    if backup is not None:
        output_layers = backup

    # new_output_layers = fetch_parallel(input_layers, output_layers, query, query_mode, radius)
    new_output_layers = fetch_sequential(
        input_layers, output_layers, query, query_mode, radius
    )

    # We apply transformation and postprocessing to anything new we fetched before
    # merging with what we had before (if anything).

    # Apply transformation to layers (translate & scale)
    if len(new_output_layers) > 0:
        new_output_layers = transform(
            new_output_layers, x, y, scale_x, scale_y, rotation
        )

        # Apply postprocessing step to layers
        if postprocessing is not None:
            new_output_layers = postprocessing(new_output_layers)

    output_layers = {**output_layers, **new_output_layers}

    ############
    ### Plot ###
    ############

    C.log("Plotting")
    # return output_layers  # TODO: remove

    # Matplot-specific stuff (only run if vsketch mode isn't activated)
    if vsketch is None:
        # Ajust axis
        ax.axis("off")
        ax.axis("equal")
        ax.autoscale()

    # Plot background
    if "background" in drawing_kwargs:
        geom = scale(box(*output_layers["perimeter"].bounds), 1.2, 1.2)

        if vsketch is None:
            ax.add_patch(PolygonPatch(geom, **drawing_kwargs["background"]))
        else:
            vsketch.geometry(geom)

    # Adjust bounds
    xmin, ymin, xmax, ymax = output_layers["perimeter"].buffer(max_dilation).bounds
    dx, dy = xmax - xmin, ymax - ymin
    if vsketch is None:
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)

    # Draw layers

    # code.interact(local=dict(globals(), **locals()))

    for layer, shapes in output_layers.items():
        kwargs = drawing_kwargs[layer] if layer in drawing_kwargs else {}
        if "hatch_c" in kwargs:
            # Draw hatched shape
            plot_shapes(
                shapes,
                ax,
                vsketch=vsketch,
                lw=0,
                ec=kwargs["hatch_c"],
                **{k: v for k, v in kwargs.items() if k not in ["lw", "ec", "hatch_c"]},
            )
            # Draw shape contour only
            plot_shapes(
                shapes,
                ax,
                vsketch=vsketch,
                fill=False,
                **{
                    k: v
                    for k, v in kwargs.items()
                    if k not in ["hatch_c", "hatch", "fill"]
                },
            )
        else:
            # Draw shape normally
            plot_shapes(shapes, ax, vsketch=vsketch, **kwargs)

    if ((isinstance(osm_credit, dict)) or (osm_credit is True)) and (vsketch is None):
        x, y = figsize
        d = 0.8 * (x**2 + y**2) ** 0.5
        draw_text(
            ax,
            (
                osm_credit["text"]
                if "text" in osm_credit
                else "data © OpenStreetMap contributors\ngithub.com/marceloprates/prettymaps"
            ),
            x=xmin + (osm_credit["x"] * dx if "x" in osm_credit else 0),
            y=ymax - 4 * d - (osm_credit["y"] * dy if "y" in osm_credit else 0),
            fontfamily=(
                osm_credit["fontfamily"]
                if "fontfamily" in osm_credit
                else "Ubuntu Mono"
            ),
            fontsize=(osm_credit["fontsize"] * d if "fontsize" in osm_credit else d),
            zorder=(
                osm_credit["zorder"]
                if "zorder" in osm_credit
                else len(output_layers) + 1
            ),
            **{
                k: v
                for k, v in osm_credit.items()
                if k not in ["text", "x", "y", "fontfamily", "fontsize", "zorder"]
            },
        )

    # Return perimeter
    return output_layers
