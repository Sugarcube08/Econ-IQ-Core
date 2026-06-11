import polars as pl
from loguru import logger


class CreditDimensionEngine:
    """
    Dimension 3: Credit Behavior
    Focus: Leverage and exposure management.
    """
    def compute(self, pressure_df: pl.DataFrame) -> pl.DataFrame:
        empty_schema = {"customer_id": pl.Utf8, "date": pl.Date, "dim_credit": pl.Float64}
        if pressure_df.is_empty():
            return pl.DataFrame(schema=empty_schema)

        logger.debug("Computing Dimension 3: Credit Behavior")

        df = pressure_df.select(
            [
                "customer_id", 
                "date", 
                "exposure_pressure_score",
                "unresolved_exposure_ratio", 
                "clearance_strength"
            ]
        )

        df = df.with_columns(
            [
                pl.col("exposure_pressure_score").fill_null(1.0),
                pl.col("unresolved_exposure_ratio").fill_null(1.0),
                pl.col("clearance_strength").fill_null(0.0),
            ]
        )

        # High pressure/ratio is bad, clearance is good.
        # We want the dimension to be higher for GOOD credit behavior.
        # exposure_pressure_score in V1 goes up when bad. We invert it.
        
        df = df.with_columns(
            (1.0 - pl.col("exposure_pressure_score").clip(0, 1)).alias("pressure_management_score"),
            (1.0 - pl.col("unresolved_exposure_ratio").clip(0, 1)).alias("utilization_score"),
            pl.col("clearance_strength").clip(0, 1).alias("clearance_score")
        )

        w_press, w_util, w_clear = 0.4, 0.4, 0.2
        
        df = df.with_columns(
            (
                pl.col("pressure_management_score") * w_press +
                pl.col("utilization_score") * w_util +
                pl.col("clearance_score") * w_clear
            ).clip(0, 1).alias("dim_credit")
        )

        return df.select(["customer_id", "date", "dim_credit"])
