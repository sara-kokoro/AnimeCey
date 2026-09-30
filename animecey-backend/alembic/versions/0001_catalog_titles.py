"""create catalog_titles (index léger Neon)

Revision ID: 0001_catalog_titles
Revises:
Create Date: 2026-09-19

Idempotente : au démarrage, ``init_db()`` (create_all) peut déjà avoir créé la table
(sans les index trigram). La table n'est donc créée que si elle est absente ; les
index trigram utilisent ``IF NOT EXISTS``.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001_catalog_titles"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    if not sa.inspect(bind).has_table("catalog_titles"):
        op.create_table(
            "catalog_titles",
            sa.Column(
                "id",
                sa.Uuid(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("title", sa.String(500), nullable=False),
            sa.Column("title_jp", sa.String(500), nullable=True),
            sa.Column("type", sa.String(16), nullable=False),
            sa.Column("year", sa.Integer(), nullable=True),
            sa.Column("source", sa.String(16), nullable=False),
            sa.Column("external_id", sa.String(255), nullable=False),
            sa.Column("poster_url", sa.String(1000), nullable=True),
            sa.Column("tmdb_id", sa.Integer(), nullable=True),
            sa.Column("anilist_id", sa.Integer(), nullable=True),
            sa.Column("is_ongoing", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.UniqueConstraint(
                "source", "external_id", name="uq_catalog_titles_source_external_id"
            ),
            sa.CheckConstraint(
                "type IN ('anime', 'serie', 'film')", name="ck_catalog_titles_type"
            ),
            sa.CheckConstraint(
                "source IN ('tmcooper', 'streamsdl')", name="ck_catalog_titles_source"
            ),
        )
        op.create_index("ix_catalog_titles_tmdb_id", "catalog_titles", ["tmdb_id"])
        op.create_index("ix_catalog_titles_anilist_id", "catalog_titles", ["anilist_id"])
        op.create_index(
            "ix_catalog_titles_ongoing_sync",
            "catalog_titles",
            ["last_synced_at"],
            postgresql_where=sa.text("is_ongoing"),
        )

    # Recherche ILIKE '%q%' rapide (pg_trgm est disponible sur Neon).
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_catalog_titles_title_trgm "
        "ON catalog_titles USING gin (title gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_catalog_titles_title_jp_trgm "
        "ON catalog_titles USING gin (title_jp gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_catalog_titles_title_jp_trgm")
    op.execute("DROP INDEX IF EXISTS ix_catalog_titles_title_trgm")
    op.execute("DROP TABLE IF EXISTS catalog_titles")
    # L'extension pg_trgm est volontairement conservée.
