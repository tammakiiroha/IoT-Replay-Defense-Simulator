"""命令风险二分类 Policy Table + 三冻结 Profile（§3b/§5, G5+G9）。

I(c)=max_k H_k(c) 六维影响度 + θ_I 触发线 + strict/standard/permissive 三冻结 Profile。
运行时唯一入口是预构建的 `PolicyTable.is_critical(cmd)`（O(1)）；`classify_critical` 仅构表用。
θ_R/ΔU 两条触发线为预留接口（D3=A），完整 P_succ 驱动留 Phase 5。
"""
from __future__ import annotations

from dataclasses import dataclass

# H_k 六维：{phys, property, privacy, availability, auth, recovery} ∈ {0..4}；I(c)=max
# 类型用变长 tuple[int, ...]（max 对任意长度成立），与 SimulationConfig.command_impact 对齐；
# 「6 维」是语义约定（默认表与构造遵守），不用定长 tuple 强约束以免与 config 类型漂移。
ImpactVector = tuple[int, ...]


@dataclass(frozen=True)
class ProfileParams:
    """部署前冻结的 Profile 参数（禁运行时反向调参，§5/G9）。"""

    theta_i: int
    theta_r: float
    lam: float


# 三组冻结 Profile（standard = 主线默认）
PROFILE_PARAMS: dict[str, ProfileParams] = {
    "strict": ProfileParams(theta_i=2, theta_r=0.005, lam=0.25),
    "standard": ProfileParams(theta_i=3, theta_r=0.01, lam=1.0),
    "permissive": ProfileParams(theta_i=4, theta_r=0.02, lam=2.0),
}

# 主线命令 6 维影响度冻结表（§3b；SET_SPEED 的 normal/critical 由 phys 维就地决定）
DEFAULT_COMMAND_IMPACT: dict[str, ImpactVector] = {
    "UNLOCK": (2, 4, 1, 1, 4, 2),          # I=4
    "LOCK": (1, 1, 0, 1, 2, 1),            # I=2
    "PAIRING": (0, 2, 2, 1, 4, 3),         # I=4
    "ENABLE_POWER": (3, 3, 0, 2, 1, 1),    # I=3
    "FACTORY_RESET": (1, 3, 1, 4, 2, 4),   # I=4
    "FWD": (1, 0, 0, 1, 0, 0),             # I=1
    "BACK": (1, 0, 0, 1, 0, 0),            # I=1
    "LEFT": (1, 0, 0, 1, 0, 0),            # I=1
    "RIGHT": (1, 0, 0, 1, 0, 0),           # I=1
    "STOP": (0, 0, 0, 1, 0, 0),            # I=1
    "SET_SPEED": (3, 1, 0, 1, 0, 0),       # I=3（争议项：standard critical / permissive normal）
}


def impact_index(h_vec: tuple[int, ...]) -> int:
    """I(c) = max_k H_k(c)（§5）。"""
    return max(h_vec)


def classify_critical(
    cmd: str,
    *,
    policy_source: str,
    profile: str,
    command_impact: dict[str, ImpactVector] | None,
    command_risk: dict[str, float] | None,
    risk_high: float,
    risk_sw: float | None = None,
    delta_u: float | None = None,
) -> bool:
    """单命令分类（构表 helper，**非逐帧运行时入口**）。按 policy_source 三态：
    - legacy：完全等于旧 `command_risk>=risk_high`（profile/impact 不生效）。
    - default_table：用 DEFAULT_COMMAND_IMPACT。
    - custom：用显式 command_impact（None 则 fail-fast）。
    θ_I 为主触发线；risk_sw/delta_u 为预留可选输入（D3=A），提供则 OR 叠加，缺省不激活。
    """
    if policy_source == "legacy":
        return (command_risk or {}).get(cmd, 0.0) >= risk_high
    if policy_source == "custom":
        if command_impact is None:
            raise ValueError("policy_source='custom' requires command_impact")
        impact = command_impact
    elif policy_source == "default_table":
        impact = DEFAULT_COMMAND_IMPACT
    else:
        raise ValueError(f"unknown policy_source: {policy_source!r}")

    params = PROFILE_PARAMS[profile]
    h = impact.get(cmd)
    crit = h is not None and impact_index(h) >= params.theta_i   # θ_I 行（未知命令 -> normal）
    if risk_sw is not None:                                       # 预留：R̃_SW(c) ≥ θ_R（Phase 5）
        crit = crit or (risk_sw >= params.theta_r)
    if delta_u is not None:                                       # 预留：ΔU(c) > 0（Phase 5）
        crit = crit or (delta_u > 0.0)
    return crit


@dataclass(frozen=True)
class PolicyTable:
    """部署前离线算好的 critical 命令集；运行时 `is_critical` 为 O(1) 集合查找（P1/P3）。"""

    critical: frozenset[str]

    @classmethod
    def from_config(
        cls,
        *,
        policy_source: str,
        profile: str,
        command_impact: dict[str, ImpactVector] | None,
        command_risk: dict[str, float] | None,
        risk_high: float,
    ) -> PolicyTable:
        """构造时离线算好 critical 集。命令域由 policy_source 自身决定：
        legacy=command_risk 键、default_table=DEFAULT_COMMAND_IMPACT 键、custom=command_impact 键。
        域外命令 -> is_critical False（normal）。"""
        if policy_source == "legacy":
            universe: list[str] = list((command_risk or {}).keys())
        elif policy_source == "default_table":
            universe = list(DEFAULT_COMMAND_IMPACT.keys())
        elif policy_source == "custom":
            if command_impact is None:
                raise ValueError("policy_source='custom' requires command_impact")
            universe = list(command_impact.keys())
        else:
            raise ValueError(f"unknown policy_source: {policy_source!r}")
        critical = frozenset(
            cmd
            for cmd in universe
            if classify_critical(
                cmd,
                policy_source=policy_source,
                profile=profile,
                command_impact=command_impact,
                command_risk=command_risk,
                risk_high=risk_high,
            )
        )
        return cls(critical=critical)

    def is_critical(self, cmd: str) -> bool:
        return cmd in self.critical
