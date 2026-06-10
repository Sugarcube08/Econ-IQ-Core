from pydantic import BaseModel, Field


class ExecutiveOverviewData(BaseModel):
    active_customers: int = Field(..., description="Number of currently active customers")
    sales_total: float = Field(..., description="Total purchase value in current window")
    sales_previous: float = Field(..., description="Total purchase value in previous window")
    sales_delta: float = Field(..., description="Percentage change in sales between windows")
    collections_total: float = Field(..., description="Total payment value in current window")
    collections_previous: float = Field(..., description="Total payment value in previous window")
    collections_delta: float = Field(..., description="Percentage change in collections between windows")
    outstanding_total: float = Field(..., description="Total current outstanding exposure")
    outstanding_previous: float = Field(..., description="Total outstanding exposure at the end of the previous window")
    outstanding_delta: float = Field(..., description="Percentage change in outstanding exposure between windows")
    overdue_total: float = Field(..., description="Total overdue exposure")
    overdue_previous: float = Field(..., description="Total overdue exposure in the previous window")
    overdue_delta: float = Field(..., description="Percentage change in overdue exposure between windows")
    commercial_health_index: float = Field(..., description="Holistic organizational health score (0-100)")
    commercial_health_previous: float = Field(..., description="Previous holistic organizational health score (0-100)")
    commercial_health_delta: float = Field(..., description="Absolute change in health index score")
    credit_limit_total: float = Field(..., description="Total credit capacity allocated across all customers")
    organization_contribution_total: float = Field(..., description="Total organizational sales volume contribution")
    last_data_date: str | None = Field(..., description="ISO 8601 string of the latest event in the ledger")


class CommercialFlowPoint(BaseModel):
    period: str = Field(..., description="Starting date of the period (daily, weekly, or monthly)")
    sales: float = Field(..., description="Total sales billing within this period")
    payments: float = Field(..., description="Total payments and returns settled within this period")
    outstanding: float = Field(..., description="Longitudinally reconstructed outstanding balance at period end")


class AgingBucketDetail(BaseModel):
    amount: float = Field(..., description="Receivables value in this age group")
    percentage: float = Field(..., description="Percentage of total outstanding exposure in this age group")


class AgingDistributionData(BaseModel):
    current: AgingBucketDetail = Field(..., description="Receivables aged <= 0 days (not yet due)")
    age_0_30: AgingBucketDetail = Field(..., description="Receivables aged 1 to 30 days", serialization_alias="0_30", validation_alias="0_30")
    age_31_60: AgingBucketDetail = Field(..., description="Receivables aged 31 to 60 days", serialization_alias="31_60", validation_alias="31_60")
    age_61_90: AgingBucketDetail = Field(..., description="Receivables aged 61 to 90 days", serialization_alias="61_90", validation_alias="61_90")
    age_91_120: AgingBucketDetail = Field(..., description="Receivables aged 91 to 120 days", serialization_alias="91_120", validation_alias="91_120")
    age_120_plus: AgingBucketDetail = Field(..., description="Receivables aged > 120 days", serialization_alias="120_plus", validation_alias="120_plus")


class StateCountDetail(BaseModel):
    count: int = Field(..., description="Number of customers categorized in this segment")
    percentage: float = Field(..., description="Percentage of active customer base in this segment")


class StateDistributionData(BaseModel):
    HEALTHY: StateCountDetail = Field(..., description="Healthy accounts: Stable credit risk and regular transactions")
    MONITOR: StateCountDetail = Field(..., description="Accounts requiring monitoring: Sporadic behaviors or mild delays")
    CONTRACT: StateCountDetail = Field(..., description="Accounts undergoing contraction: Declining sales volume or key stress flags")
    LIQUIDITY_STRESS: StateCountDetail = Field(..., description="Accounts in critical liquidity stress or active overdue risk")


class CustomerDeltaInfo(BaseModel):
    customer_id: str = Field(..., description="Unique customer identifier")
    customer_name: str = Field(..., description="Full customer name")
    city: str = Field(..., description="Name of customer city")
    trust_score: float | None = Field(..., description="Current trust score (0.0 to 1.0)")
    trust_delta: float | None = Field(..., description="Change in trust score in the current window")
    payment_delta: float | None = Field(..., description="Change in payment score in the current window")
    repayment_health_delta: float | None = Field(..., description="Change in repayment health score in the current window")
    outstanding_delta: float | None = Field(..., description="Change in outstanding dollar balance in the current window")
    state: str | None = Field(..., description="Current behavioral state")
    grade: str | None = Field(..., description="Current overall credit grade classification")
    last_purchased_at: str | None = Field(..., description="ISO 8601 date of the customer's last purchase")


class HighRiskCustomerInfo(BaseModel):
    customer_id: str = Field(..., description="Unique customer identifier")
    customer_name: str = Field(..., description="Full customer name")
    state: str | None = Field(..., description="Current behavioral state")
    grade: str | None = Field(..., description="Current overall credit grade classification")
    trust_score: float | None = Field(..., description="Current trust score (0.0 to 1.0)")
    outstanding_current: float | None = Field(..., description="Current outstanding debt balance")
    overdue_amount: float | None = Field(..., description="Outstanding balance beyond terms")
    credit_limit: float | None = Field(..., description="Current approved credit limit")
    credit_utilization: float | None = Field(..., description="Utilization ratio of allocated credit (outstanding / limit)")
    repayment_health_score: float | None = Field(..., description="Current repayment health index score (0.0 to 1.0)")
    last_purchased_at: str | None = Field(..., description="ISO 8601 date of the customer's last purchase")


class CustomerActivitySummaryData(BaseModel):
    newly_active_customers: int = Field(..., description="Number of customers transitioning from inactive to active trading")
    newly_inactive_customers: int = Field(..., description="Number of previously active customers with no transactions in this window")
    customers_improved: int = Field(..., description="Number of customers with positive trust transitions (>0.05 increase)")
    customers_deteriorated: int = Field(..., description="Number of customers with negative trust transitions (<-0.05 decrease)")
    customers_with_new_overdue: int = Field(..., description="Number of customers who went into overdue status during this window")
    customers_near_credit_limit: int = Field(..., description="Number of customers utilizing >= 90% of their approved credit limit")


class TopContributorInfo(BaseModel):
    customer_id: str = Field(..., description="Unique customer identifier")
    customer_name: str = Field(..., description="Full customer name")
    contribution_percent: float = Field(..., description="Customer's share of total organizational sales volume (%)")
    sales_total: float = Field(..., description="Total purchase billing by this customer in current window")
    outstanding_current: float = Field(..., description="Current outstanding balance of this customer")
    trust_score: float = Field(..., description="Current trust score of this customer")

