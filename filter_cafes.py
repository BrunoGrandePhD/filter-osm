import sys

import osmium


class CafeFilter:
    # Seattle bounding box coordinates
    SEATTLE_NORTH = 47.7772
    SEATTLE_SOUTH = 47.4299
    SEATTLE_EAST = -121.9180
    SEATTLE_WEST = -122.4330

    def node(self, n):
        # Check if node is outside Seattle's bounding box
        if (
            n.location.lat < self.SEATTLE_SOUTH
            or n.location.lat > self.SEATTLE_NORTH
            or n.location.lon < self.SEATTLE_WEST
            or n.location.lon > self.SEATTLE_EAST
        ):
            return True

        # Check if it's not a cafe
        return not (
            ("cafe" in n.tags.get("amenity", ""))
            or ("coffee_shop" in n.tags.get("cuisine", ""))
        )


def main(input_file, output_file):
    fp = osmium.FileProcessor(input_file, osmium.osm.NODE).with_filter(CafeFilter())

    with osmium.SimpleWriter(output_file) as writer:
        for obj in fp:
            writer.add(obj)


if __name__ == "__main__":
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    main(input_file, output_file)
