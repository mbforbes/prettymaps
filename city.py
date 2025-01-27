import shutup

shutup.please()

import argparse
import code
import glob
import os
import pickle
from typing import List, Union, Tuple, Dict, Any, Callable

from imgcat import imgcat
from matplotlib import pyplot as plt
import matplotlib.font_manager as fm
from rich.console import Console
from unidecode import unidecode

from prettymaps import plot

Place = Union[str, Tuple[float, float]]
DrawLayerDict = Dict[str, Dict[str, Any]]
DrawLayerFilter = Callable[[DrawLayerDict], DrawLayerDict]


def no_filter(drawing_kwargs: DrawLayerDict) -> DrawLayerDict:
    return drawing_kwargs


def make_layer_filter(draw_layers: List[str]) -> DrawLayerFilter:
    all_draw_layers = ["perimeter"] + draw_layers

    def layer_filter(
        drawing_kwargs: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        res = {}
        for k, v in drawing_kwargs.items():
            res[k] = (
                v if k in all_draw_layers else {"fill": False, "lw": 0, "zorder": 0}
            )
        return res

    return layer_filter


def get_output_paths(dir: str, slug: str, boundary_type: str) -> Tuple[str, str]:
    """Returns (png path, folder path (for saving layers))"""
    n = 1
    while True:
        if len(glob.glob(os.path.join(dir, f"{slug}-{n}*.png"))) == 0:
            break
        n += 1
    slug_res = f"{slug}-{n}-{boundary_type}"
    return (os.path.join(dir, f"{slug_res}.png"), os.path.join(dir, f"{slug_res}/"))


def parse_place(place: str) -> Place:
    """Returns float tuple if it looks like coords, else just the input."""
    if place[0] == "(" and place[-1] == ")" and len(place.split(",")) == 2:
        return tuple(float(x) for x in place[1:-1].split(","))  # type: ignore
    return place


C = Console()

PALETTES = {
    # portugal: first
    # "portugal": ["#5C6853", "#D13E23"],
    # portugal, map cream red w/ huemint green
    # "portugal": ["#EC6961", "#a3ba95"],
    # portugal: map darker red w/ huemint green.
    # - other huemint greens: #93cb62 #97e277, #96ccad, #6cd58e, #b4d28c
    "portugal": ["#B63841", "#046A38"],  # flag! #046A38
    # USA: flag
    # "usa": ["#B31942", "#0A3161", "#FFFFFF"],
    # USA higher light & saturation
    # "usa": ["#e62d5e", "#195bcc", "#FFFFFF"],
    # USA: going from map cream red, adding huemint blue, off-white
    # "usa": ["#EC6961", "#014d99", "#FAF8F8"],
    # USA: map darker red, huemint blue.
    # - other huemint blues: #38b6d1, #49b09f, #89cdb8, #63cad4, #6fc5ba
    # - other humeint whites: #f0f5cb
    "usa": ["#B63841", "#014d99", "#FAF8F8"],
    # Spain: right from the map
    "spain": ["#B63841", "#F6CA6B"],
    # Greece
    "greece": ["#195bcc", "#FAF8F8"],
    # England
    "england": ["#B63841", "#FAF8F8"],
    "bosnia": ["#195bcc", "#F6CA6B"],
    # "korea": ["#B63841", "#195bcc"],  # just using usa colors for now
}


def do_plot(
    place: Place,
    radius: int | None,
    palette: List[str],
    backup: Any,
    writing_txt,
    writing_x,
    writing_y,
    writing_rot,
    draw_layer_filter: DrawLayerFilter,
    output_path: str,
):
    """Returns layers"""
    # og: 15 x 12, resulting in 1500 x 1200 px
    # v2: 21.12 x 16.90 resulting in 2112 x 1690 px (actually: 1689)
    #     desired bc display width is 704, times pixel scale 3 = 2112
    # v3: 14.08 x 11.27. turns out pixel density on comps/ipads is 2, not 3
    #     (3 on phones, but max width there is like 390 CSSpx = 1170 PHYSpx)
    #     so targeting 704 x 2 = 1408px W
    plt.clf()
    fig, ax = plt.subplots(figsize=(14.08, 11.27), constrained_layout=True)
    fig.patch.set_facecolor("#FCEEE1")

    layers = plot(
        place,
        radius=radius,
        ax=ax,
        backup=backup,
        layers={
            "perimeter": {},
            "streets": {
                "width": {
                    "motorway": 6,
                    "trunk": 5,
                    "primary": 5,
                    "secondary": 4,
                    "tertiary": 3,
                    "residential": 2,
                    "service": 2,
                    "unclassified": 2,
                    "pedestrian": 2,
                    "footway": 2,
                    "path": 2,
                }
            },
            # "lines" are not working anymore and I don't know why.
            "lines": {
                "tags": {
                    "railway": True,
                    "highway": ["tertiary", "living_street"],
                    "aeroway": ["runway", "taxiway"],
                }
            },
            # "railway": {},
            "building": {
                "tags": {
                    "building": True,
                    "leisure": ["track", "pitch"],
                    # "landuse": "retail",  # just draws big blobs over others
                    "landuse": "construction",
                    "shop": "mall",
                },
                "union": False,
            },
            # "water": {"tags": {"natural": ["water", "bay"], "water": True}},
            # "water": {"tags": "water"},
            "water": {
                "tags": {
                    "waterway": True,
                    "water": True,
                    "harbour": True,
                    "marina": True,
                    "bay": True,
                    "river": True,
                    "natural": "water",
                },
                # "union": False,
                # "buffer": 1000,  # meters. affects # retrieved.
                # "perimeter_tolerance": 1000,  # meters. no effect on # retrieved.
                # "dilate": 100,
            },
            "park": {"tags": {"leisure": "park"}},
            "forest": {"tags": {"landuse": ["forest", "orchard"]}},
            "garden": {
                "tags": {
                    "leisure": "garden",
                    "landuse": ["vineyard", "allotments", "farmland"],
                }
            },
            "green": {
                "tags": {
                    "landuse": [
                        "grass",
                        "meadow",
                        "cemetery",
                    ],
                    "natural": ["island", "scrub", "wood"],
                    "leisure": ["park", "golf_course", "nature_reserve"],
                }
            },
            "parking": {
                "tags": {
                    "amenity": ["parking", "school"],
                    "highway": "pedestrian",
                    "man_made": "pier",
                    "landuse": ["military", "landfill", "industrial"],
                    "aeroway": "apron",
                    "surface": "paved",
                }
            },
            "area": {
                "tags": {
                    "landuse": ["residential", "retail"],
                    "amenity": ["social_facility"],
                }
            },
            # "coastline": {
            #     "file_location": "coast/water-polygons-split-4326/water_polygons.shp",
            #     "buffer": 100000,
            #     "circle": True,
            # },
        },
        drawing_kwargs=draw_layer_filter(
            {
                # I think that "fc" = face color (fill)
                #              "ec" = edge color (border)
                # OG colors
                # "perimeter": {"fill": False, "lw": 0, "zorder": 0},
                # "park": {"fc": "#AABD8C", "ec": "#87996b44", "lw": 0.25, "zorder": 1},
                # "forest": {"fc": "#78A58D", "ec": "#658a7644", "lw": 0.25, "zorder": 1},
                # "garden": {"fc": "#a9d1a9", "ec": "#8ab58a44", "lw": 0.25, "zorder": 1},
                # "green": {"fc": "#a9d1a9", "ec": "#8ab58a44", "lw": 0.25, "zorder": 1},
                # "water": {"fc": "#92D5F2", "ec": "#6da8c244", "lw": 0.25, "zorder": 2},
                # "parking": {"fc": "#F1E6D044", "ec": "#2F373744", "lw": 0.25, "zorder": 3},
                # "streets": {"fc": "#F1E6D044", "ec": "#2F373744", "lw": 0.25, "zorder": 4},
                # "building": {"palette": palette, "ec": "#2F373744", "lw": 0.25, "zorder": 5},
                # new colors
                "perimeter": {"fill": False, "lw": 0, "zorder": 0},
                "area": {"fc": "#f9ddc3", "ec": "#f9ddc3", "lw": 0.25, "zorder": 1},
                "park": {"fc": "#a9d1a9", "ec": "#a9d1a9", "lw": 0.25, "zorder": 2},
                "forest": {"fc": "#78A58D", "ec": "#78A58D", "lw": 0.25, "zorder": 2},
                "garden": {"fc": "#a9d1a9", "ec": "#a9d1a9", "lw": 0.25, "zorder": 2},
                "green": {"fc": "#a9d1a9", "ec": "#a9d1a9", "lw": 0.25, "zorder": 2},
                "water": {"fc": "#92D5F2", "ec": "#92D5F2", "lw": 0.25, "zorder": 3},
                "coastline": {
                    "fc": "#92D5F2",
                    "ec": "#92D5F2",
                    "lw": 0.25,
                    "zorder": 3,
                },
                "parking": {"fc": "#B9B2AB", "ec": "#B9B2AB", "lw": 0.25, "zorder": 4},
                "streets": {
                    "fc": "#2F3737BB",
                    "ec": "#2F373788",
                    "lw": 0.25,
                    "zorder": 5,
                },
                # "railway": {"fc": "#2F3737BB", "ec": "#2F373788", "lw": 0.25, "zorder": 5},
                # "railway": {"fc": "#FF00AA", "ec": "#FF00AA", "lw": 1, "zorder": 5},
                "lines": {
                    "fc": "#2F3737BB",
                    "ec": "#2F373788",
                    "lw": 0.25,
                    "zorder": 5,
                },
                # "lines": {"fc": "#FF00AA", "ec": "#FF00AA", "lw": 1, "zorder": 5},
                "building": {"palette": palette, "ec": "#2F3737", "lw": 0, "zorder": 6},
            }
        ),
        # osm_credit={"x": -0.55, "y": -0.25, "color": "#2F3737"} if i == 0 else None,
        # NOTE: Putting OSM and prettymaps credit in image captions/attributions.
        osm_credit=None,
    )

    xmin, ymin, xmax, ymax = layers["perimeter"].bounds
    dx, dy = xmax - xmin, ymax - ymin
    ax.text(
        xmin + writing_x * dx,
        ymin + writing_y * dy,
        # xmax,
        # ymin,
        (place if writing_txt is None else writing_txt),
        color="#2F3737",
        rotation=writing_rot,
        fontproperties=fm.FontProperties(
            # NOTE: update w/ size changes. used 42 for v2 size.
            fname="assets/Permanent_Marker/PermanentMarker-Regular.ttf",
            size=28,
        ),
        ha="right",
        va="baseline",
    )

    ax.autoscale()

    # imgcat(fig)
    C.log(f"Saving image to {output_path}")
    plt.savefig(output_path)

    return layers


def main() -> None:
    # Settings
    # -------
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--place", type=str, required=True, help="Location")
    parser.add_argument(
        "--palette",
        type=str,
        required=True,
        choices=PALETTES.keys(),
        help="Color palette",
    )
    parser.add_argument(
        "--radius",
        type=int,
        help="If specified, radius in meters to bound instead of OSM-defined place perimeter.",
    )
    parser.add_argument(
        "--place-slug",
        type=str,
        help="If provided, use this instead auto-generating file name from place.",
    )
    parser.add_argument(
        "--writing",
        type=str,
        help="If provided, write this instead of the place name on the map.",
    )
    parser.add_argument(
        "--x",
        type=float,
        default=1.0,
        help="Where on x-axis to write place name (right-aligned). 0 left, 1 right.",
    )
    parser.add_argument(
        "--y",
        type=float,
        default=0.0,
        help="Where on y-axis to write place name (baseline-aligned). 0 bottom, 1 top.",
    )
    parser.add_argument(
        "--rotation-deg",
        type=int,
        default=0,
        help="Rotate the place text counterclockwise by this",
    )
    parser.add_argument(
        "--draw-layers",
        action="store_true",
        help="Whether to draw individual layers in a folder.",
    )

    args = parser.parse_args()

    writing_txt = args.writing
    writing_x = args.x
    writing_y = args.y
    writing_rot = args.rotation_deg
    radius = args.radius
    palette = PALETTES[args.palette]
    place = parse_place(args.place)
    draw_layers = args.draw_layers
    # sanity check
    assert (
        isinstance(place, str) or args.place_slug is not None
    ), "Need place slug if coord"
    place_slug = (
        args.place_slug
        if args.place_slug is not None
        else unidecode(
            place.lower()  # type: ignore
            .replace(" ", "-")
            .replace(",", "-")
            .replace(".", "-")
            .replace("--", "-")
            .replace("--", "-")
        )
    )
    boundary_type = f"r{radius}" if radius is not None else "perimeter"
    cache_path = f"cache/{place_slug}-{boundary_type}.pickle"
    output_file_path, output_folder_path = get_output_paths(
        "maps", place_slug, boundary_type
    )

    C.log(f"Settings")
    C.log(f"- place:              {place}")
    C.log(f"- palette:            {palette}")
    C.log(f"- cache_path:         {cache_path}")
    C.log(f"- output_file_path:   {output_file_path}")
    if draw_layers:
        C.log(f"- output_folder_path: {output_folder_path}")

    # Load cached data
    # -------
    backup = None
    if os.path.exists(cache_path):
        C.log(f"Cache found, loading {cache_path}")
        with open(cache_path, "rb") as fr:
            backup = pickle.load(fr)

    # spec layers to re-fetch here
    to_delete: List[str] = [
        # "area",
        # "building",
        # "forest",
        # "garden",
        # "green",
        # "lines",
        # "parking",
        # "water",
        # "coastline"
        # "railway",
        # "streets"
    ]
    if backup is not None:
        for d in to_delete:
            if d in backup:
                del backup[d]

    # Main plotting
    # -------------
    layers = do_plot(
        place,
        radius,
        palette,
        backup,
        writing_txt,
        writing_x,
        writing_y,
        writing_rot,
        no_filter,
        output_file_path,
    )

    # Save cached data
    # ----------------
    C.log(f"Writing cache to {cache_path}")
    with open(cache_path, "wb") as fw:
        pickle.dump(layers, fw)

    # Layer plotting
    # --------------
    if draw_layers:
        C.log(f"Drawing layers to {output_folder_path}")
        os.makedirs(output_folder_path, exist_ok=True)
        active_layers = []
        layer_sets = [
            ["streets", "lines", "area"],
            ["park", "garden", "green", "forest"],
            ["water", "coastline"],
            ["building", "parking"],
        ]
        for idx, layer_names in enumerate(layer_sets):
            active_layers += layer_names
            layer_file_path = os.path.join(output_folder_path, f"{idx}.png")
            C.log(f"Drawing layer {idx} to {layer_file_path}")
            do_plot(
                place,
                radius,
                palette,
                layers,
                writing_txt,
                writing_x,
                writing_y,
                writing_rot,
                make_layer_filter(active_layers),
                layer_file_path,
            )


if __name__ == "__main__":
    main()
