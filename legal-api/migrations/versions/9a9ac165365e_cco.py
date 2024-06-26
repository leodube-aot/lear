"""cco

Revision ID: 9a9ac165365e
Revises: ae43b5cc0d2d
Create Date: 2023-05-29 13:07:41.668681

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '9a9ac165365e'
down_revision = 'ae43b5cc0d2d'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('consent_continuation_outs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('foreign_jurisdiction', sa.String(length=10), nullable=True),
        sa.Column('foreign_jurisdiction_region', sa.String(length=10), nullable=True),
        sa.Column('expiry_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('filing_id', sa.Integer(), nullable=True),
        sa.Column('business_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ),
        sa.ForeignKeyConstraint(['filing_id'], ['filings.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id')
    )
    op.drop_column('businesses', 'cco_expiry_date')
    op.drop_column('businesses_version', 'cco_expiry_date')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('businesses_version', sa.Column('cco_expiry_date', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True))
    op.add_column('businesses', sa.Column('cco_expiry_date', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True))
    op.drop_table('consent_continuation_outs')
    # ### end Alembic commands ###
