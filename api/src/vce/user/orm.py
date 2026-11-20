from sqlalchemy import Column, Integer, String, Table

from vce.db import metadata

user = Table(
    "user",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("email", String(256)),
    Column("password", String(256)),
    Column("salt", String(64)),
    Column("github_id", Integer),
    Column("github_name", String(64)),
)
