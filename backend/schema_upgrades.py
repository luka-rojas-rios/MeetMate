from sqlalchemy import inspect, text

from backend.database import engine


def table_exists(connection, table_name):
    inspector = inspect(connection)
    return table_name in inspector.get_table_names()


def column_exists(connection, table_name, column_name):
    inspector = inspect(connection)
    columns = inspector.get_columns(table_name)
    return column_name in [column["name"] for column in columns]


def add_column_if_missing(connection, table_name, column_name, column_definition):
    if table_exists(connection, table_name) and not column_exists(connection, table_name, column_name):
        connection.execute(
            text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")
        )


def run_schema_upgrades():
    with engine.begin() as connection:
        if table_exists(connection, "users"):
            add_column_if_missing(connection, "users", "first_name", "VARCHAR")
            add_column_if_missing(connection, "users", "last_name", "VARCHAR")
            add_column_if_missing(connection, "users", "birth_date", "VARCHAR")
            add_column_if_missing(connection, "users", "sex", "VARCHAR")
            add_column_if_missing(connection, "users", "nationality", "VARCHAR")
            add_column_if_missing(connection, "users", "phone", "VARCHAR")
            add_column_if_missing(connection, "users", "profile_photo", "VARCHAR")
            add_column_if_missing(connection, "users", "biography", "TEXT")

            add_column_if_missing(connection, "users", "user_type", "VARCHAR")
            add_column_if_missing(connection, "users", "language", "VARCHAR")
            add_column_if_missing(connection, "users", "language_2", "VARCHAR")
            add_column_if_missing(connection, "users", "home_university", "VARCHAR")
            add_column_if_missing(connection, "users", "exchange_university", "VARCHAR")
            add_column_if_missing(connection, "users", "favorite_sport_1", "VARCHAR")
            add_column_if_missing(connection, "users", "favorite_sport_2", "VARCHAR")
            add_column_if_missing(connection, "users", "hobby_1", "VARCHAR")
            add_column_if_missing(connection, "users", "hobby_2", "VARCHAR")

        if table_exists(connection, "events"):
            add_column_if_missing(connection, "events", "category", "VARCHAR DEFAULT 'General'")
            add_column_if_missing(connection, "events", "max_participants", "INTEGER")

        if table_exists(connection, "feedback"):
            add_column_if_missing(connection, "feedback", "overall_rating", "INTEGER DEFAULT 0")
            add_column_if_missing(connection, "feedback", "created_at", "VARCHAR")

        if table_exists(connection, "matches"):
            add_column_if_missing(connection, "matches", "student_id", "INTEGER")
            add_column_if_missing(connection, "matches", "buddy_id", "INTEGER")
            add_column_if_missing(connection, "matches", "requested_by", "INTEGER")
            add_column_if_missing(connection, "matches", "status", "VARCHAR DEFAULT 'pending'")
            add_column_if_missing(connection, "matches", "compatibility_score", "INTEGER DEFAULT 0")
            add_column_if_missing(connection, "matches", "match_reason", "TEXT")
            add_column_if_missing(connection, "matches", "created_at", "VARCHAR")
            add_column_if_missing(connection, "matches", "responded_at", "VARCHAR")

        if table_exists(connection, "event_reviews"):
            add_column_if_missing(connection, "event_reviews", "creator_rating", "INTEGER")
            add_column_if_missing(connection, "event_reviews", "creator_comment", "TEXT")