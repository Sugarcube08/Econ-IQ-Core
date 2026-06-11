import polars as pl
from loguru import logger


class ConcentrationDimensionEngine:
    """
    Dimension 10: Portfolio Concentration
    Focus: Diversified buying vs single-product dependency.
    """
    def compute(self, features_df: pl.DataFrame) -> pl.DataFrame:
        if features_df.is_empty():
            return pl.DataFrame({"customer_id": [], "date": [], "dim_concentration": []})

        logger.debug("Computing Dimension 10: Portfolio Concentration")
        
        df = features_df.select(
            [
                "customer_id", 
                "date", 
                "category_diversity_count",
                "product_diversity_count",
                "sales_events_window"
            ]
        )

        # Diversification Scores
        # Assume > 5 categories is high diversity
        df = df.with_columns(
            (pl.col("category_diversity_count") / 5.0).clip(0, 1).alias("category_diversity_score"),
            # Products per sales event (Basket Complexity)
            pl.when(pl.col("sales_events_window") > 0)
            .then((pl.col("product_diversity_count") / pl.col("sales_events_window")).clip(0, 5) / 5.0)
            .otherwise(0.0)
            .alias("basket_complexity_score")
        )

        w_cat, w_basket = 0.6, 0.4
        
        df = df.with_columns(
            (
                pl.col("category_diversity_score") * w_cat +
                pl.col("basket_complexity_score") * w_basket
            ).clip(0, 1).alias("dim_concentration")
        )

        return df.select(["customer_id", "date", "dim_concentration"])
