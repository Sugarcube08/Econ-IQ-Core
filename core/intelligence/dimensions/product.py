import polars as pl


class ProductDimensionEngine:
    """
    Dimension 5: Product Behavior (Consolidated: Product + Concentration)
    Focus: Catalog penetration and concentration risk.
    """
    def compute(self, features_df: pl.DataFrame, org_metrics: dict | None = None) -> pl.DataFrame:
        empty_schema = {"customer_id": pl.Utf8, "date": pl.Date, "dim_product": pl.Float64}
        if features_df.is_empty():
            return pl.DataFrame(schema=empty_schema)


        df = features_df.select(
            [
                "customer_id", 
                "date", 
                "category_diversity_count",
                "product_diversity_count",
                "sales_events_window"
            ]
        )

        df = df.with_columns(
            [
                pl.col("category_diversity_count").fill_null(0),
                pl.col("product_diversity_count").fill_null(0),
                pl.col("sales_events_window").fill_null(1),
            ]
        )

        # Diversification / SKU Breadth
        # Assume > 3 categories is high diversity
        df = df.with_columns(
            (pl.col("category_diversity_count") / 3.0).clip(0, 1).alias("category_diversity_score"),
            # Products per sales event (Basket Complexity / SKU Breadth)
            pl.when(pl.col("sales_events_window") > 0)
            .then((pl.col("product_diversity_count") / pl.col("sales_events_window")).clip(0, 3) / 3.0)
            .otherwise(0.0)
            .alias("basket_complexity_score")
        )

        w_cat, w_basket = 0.6, 0.4
        
        df = df.with_columns(
            (
                pl.col("category_diversity_score") * w_cat +
                pl.col("basket_complexity_score") * w_basket
            ).clip(0, 1).alias("dim_product")
        )

        return df.select(["customer_id", "date", "dim_product"])

