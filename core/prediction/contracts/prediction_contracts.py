from pydantic import BaseModel, Field


class ModelMetadataContract(BaseModel):
    """
    Contract describing model metadata, execution signature, and framework details.
    """
    model_name: str = Field(..., description="Name of the registered estimator")
    model_version: str = Field(..., description="Semantic version of the model, e.g. 1.0.0")
    framework: str = Field(..., description="Framework used, e.g. XGBoost, LightGBM, CatBoost")
    features_required: list[str] = Field(default_factory=list, description="List of feature names required for inference")
    hyperparameters: dict[str, float | int | str] = Field(default_factory=dict, description="Model training parameters")
