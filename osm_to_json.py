import json
import sys
from collections import defaultdict

import osmium
from jsonschema import Draft7Validator, validate


class SchemaAnalyzer(osmium.SimpleHandler):
    """First pass handler to analyze the schema of OSM tags"""

    def __init__(self):
        super().__init__()
        self.semicolon_keys = set()  # Keys that have semicolon values
        self.colon_keys = set()  # Base keys that have colon-separated variants
        self.key_variants = defaultdict(set)  # Track all variants of each base key
        self.value_types = defaultdict(set)  # Track types for each key
        self.nested_structures = defaultdict(
            lambda: defaultdict(set)
        )  # Track nested structures
        self.known_patterns = {
            "phone": r"^\+\d[\d\s-]+$",
            "website": r"^https?://\S+$",
            "wikidata": r"^Q\d+$",
            "ref": r"^\d+$",
            "postcode": r"^\d{5}(-\d{4})?$",
        }

    def analyze_value(self, key, value):
        """Analyze the type and structure of a value"""
        # Track the Python type
        self.value_types[key].add(type(value).__name__)

        # Track if it's a list (from semicolon split)
        if isinstance(value, str) and ";" in value:
            self.semicolon_keys.add(key)
            self.value_types[key].add("array")

    def analyze_tags(self, tags):
        """Analyze tags for schema information"""
        for tag in tags:
            # Basic value analysis
            self.analyze_value(tag.k, tag.v)

            # Handle colon-separated keys
            if ":" in tag.k:
                parts = tag.k.split(":")
                base_key = parts[0]
                self.colon_keys.add(base_key)
                self.key_variants[base_key].add(tag.k)

                # Track nested structure
                current = self.nested_structures[base_key]
                for i, part in enumerate(parts[1:], 1):
                    current = current[part]

            # Check for semicolons in values
            if ";" in tag.v:
                self.semicolon_keys.add(tag.k)
                # If this is a colon-separated key, also mark its base key
                if ":" in tag.k:
                    self.semicolon_keys.add(tag.k.split(":")[0])

    def _generate_tag_properties(self):
        """Generate schema properties for tags"""
        properties = {}

        for key in self.value_types:
            if key in self.colon_keys:
                # This is a base key with nested structure
                properties[key] = self._generate_nested_schema(key)
            else:
                # This is a regular key
                prop = {}
                if key in self.semicolon_keys:
                    prop = {
                        "oneOf": [
                            {"type": "array", "items": {"type": "string"}},
                            {"type": "string"},
                        ]
                    }
                else:
                    prop = {"type": "string"}

                # Add pattern if this is a known format
                base_key = key.split(":")[-1]  # Get the last part of the key
                if base_key in self.known_patterns:
                    if "oneOf" in prop:
                        prop["oneOf"][1]["pattern"] = self.known_patterns[base_key]
                    else:
                        prop["pattern"] = self.known_patterns[base_key]

                properties[key] = prop

        return properties

    def _generate_nested_schema(self, base_key):
        """Generate schema for nested structures"""
        return {
            "type": "object",
            "properties": {
                "_value": {
                    "oneOf": [
                        {"type": "string"},
                        {"type": "array", "items": {"type": "string"}},
                    ]
                }
            },
            "additionalProperties": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "array", "items": {"type": "string"}},
                    {"type": "object", "additionalProperties": True},
                ]
            },
        }

    def generate_schema(self):
        """Generate JSON Schema based on analyzed data"""
        # Generate tag properties once to reuse
        tag_properties = self._generate_tag_properties()

        # Define the tags schema once
        tags_schema = {
            "type": "object",
            "properties": tag_properties,
            "additionalProperties": True,  # Allow unknown tags
        }

        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "required": ["nodes"],
            "definitions": {"tags": tags_schema},
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
                            "tags": {"$ref": "#/definitions/tags"},
                        },
                    },
                }
            },
        }

        # Validate the schema itself
        Draft7Validator.check_schema(schema)
        return schema

    def node(self, n):
        self.analyze_tags(n.tags)


class JsonHandler(osmium.SimpleHandler):
    """Second pass handler to convert OSM data to JSON using schema information"""

    def __init__(self, schema_info):
        super().__init__()
        self.data = {"nodes": []}
        self.semicolon_keys = schema_info.semicolon_keys
        self.colon_keys = schema_info.colon_keys
        self.key_variants = schema_info.key_variants

    def _process_value(self, key, value):
        """Process value according to schema analysis"""
        base_key = key.split(":")[0] if ":" in key else key

        # If this key or its base key should be a list
        if key in self.semicolon_keys or base_key in self.semicolon_keys:
            # Always split on semicolon and return as list
            values = [v.strip() for v in value.split(";") if v.strip()]
            return (
                values if values else [value]
            )  # Return single value as list if no semicolons
        return value

    def _create_nested_dict(self, tags):
        """Create a nested dictionary structure for colon-separated keys"""
        result = {}

        # Process regular keys first
        for tag in tags:
            if ":" not in tag.k:
                value = self._process_value(tag.k, tag.v)
                if tag.k in self.colon_keys:
                    # This is a base key that has nested variants
                    result[tag.k] = {"_value": value}
                else:
                    result[tag.k] = value

        # Process colon-separated keys
        for tag in tags:
            if ":" in tag.k:
                parts = tag.k.split(":")
                value = self._process_value(tag.k, tag.v)

                current = result
                # Create nested structure
                for i, part in enumerate(parts[:-1]):
                    if part not in current:
                        current[part] = {}
                    current = current[part]

                # Set the final value
                current[parts[-1]] = value

        return result

    def node(self, n):
        node = {
            "id": n.id,
            "lat": n.location.lat,
            "lon": n.location.lon,
            "tags": self._create_nested_dict(n.tags),
        }
        self.data["nodes"].append(node)


def main(input_file, output_file):
    try:
        # First pass: Analyze schema
        schema_analyzer = SchemaAnalyzer()
        schema_analyzer.apply_file(input_file)

        # Generate and validate schema
        schema = schema_analyzer.generate_schema()

        # Write schema to file
        schema_file = output_file.replace(".json", "-schema.json")
        with open(schema_file, "w") as f:
            json.dump(schema, f, indent=2)
        print(f"Generated schema at {schema_file}")

        # Second pass: Convert to JSON using schema information
        handler = JsonHandler(schema_analyzer)
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
