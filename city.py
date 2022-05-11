import shutup

shutup.please()

import argparse
import code
import glob
import os
import pickle

from imgcat import imgcat
from matplotlib import pyplot as plt
import matplotlib.font_manager as fm
from rich.console import Console
from unidecode import unidecode

from prettymaps import plot


def get_output_path(dir: str, slug: str, boundary_type: str) -> str:
    n = 1
    while True:
        g = os.path.join(dir, f"{slug}-{n}*.png")
        gs = len(glob.glob(g))
        print(g, gs)
        if gs == 0:
            break
        n += 1
    return os.path.join(dir, f"{slug}-{n}-{boundary_type}.png")


C = Console()

palettes = {
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
}

parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--place", type=str, required=True, help="Location")
parser.add_argument(
    "--palette", type=str, required=True, choices=palettes.keys(), help="Color palette"
)
parser.add_argument(
    "--radius",
    type=int,
    help="If specified, radius in meters to bound instead of OSM-defined place perimeter.",
)

args = parser.parse_args()

radius = args.radius
palette = palettes[args.palette]
place = args.place
place_slug = unidecode(
    place.lower()
    .replace(" ", "-")
    .replace(",", "-")
    .replace(".", "-")
    .replace("--", "-")
    .replace("--", "-")
)
boundary_type = f"r{radius}" if radius is not None else "perimeter"
cache_path = f"cache/{place_slug}-{boundary_type}.pickle"
output_path = get_output_path("maps", place_slug, boundary_type)

C.log(f"Settings")
C.log(f"- place:       {place}")
C.log(f"- palette:     {palette}")
C.log(f"- cache_path:  {cache_path}")
C.log(f"- output_path: {output_path}")

exit(0)

backup = None
if os.path.exists(cache_path):
    C.log(f"Cache found, loading {cache_path}")
    with open(cache_path, "rb") as f:
        backup = pickle.load(f)

fig, ax = plt.subplots(figsize=(15, 12), constrained_layout=True)
fig.patch.set_facecolor("#FCEEE1")


# spec layers to re-fetch here
to_delete = [
    # "area",
    # "building",
    # "forest",
    # "garden",
    # "green",
    # "lines",
    # "parking",
    # "water",
]
if backup is not None:
    for d in to_delete:
        if d in backup:
            del backup[d]

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
                "unclassified": 1,
                "pedestrian": 1,
                "footway": 1,
                "path": 1,
            }
        },
        "lines": {
            "tags": {
                "railway": True,
                "highway": ["tertiary", "living_street"],
                "aeroway": ["runway", "taxiway"],
            }
        },
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
                "leisure": ["park", "golf_course"],
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
    },
    drawing_kwargs={
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
        # "coastline": {"fc": "#ff0000", "ec": "#ff0000", "lw": 0.25, "zorder": 3},
        "parking": {"fc": "#B9B2AB", "ec": "#B9B2AB", "lw": 0.25, "zorder": 4},
        "streets": {"fc": "#2F3737BB", "ec": "#2F373788", "lw": 0.25, "zorder": 5},
        "lines": {"fc": "#2F3737BB", "ec": "#2F373788", "lw": 0.25, "zorder": 5},
        "building": {"palette": palette, "ec": "#2F3737", "lw": 0, "zorder": 6},
    },
    # osm_credit={"x": -0.55, "y": -0.25, "color": "#2F3737"} if i == 0 else None,
    # NOTE: Putting OSM and prettymaps credit in image captions/attributions.
    osm_credit=None,
)

C.log(f"Writing cache to {cache_path}")
with open(cache_path, "wb") as f:
    backup = pickle.dump(layers, f)


xmin, ymin, xmax, ymax = layers["perimeter"].bounds
dx, dy = xmax - xmin, ymax - ymin
ax.text(
    # xmin + 0.75 * dx,
    # ymin + 0.05 * dy,
    xmax,
    ymin,
    place,
    color="#2F3737",
    # rotation=90,
    fontproperties=fm.FontProperties(
        fname="assets/Permanent_Marker/PermanentMarker-Regular.ttf", size=35
    ),
    ha="right",
    va="baseline",
)

ax.autoscale()

# plt.savefig('../prints/bomfim-farroupilha-cidadebaixa.png')
# plt.savefig('../prints/bomfim-farroupilha-cidadebaixa.svg')

# imgcat(fig)
C.log(f"Saving image to {output_path}")
plt.savefig(output_path)
