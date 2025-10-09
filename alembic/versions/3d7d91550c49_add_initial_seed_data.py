"""Add initial seed data"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



# revision identifiers, used by Alembic.
revision: str = '3d7d91550c49'
down_revision: Union[str, Sequence[str], None] = '2a8406c792f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
