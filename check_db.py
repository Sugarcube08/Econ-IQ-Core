import asyncio

from sqlalchemy import inspect

from core.storage.postgres import engine


async def check_schema():
    async with engine.connect() as conn:
        def inspect_db(sync_conn):
            inspector = inspect(sync_conn)
            tables = inspector.get_table_names()
            print("--- TABLES ---")
            for table in tables:
                print(f"Table: {table}")
                columns = inspector.get_columns(table)
                print("  Columns:")
                for col in columns:
                    print(f"    - {col['name']} ({col['type']})")
                indexes = inspector.get_indexes(table)
                print("  Indexes:")
                for idx in indexes:
                    print(f"    - {idx['name']} (columns: {idx['column_names']})")
        await conn.run_sync(inspect_db)

if __name__ == "__main__":
    asyncio.run(check_schema())
