"""`vce-migrate`: bring the database schema up to date. Safe to run on every container start."""

import logging

from alembic import command
from alembic.config import Config


def alembic_config() -> Config:
    """Config without alembic.ini, so it also works from the installed package in the prod image."""
    config = Config()
    config.set_main_option("script_location", "vce:migrations")
    return config


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")
    command.upgrade(alembic_config(), "head")
