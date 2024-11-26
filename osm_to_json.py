import json
import sys
from collections import defaultdict

import osmium
from jsonschema import Draft7Validator, validate


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

        # First pass: handle non-colon keys
        for tag in tags:
            if ":" not in tag.k:
                result[tag.k] = self._process_value(tag.k, tag.v)

        # Second pass: handle colon keys
        for tag in tags:
            if ":" in tag.k:
                key_parts = tag.k.split(":")
                value = self._process_value(tag.k, tag.v)

                # Get or create the parent structure
                current = result
                for part in key_parts[:-1]:
                    if part not in current:
                        current[part] = {}
                    elif not isinstance(current[part], dict):
                        # If we encounter a non-dict, convert it to a dict with _value
                        current[part] = {"_value": current[part]}
                    current = current[part]

                # Set the final value
                current[key_parts[-1]] = value

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
