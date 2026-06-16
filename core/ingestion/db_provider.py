from datetime import UTC, datetime
from typing import Any

import polars as pl
from loguru import logger
from core.observability.failure_registry import FailureRegistry
from sqlalchemy import Table, select, update
from sqlalchemy.ext.asyncio import AsyncSession


class DBIngestionProvider:
    def __init__(self, session: AsyncSession, fetch_limit: int = 10000):
        self.session = session
        self.fetch_limit = fetch_limit

    async def _get_table(self, table_name: str) -> Table | None:
        """Reflects an external table only if it exists, using a global cache."""
        from core.storage.postgres import _missing_tables, get_reflected_table

        is_already_missing = table_name in _missing_tables
        table = await get_reflected_table(table_name, self.session)
        if table is None and not is_already_missing:
            FailureRegistry.record(
                "RAW_TABLE_NOT_FOUND",
                f"External raw table {table_name} does not exist",
                "WARNING",
                extra={"table_name": table_name},
            )
        elif table is not None:
            FailureRegistry.recover(
                "RAW_TABLE_NOT_FOUND", f"External raw table {table_name} found", extra={"table_name": table_name}
            )
        return table

    async def ingest_async(self) -> tuple[pl.DataFrame, dict[str, list[Any]], list[str]]:
        """
        Custom ingestion method for DB provider that handles async extraction.
        Reads unprocessed records (is_processed=False) from external raw tables.
        Returns (DataFrame, processed_ids_map, metadata_customer_ids)
        """

        source_configs = [
            ("raw_sales", self._normalize_sales),
            ("raw_payments", self._normalize_payments),
            ("raw_returns", self._normalize_rg),
            ("customers", self._normalize_customers),
        ]

        all_normalized = []
        processed_ids = {}
        metadata_customer_ids = []
        remaining_limit = self.fetch_limit

        for table_name, normalizer in source_configs:
            if remaining_limit <= 0:
                break

            table = await self._get_table(table_name)
            if table is not None:
                # Focus ONLY on unprocessed records
                stmt = select(table).where(table.c.is_processed.is_(False)).limit(remaining_limit)

                result = await self.session.execute(stmt)
                rows = result.fetchall()

                if not rows:
                    continue

                dicts = [dict(row._mapping) for row in rows]
                raw_df = pl.DataFrame(dicts, infer_schema_length=None)

                processed_ids[table_name] = raw_df["id"].to_list()

                # MANDATORY: Convert Object-type columns (UUIDs, Decimals from SQLAlchemy) to String.
                # Polars cannot strictly cast 'Object' to 'String' using .cast(), so we use map_elements.
                object_cols = [c for c in raw_df.columns if raw_df[c].dtype == pl.Object]
                if object_cols:
                    raw_df = raw_df.with_columns(
                        [
                            pl.col(c).map_elements(lambda x: str(x) if x is not None else None, return_dtype=pl.Utf8)
                            for c in object_cols
                        ]
                    )

                norm_df = normalizer(raw_df)
                if not norm_df.is_empty():
                    all_normalized.append(norm_df)
                    remaining_limit -= raw_df.height

            # No cities side-effect processing needed

        if not all_normalized:
            return pl.DataFrame(), processed_ids, metadata_customer_ids

        return pl.concat(all_normalized, how="diagonal_relaxed"), processed_ids, metadata_customer_ids

    def _parse_date_column(self, df: pl.DataFrame, col_name: str) -> pl.Expr:
        if col_name not in df.columns:
            return pl.lit(None).cast(pl.Date)

        dtype = df[col_name].dtype
        if dtype in [pl.String, pl.Utf8]:
            # User mentioned format: "08/05/22 00:00:00" (DD/MM/YY or MM/DD/YY)
            # We try to parse with common formats first to be robust
            expr = (
                pl.col(col_name)
                .str.to_datetime("%d/%m/%y %H:%M:%S", strict=False)
                .fill_null(pl.col(col_name).str.to_datetime("%m/%d/%y %H:%M:%S", strict=False))
                .fill_null(pl.col(col_name).str.to_datetime(strict=False))  # Fallback to default
            )
        else:
            expr = pl.col(col_name).cast(pl.Datetime)

        # Truncate to date to ensure consistency across the system
        return expr.dt.date()

    def _normalize_sales(self, df: pl.DataFrame) -> pl.DataFrame:
        is_ok_expr = (
            pl.col("is_ok").fill_null(0).cast(pl.Int32)
            if "is_ok" in df.columns
            else pl.lit(0).cast(pl.Int32).alias("is_ok")
        )

        # Pull extra signals if they exist
        extra_cols = ["product_category", "product_name", "quantity", "unit_price", "tax_amount"]
        select_list = [
            pl.col("customer_id").cast(pl.Utf8),
            pl.lit("SALE").alias("event_type"),
            pl.coalesce(
                [
                    self._parse_date_column(df, "invoice_date"),
                    self._parse_date_column(df, "created_at"),
                ]
            ).alias("event_date"),
            pl.col("invoice_amount").alias("amount").fill_null(0.0).cast(pl.Float64),
            pl.col("discount_amount").alias("discount_amount").fill_null(0.0).cast(pl.Float64),
            is_ok_expr,
            pl.lit(None).alias("rg_responsibility").cast(pl.Utf8),
            pl.lit(None).alias("payment_mode").cast(pl.Utf8),
            pl.lit(None).alias("bank_name").cast(pl.Utf8),
            pl.lit("raw_sales").alias("source_table"),
            pl.col("id").cast(pl.Utf8).alias("source_raw_id"),
        ]

        for col in extra_cols:
            if col in df.columns:
                select_list.append(pl.col(col))

        return df.select(select_list).pipe(self._add_event_uid)

    def _normalize_payments(self, df: pl.DataFrame) -> pl.DataFrame:
        # 1. Base payment events
        payments = df.select(
            [
                pl.col("customer_id").cast(pl.Utf8),
                pl.lit("PAYMENT").alias("event_type"),
                pl.coalesce(
                    [
                        self._parse_date_column(df, "payment_date"),
                        self._parse_date_column(df, "created_at"),
                    ]
                ).alias("event_date"),
                pl.col("payment_amount").alias("amount").fill_null(0.0).cast(pl.Float64),
                pl.lit(0.0).alias("discount_amount").cast(pl.Float64),
                pl.lit(0).alias("is_ok").cast(pl.Int32),
                pl.lit(None).alias("rg_responsibility").cast(pl.Utf8),
                pl.col("payment_mode").cast(pl.Utf8)
                if "payment_mode" in df.columns
                else pl.lit(None).alias("payment_mode").cast(pl.Utf8),
                pl.col("bank_name").cast(pl.Utf8)
                if "bank_name" in df.columns
                else pl.lit(None).alias("bank_name").cast(pl.Utf8),
                pl.lit("raw_payments").alias("source_table"),
                pl.col("id").cast(pl.Utf8).alias("source_raw_id"),
            ]
        )
        return payments.pipe(self._add_event_uid)

    def _normalize_customers(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        Generates OPENING_BALANCE events from customers.
        These act as the initial financial position for the ledger.
        """
        extra_cols = ["business_type", "registration_date", "credit_limit", "payment_terms_days"]
        select_list = [
            pl.col("id").cast(pl.Utf8).alias("customer_id"),
            pl.lit("OPENING_BALANCE").alias("event_type"),
            # Anchor at a very early date to ensure it is the first event
            pl.lit("2000-01-01").str.to_date("%Y-%m-%d").alias("event_date"),
            pl.lit(0.0).alias("amount").cast(pl.Float64),
            pl.lit(0.0).alias("discount_amount").cast(pl.Float64),
            pl.lit(0).alias("is_ok").cast(pl.Int32),
            pl.lit(None).alias("rg_responsibility").cast(pl.Utf8),
            pl.lit(None).alias("payment_mode").cast(pl.Utf8),
            pl.lit(None).alias("bank_name").cast(pl.Utf8),
            pl.lit("customers").alias("source_table"),
            pl.col("id").cast(pl.Utf8).alias("source_raw_id"),
        ]

        for col in extra_cols:
            if col in df.columns:
                if col == "registration_date":
                    select_list.append(self._parse_date_column(df, col).alias(col))
                else:
                    select_list.append(pl.col(col))

        return df.select(select_list).pipe(self._add_event_uid)

    def _normalize_rg(self, df: pl.DataFrame) -> pl.DataFrame:
        # Standardize returns responsibility based on return_reason
        if "return_reason" in df.columns:
            df = df.with_columns(
                pl.col("return_reason")
                .map_elements(
                    lambda x: (
                        "GENUINE"
                        if str(x).lower() in ["genuine", "company fault"]
                        else ("CUSTOMER" if str(x).lower() in ["customer fault", "wrong purchase"] else "UNKNOWN")
                    ),
                    return_dtype=pl.Utf8,
                )
                .alias("rg_responsibility")
            )
        else:
            df = df.with_columns(pl.lit("GENUINE").alias("rg_responsibility"))

        select_list = [
            pl.col("customer_id").cast(pl.Utf8),
            pl.lit("RETURN").alias("event_type"),
            pl.coalesce(
                [
                    self._parse_date_column(df, "return_date"),
                    self._parse_date_column(df, "created_at"),
                ]
            ).alias("event_date"),
            pl.col("return_value").alias("amount").fill_null(0.0).cast(pl.Float64),
            pl.lit(0.0).alias("discount_amount").cast(pl.Float64),
            pl.lit(0).alias("is_ok").cast(pl.Int32),
            pl.col("rg_responsibility"),
            pl.lit(None).alias("payment_mode").cast(pl.Utf8),
            pl.lit(None).alias("bank_name").cast(pl.Utf8),
            pl.lit("raw_returns").alias("source_table"),
            pl.col("id").cast(pl.Utf8).alias("source_raw_id"),
        ]

        if "return_reason" in df.columns:
            select_list.append(pl.col("return_reason"))

        return df.select(select_list).pipe(self._add_event_uid)

    def _add_event_uid(self, df: pl.DataFrame) -> pl.DataFrame:
        # Use a stable identity: event_type + source_raw_id
        return df.with_columns(
            pl.concat_str(
                [
                    pl.col("event_type"),
                    pl.lit("_"),
                    pl.col("source_raw_id"),
                ]
            )
            .str.to_uppercase()
            .alias("event_id")
        )

    async def mark_as_processed(self, processed_ids: dict[str, list[str]], batch_id: str):
        """Marks the records as processed directly in the external raw tables."""

        for table_name, ids in processed_ids.items():
            # Uses cached table definition from _REFLECTED_METADATA
            table = await self._get_table(table_name)
            if table is not None:
                # Check if columns exist before updating
                update_values = {"is_processed": True}
                if "updated_at" in table.c:
                    update_values["updated_at"] = datetime.now(UTC)

                # Process in batches to avoid query size limits
                batch_size = 1000
                for i in range(0, len(ids), batch_size):
                    chunk = ids[i : i + batch_size]
                    stmt = update(table).where(table.c.id.in_(chunk)).values(**update_values)
                    await self.session.execute(stmt)

        await self.session.commit()
