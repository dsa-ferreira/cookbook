"""seed units

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-31 17:30:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copy of the vocabulary at this revision. Adding a unit means a new
# migration, not an edit here.
UNITS = [
    ("g", "mass", 1),
    ("kg", "mass", 1000),
    ("ml", "volume", 1),
    ("l", "volume", 1000),
    ("tsp", "volume", 5),
    ("tbsp", "volume", 15),
    ("cup", "volume", 240),
    ("piece", "count", 1),
    ("clove", "count", 1),
    ("can", "count", 1),
    ("pinch", "count", 1),
]

units = sa.table(
    "units",
    sa.column("code", sa.Text),
    sa.column("dimension", sa.Text),
    sa.column("to_base", sa.Numeric),
)


def upgrade() -> None:
    op.bulk_insert(units, [{"code": c, "dimension": d, "to_base": f} for c, d, f in UNITS])


def downgrade() -> None:
    op.execute(units.delete().where(units.c.code.in_([c for c, _, _ in UNITS])))
