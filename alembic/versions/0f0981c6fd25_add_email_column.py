"""add email column

Revision ID: 0f0981c6fd25
Revises: 
Create Date: 2026-02-15 02:58:19.961463

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0f0981c6fd25'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column(
        'employee',
        sa.Column('email', sa.String(length=100), nullable=True)
    )



def downgrade():
    op.drop_column('employee', 'email')
