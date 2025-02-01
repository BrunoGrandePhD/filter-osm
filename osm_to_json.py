import json
import sys

import osmium
from jsonschema import validate


class SchemaAnalyzer(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.semicolon_keys = set()
        self.colon_keys = set()

    def analyze_tags(self, tags):
        for tag in tags:
            if ";" in tag.v:
                self.semicolon_keys.add(tag.k)
                if ":" in tag.k:
                    self.semicolon_keys.add(tag.k.split(":")[0])

            if ":" in tag.k:
                base_key = tag.k.split(":")[0]
                self.colon_keys.add(base_key)

    def generate_schema(self):
        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "required": ["nodes"],
            "properties": {
                "nodes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["id", "lat", "lon", "tags"],
                        "properties": {
                            "id": {"type": "integer"},
                            "lat": {"type": "number"},
                            "lon": {"type": "number"},
                            "tags": {"type": "object", "additionalProperties": True},
                        },
                    },
                }
            },
        }
        return schema

    def node(self, n):
        self.analyze_tags(n.tags)


class JsonHandler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.data = {"nodes": []}
        self.semicolon_keys = set()
        self.colon_keys = set()

    def set_schema_info(self, semicolon_keys, colon_keys):
        self.semicolon_keys = set(semicolon_keys)
        self.colon_keys = set(colon_keys)

    def _process_value(self, key, value):
        """Process a single value, handling semicolon-separated lists"""
        if not isinstance(value, str):
            return value

        if key in self.semicolon_keys or (
            (":" in key) and (key.split(":")[0] in self.semicolon_keys)
        ):
            if ";" in value:
                return [v.strip() for v in value.split(";") if v.strip()]
            return [value]
        return value

    def _create_nested_structure(self, key_parts):
        """Create a nested dictionary structure from key parts"""
        result = {}
        current = result

        # Build the nested structure
        for part in key_parts[:-1]:
            current[part] = {}
            current = current[part]

        return result, current

    def _process_tags(self, tags):
        """Process OSM tags into a dictionary"""
        result = {}
        extra_values = {}  # Store colon-separated values here temporarily

        # First pass: handle all keys
        for tag in tags:
            # Process the value first to handle semicolon-separated lists
            processed_value = self._process_value(tag.k, tag.v)

            if ":" not in tag.k:
                # Handle normal keys
                result[tag.k] = processed_value
            else:
                # Handle colon keys (e.g., name:en)
                key_parts = tag.k.split(":")
                base_key = key_parts[0]
                sub_key = key_parts[1]

                # Initialize the extra values dictionary for this base key
                if base_key not in extra_values:
                    extra_values[base_key] = {}

                # Store the processed value in the extra values dictionary
                extra_values[base_key][sub_key] = processed_value

                # If this is the first value for this base key, also store it directly
                if base_key not in result:
                    result[base_key] = processed_value

        # Second pass: merge extra values into result
        for base_key, extra_dict in extra_values.items():
            extra_key = f"{base_key}:extra"
            result[extra_key] = extra_dict

        return result

    def node(self, n):
        node = {
            "id": n.id,
            "lat": n.location.lat,
            "lon": n.location.lon,
            "tags": self._process_tags(n.tags),
        }
        self.data["nodes"].append(node)


def main(input_file, output_file):
    try:
        # First pass: Analyze schema
        schema_analyzer = SchemaAnalyzer()
        schema_analyzer.apply_file(input_file)

        # Generate schema
        schema = schema_analyzer.generate_schema()

        # Write schema to file
        schema_file = output_file.replace(".json", "-schema.json")
        with open(schema_file, "w") as f:
            json.dump(schema, f, indent=2)
        print(f"Generated schema at {schema_file}")

        # Second pass: Convert to JSON
        handler = JsonHandler()
        handler.set_schema_info(
            semicolon_keys=schema_analyzer.semicolon_keys,
            colon_keys=schema_analyzer.colon_keys,
        )
        handler.apply_file(input_file)

        # Validate output data against schema
        validate(instance=handler.data, schema=schema)

        # Write the validated JSON output
        with open(output_file, "w") as f:
            json.dump(handler.data, f, indent=2)
        print(f"Converted {input_file} to {output_file}")
        print("Schema validation successful")

    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python osm_to_json.py <input.osm> <output.json>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]
    main(input_file, output_file)
