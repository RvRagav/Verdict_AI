"""Services layer.

Services orchestrate pipelines, persist state changes, and emit audit
events. They are the thin layer between FastAPI routes and the lower
pipeline modules. Routes never touch the DB directly — they call services.
"""
