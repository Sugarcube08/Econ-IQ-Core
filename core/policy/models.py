from pydantic import BaseModel, Field

class TrustPolicy(BaseModel):
    purchase_weight: float = Field(0.50, description="Weight of purchase behavior score")
    payment_weight: float = Field(0.50, description="Weight of payment behavior score")

class StatePolicy(BaseModel):
    # Overall class trust score thresholds
    class_a_threshold: float = Field(0.70, description="Trust score threshold for Class A")
    class_b_threshold: float = Field(0.55, description="Trust score threshold for Class B")
    class_c_threshold: float = Field(0.40, description="Trust score threshold for Class C")
    
    # State thresholds
    elite_trust_threshold: float = Field(0.75, description="Trust score threshold for Elite state")
    elite_stress_threshold: float = Field(0.15, description="Stress score threshold for Elite state")
    active_trust_threshold: float = Field(0.45, description="Trust score threshold for Active state")
    active_stress_threshold: float = Field(0.35, description="Stress score threshold for Active state")
    declining_stress_threshold: float = Field(0.50, description="Stress score threshold for Declining override")
    
    # Trajectory velocity ratio thresholds
    accelerating_ratio: float = Field(1.5, description="Velocity ratio to classify as ACCELERATING")
    growing_ratio: float = Field(1.1, description="Velocity ratio to classify as GROWING")
    declining_ratio: float = Field(0.8, description="Velocity ratio to classify as DECLINING")
    collapsing_ratio: float = Field(0.5, description="Velocity ratio to classify as COLLAPSING")

class PaymentPolicy(BaseModel):
    # Subfactor weights (must sum to 1.0)
    delay_weight: float = Field(0.25, description="Weight of payment delay score")
    consistency_weight: float = Field(0.15, description="Weight of payment consistency score")
    partial_habit_weight: float = Field(0.10, description="Weight of partial payment habit score")
    clearance_weight: float = Field(0.15, description="Weight of clearance score")
    weight_aging: float = Field(0.15, description="Weight of aging score")
    discipline_weight: float = Field(0.10, description="Weight of outstanding discipline score")
    breach_weight: float = Field(0.10, description="Weight of credit day breach score")
    
    # Delay score decay parameters
    delay_healthy_days: int = Field(30, description="Days below which delay score is 1.0")
    delay_warning_days: int = Field(90, description="Days below which delay score decays to 0.4")
    delay_critical_days: int = Field(180, description="Days below which delay score decays to 0.0")
    delay_warning_score: float = Field(0.4, description="Score at delay_warning_days")
    
    # Partial payment fragmentation
    partial_habit_max_fragmentation: float = Field(2.5, description="Fragmentation value above which score is 0.0")
    
    # Individualized clearance
    clearance_critical_ratio: float = Field(3.0, description="Ratio of outstanding to avg billing above which score is 0.0")
    
    # Exposure aging weights
    aging_60_90_weight: float = Field(0.2, description="Penalty weight for 60-90 days overdue")
    aging_90_120_weight: float = Field(0.5, description="Penalty weight for 90-120 days overdue")
    aging_120p_weight: float = Field(1.0, description="Penalty weight for 120+ days overdue")
    
    # Outstanding pressure
    discipline_scale_factor: float = Field(2.0, description="Scale factor for outstanding pressure score")
    
    # Credit day breach
    breach_expected_threshold: int = Field(60, description="Expected payment days threshold")
    breach_max_days: float = Field(120.0, description="Max breach days scaled")
    breach_scaling_factor: float = Field(60.0, description="Scaling denominator for breach score")
    
    # Evidence strength confidence caps
    evidence_caps: list[dict[str, float]] = Field(
        default=[
            {"limit": 0.2, "cap": 0.60},
            {"limit": 0.4, "cap": 0.75},
            {"limit": 0.6, "cap": 0.90}
        ],
        description="Graduated confidence caps based on evidence strength"
    )

class StressPolicy(BaseModel):
    customer_fault_weight: float = Field(1.0, description="Penalty weight for customer fault return")
    genuine_fault_weight: float = Field(0.0, description="Penalty weight for genuine/company fault return")
    unknown_fault_weight: float = Field(0.8, description="Penalty weight for unknown fault return")
    stress_rg_weight: float = Field(0.8, description="Weight of returns ratio in stress score")
    stress_deficiency_weight: float = Field(0.2, description="Weight of payment deficiency in stress score")

class EconiqPolicy(BaseModel):
    trust: TrustPolicy = Field(default_factory=TrustPolicy)
    state: StatePolicy = Field(default_factory=StatePolicy)
    payment: PaymentPolicy = Field(default_factory=PaymentPolicy)
    stress: StressPolicy = Field(default_factory=StressPolicy)
