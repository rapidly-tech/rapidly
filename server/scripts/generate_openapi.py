import json
import sys

from rapidly.app import create_app
from rapidly.openapi import set_openapi_generator

if __name__ == "__main__":
    app = create_app()
    # Clear any cached schema and re-apply the transformer pipeline
    # (MetadataQuery injection, OAuth2 form schemas, etc.) so the
    # generated output matches what the running server exposes.
    app.openapi_schema = None
    set_openapi_generator(app)
    schema = app.openapi()
    json.dump(schema, sys.stdout)
    sys.stdout.flush()
