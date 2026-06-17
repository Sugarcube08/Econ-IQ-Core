import enum

class CustomerState(str, enum.Enum):
    DORMANT = "dormant"
    DISTRESSED = "distressed"
    STRESSED = "stressed"
    OVERLEVERAGED = "overleveraged"
    DECLINING = "declining"
    RECOVERING = "recovering"
    EXPANDING = "expanding"
    GROWING = "growing"
    HEALTHY = "healthy"

class RiskDirection(str, enum.Enum):
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"

class TrustDirection(str, enum.Enum):
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"

class CustomerArchetype(str, enum.Enum):
    WHALE = "whale"
    GROWING_RETAILER = "growing_retailer"
    DECLINING_RETAILER = "declining_retailer"
    LIQUIDITY_STRESSED = "liquidity_stressed"
    STABLE_RETAILER = "stable_retailer"

class SnapshotSource(str, enum.Enum):
    BATCH = "BATCH"
    REALTIME = "REALTIME"
