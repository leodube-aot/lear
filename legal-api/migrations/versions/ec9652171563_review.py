"""review

Revision ID: ec9652171563
Revises: 01b28a2bb730
Create Date: 2024-06-26 16:13:07.413995

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'ec9652171563'
down_revision = '01b28a2bb730'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('filings', sa.Column('resubmission_date', sa.DateTime(timezone=True), nullable=True))

    op.create_table('reviews',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('nr_number', sa.String(length=15), nullable=True),
                    sa.Column('identifier', sa.String(length=50), nullable=True),
                    sa.Column('completing_party', sa.String(length=150), nullable=True),
                    sa.Column('status', sa.Enum('AWAITING_REVIEW', 'CHANGE_REQUESTED', 'RESUBMITTED', 'APPROVED', 'REJECTED', name='review_status'), nullable=False),
                    sa.Column('submission_date', sa.DateTime(timezone=True), nullable=True),
                    sa.Column('creation_date', sa.DateTime(timezone=True), nullable=True),
                    sa.Column('filing_id', sa.Integer(), nullable=False),
                    sa.ForeignKeyConstraint(['filing_id'], ['filings.id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_table('review_results',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('status', sa.Enum('AWAITING_REVIEW', 'CHANGE_REQUESTED', 'RESUBMITTED', 'APPROVED', 'REJECTED', name='review_status'), nullable=False),
                    sa.Column('comments', sa.Text(), nullable=True),
                    sa.Column('reviewer_id', sa.Integer(), nullable=True),
                    sa.Column('creation_date', sa.DateTime(timezone=True), nullable=True),
                    sa.Column('submission_date', sa.DateTime(timezone=True), nullable=True),
                    sa.Column('review_id', sa.Integer(), nullable=False),
                    sa.ForeignKeyConstraint(['review_id'], ['reviews.id'], ),
                    sa.ForeignKeyConstraint(['reviewer_id'], ['users.id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('filings', 'resubmission_date')
    op.drop_table('review_results')
    op.drop_table('reviews')
    op.execute("DROP TYPE review_status;")
    # ### end Alembic commands ###
