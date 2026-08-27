from src.models import get_connection, run_migrations, DEFAULT_DB_PATH


def main():
    conn = get_connection()
    run_migrations(conn)
    conn.close()
    print(f"Database initialized at {DEFAULT_DB_PATH}")


if __name__ == "__main__":
    main()
