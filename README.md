# Filter OSM Data for Coffee Shops

This repository contains scripts for parsing, filtering, and converting OpenStreetMap data.

## Quick Start

You can generate a JSON file of coffee shops listings in Seattle from an OpenStreetMap PBF file using the following commands:

```bash
# See 'Environment' section below for additional help
python3 -m pip install -r requirements.txt
python3 filter_cafes.py washington-latest.osm.pbf seattle-cafes.osm
python3 osm_to_json.py seattle-cafes.osm seattle-cafes.json
```

## Data

The `washington-latest.osm.pbf` file was downloaded from [here](https://download.geofabrik.de/north-america/us/washington.html).

## Environment

This repository comes with a DevContainer setup, so feel free to use that (_e.g._ in VS Code) to set up your environment prior to running the above commands.
