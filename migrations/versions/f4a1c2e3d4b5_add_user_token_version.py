"""add user token_version for JWT session revocation

Revision ID: f4a1c2e3d4b5
Revises: a808d9a62bd7
Create Date: 2026-05-21 14:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f4a1c2e3d4b5"
down_revision: Union[str, Sequence[str], None] = "a808d9a62bd7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "token_version")
