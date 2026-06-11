import polars as pl
from loguru import logger


class PaymentModeDimensionEngine:
    """
    Dimension 11: Payment Method Behavior
    Focus: Payment mode signals (Digital vs Cash vs Cheque).
    """
    def compute(self, features_df: pl.DataFrame) -> pl.DataFrame:
        if features_df.is_empty():
            return pl.DataFrame({"customer_id": [], "date": [], "dim_payment_mode": []})

        logger.debug("Computing Dimension 11: Payment Method Behavior")
        
        # Payment modes is a List(Utf8) column
        df = features_df.select(["customer_id", "date", "payment_modes_window"])

        def calculate_digital_ratio(modes) -> float:
            if modes is None:
                return 0.5
            if hasattr(modes, "to_list"):
                modes = modes.to_list()
            if not modes:
                return 0.5 # Neutral
            digital_terms = ["DIGITAL", "BANK TRANSFER", "UPI", "NEFT", "RTGS", "ONLINE"]
            digital_count = sum(1 for m in modes if str(m or "").upper() in digital_terms)
            return digital_count / len(modes)

        df = df.with_columns(
            pl.col("payment_modes_window").map_elements(calculate_digital_ratio, return_dtype=pl.Float64).alias("digital_ratio")
        )

        # Dimension score: Preference for digital/traceable payments
        df = df.with_columns(
            pl.col("digital_ratio").alias("dim_payment_mode")
        )

        return df.select(["customer_id", "date", "dim_payment_mode"])
