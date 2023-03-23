import os

from eth_challenge_base.service import create_asgi_application

project_root = os.getcwd()
if os.environ.get("DEBUG_MODE", False) and not os.environ.get("MOVE_MODE", False):
    project_root = os.path.join(project_root, "example")

if os.environ.get("DEBUG_MODE", False) and os.environ.get("MOVE_MODE", False):
    project_root = os.path.join(project_root, "move_contracts", "checkin")

app = create_asgi_application(project_root, os.environ.get("MOVE_MODE", False))
