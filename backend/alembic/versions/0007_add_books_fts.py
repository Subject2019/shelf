"""书籍全文检索表（FTS5 + trigram 分词）

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-25
"""

from __future__ import annotations

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

COLUMNS = ("title", "subtitle", "author", "narrator", "series_name", "description")


def upgrade() -> None:
    # external content：正文仍存在 books，FTS 只保留索引；
    # trigram 让中文可以子串匹配（「东林皆」能搜到「东林皆石」）。
    op.execute(
        """
        CREATE VIRTUAL TABLE books_fts USING fts5(
            title, subtitle, author, narrator, series_name, description,
            content='books',
            content_rowid='id',
            tokenize='trigram'
        )
        """
    )
    # 回填存量数据
    op.execute("INSERT INTO books_fts(books_fts) VALUES('rebuild')")

    op.execute(
        """
        CREATE TRIGGER books_fts_ai AFTER INSERT ON books BEGIN
            INSERT INTO books_fts(rowid, title, subtitle, author, narrator, series_name, description)
            VALUES (new.id, new.title, new.subtitle, new.author, new.narrator,
                    new.series_name, new.description);
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER books_fts_ad AFTER DELETE ON books BEGIN
            INSERT INTO books_fts(books_fts, rowid, title, subtitle, author, narrator, series_name, description)
            VALUES ('delete', old.id, old.title, old.subtitle, old.author, old.narrator,
                    old.series_name, old.description);
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER books_fts_au AFTER UPDATE ON books BEGIN
            INSERT INTO books_fts(books_fts, rowid, title, subtitle, author, narrator, series_name, description)
            VALUES ('delete', old.id, old.title, old.subtitle, old.author, old.narrator,
                    old.series_name, old.description);
            INSERT INTO books_fts(rowid, title, subtitle, author, narrator, series_name, description)
            VALUES (new.id, new.title, new.subtitle, new.author, new.narrator,
                    new.series_name, new.description);
        END
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS books_fts_au")
    op.execute("DROP TRIGGER IF EXISTS books_fts_ad")
    op.execute("DROP TRIGGER IF EXISTS books_fts_ai")
    op.execute("DROP TABLE IF EXISTS books_fts")
