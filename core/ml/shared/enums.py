import enum


class CustomerState(enum.StrEnum):
    DORMANT = "dormant"
    DISTRESSED = "distressed"
    STRESSED = "stressed"
    OVERLEVERAGED = "overleveraged"
    DECLINING = "declining"
    RECOVERING = "recovering"
    EXPANDING = "expanding"
    GROWING = "growing"
    HEALTHY = "healthy"

class RiskDirection(enum.StrEnum):
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"

class TrustDirection(enum.StrEnum):
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"

class CustomerArchetype(enum.StrEnum):
    WHALE = "whale"
    GROWING_RETAILER = "growing_retailer"
    DECLINING_RETAILER = "declining_retailer"
    LIQUIDITY_STRESSED = "liquidity_stressed"
    STABLE_RETAILER = "stable_retailer"

class SnapshotSource(enum.StrEnum):
    BATCH = "BATCH"
    REALTIME = "REALTIME"
