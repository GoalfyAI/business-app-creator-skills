"""把 Hub 的 Skill 建议线抬到已登记版本，保留强制线与应急开关。 [任务:T-4466]

QA 分支每出一个候选版就调用一次：旧版本仍能建工单，只会收到升级提示。
策略接口是整体覆盖（PUT /api/internal/workflow/scene-skill-versions/policy），所以先读当前
强制线再写回。按登记 ID 判断先后，同版或较旧版本重跑时跳过写入。
发布工作流须串行运行，人工策略编辑须避开发布窗口；现有 PUT 不提供原子比较更新。

环境变量：HUB_URL（如 https://goalfyhub.qa.goalfyai.cn）、HUB_API_KEY、HUB_APP_ID、
HUB_OPERATOR_EMAIL、HUB_OPERATOR_ID。
用法：python3 scripts/raise_skill_recommended.py v20260924-39692d
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from urllib.parse import urlsplit

POLICY_PATH = "/api/internal/workflow/scene-skill-versions/policy"
RELEASES_PATH = "/api/internal/workflow/scene-skill-versions/releases"


def hub_url(value: str) -> str:
    """限制配置为 Hub 根地址，避免把凭据或查询参数带入日志。"""
    parts = urlsplit(value.strip())
    if (
        parts.scheme not in {"http", "https"}
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or parts.path not in {"", "/"}
        or parts.query
        or parts.fragment
    ):
        raise RuntimeError("Hub 地址必须是无凭据、路径和查询参数的 HTTP(S) 根地址")
    return value.strip().rstrip("/")


def operator_headers(target: dict) -> dict[str, str]:
    """在任何写入前校验操作身份，错误信息只包含字段名。"""
    headers = {}
    fields = {
        "api_key": "X-API-Key",
        "operator_email": "X-Operator-Email",
        "operator_id": "X-Operator-ID",
    }
    for field, header in fields.items():
        raw = target.get(field, "")
        if not isinstance(raw, str) and not (field == "operator_id" and type(raw) is int):
            raise RuntimeError(f"抬线配置缺失或无效：{field}")
        value = str(raw).strip()
        if not value or "\n" in value or "\r" in value:
            raise RuntimeError(f"抬线配置缺失或无效：{field}")
        headers[header] = value
    if not headers["X-Operator-ID"].isdigit() or int(headers["X-Operator-ID"]) <= 0:
        raise RuntimeError("抬线配置 operator_id 必须是正整数")
    app_id = target.get("app_id", "goalfymax")
    if not isinstance(app_id, str) or not app_id.strip() or "\n" in app_id or "\r" in app_id:
        raise RuntimeError("抬线配置 app_id 无效")
    headers.update({
        "X-App-ID": app_id.strip(),
        "X-User-ID": headers["X-Operator-ID"],
        "Content-Type": "application/json",
    })
    return headers


def release_targets(registry_targets: list[tuple[str, str]]) -> list[tuple[str, dict]]:
    """正式抬线目标必须与登记目标逐个对应，全部配置校验后才允许写入。"""
    raw = os.environ.get("SCENE_SKILL_RELEASE_RECOMMENDED_TARGETS", "").strip()
    try:
        targets = json.loads(raw)
    except (ValueError, TypeError):
        raise RuntimeError("SCENE_SKILL_RELEASE_RECOMMENDED_TARGETS 必须是非空 JSON 数组") from None
    if not isinstance(targets, list) or not targets:
        raise RuntimeError("SCENE_SKILL_RELEASE_RECOMMENDED_TARGETS 必须是非空 JSON 数组")
    parsed = []
    for target in targets:
        if not isinstance(target, dict) or not isinstance(target.get("hub_url"), str):
            raise TypeError("抬线目标必须包含 hub_url")
        parsed.append((hub_url(target["hub_url"]), operator_headers(target)))
    registry_hubs = []
    for endpoint, _ in registry_targets:
        parts = urlsplit(endpoint)
        if parts.query or parts.fragment or parts.username is not None or parts.password is not None:
            raise RuntimeError("登记目标 URL 不能包含凭据、查询参数或片段")
        registry_hubs.append(hub_url(f"{parts.scheme}://{parts.netloc}"))
    hubs = [hub for hub, _ in parsed]
    if len(set(hubs)) != len(hubs) or len(set(registry_hubs)) != len(registry_hubs):
        raise RuntimeError("登记或抬线目标重复")
    if set(hubs) != set(registry_hubs):
        raise RuntimeError("登记与抬线目标 Hub 必须一一对应")
    return parsed


def request(method: str, url: str, headers: dict[str, str], body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        result = json.loads(response.read() or b"{}")
    if not isinstance(result, dict) or result.get("code", 0) != 0:
        raise RuntimeError("Hub 返回无效响应或业务失败")
    return result


def read_policy(data: dict) -> dict:
    """null 表示 Hub 尚无策略行；已有策略必须完整，不能用默认值覆盖未知字段。"""
    if "policy" not in data:
        raise RuntimeError("Hub 响应缺少版本策略")
    policy = data["policy"]
    if policy is None:
        return {"min_required_version": "", "min_recommended_version": "",
                "emergency_bypass": False}
    if not isinstance(policy, dict):
        raise TypeError("Hub 版本策略响应无效")
    if (
        not isinstance(policy.get("min_required_version"), str)
        or not isinstance(policy.get("min_recommended_version"), str)
        or type(policy.get("emergency_bypass")) is not bool
    ):
        raise RuntimeError("Hub 版本策略字段缺失或类型无效")
    return policy


def raise_recommended(version: str, hub: str, headers: dict[str, str]) -> None:
    """只提升建议线；结果未知时由下次运行先读取对账，不自动重发 PUT。"""
    payload = request("GET", hub + RELEASES_PATH, headers)
    data = payload.get("data", payload)
    if not isinstance(data, dict):
        raise TypeError("Hub 发布记录响应无效")
    policy = read_policy(data)
    registered = {}
    for row in data.get("releases") or []:
        if not isinstance(row, dict):
            raise TypeError("Hub 发布记录无效")
        release_id = row.get("id")
        if type(release_id) is not int or release_id <= 0:
            raise RuntimeError("Hub 发布记录缺少有效登记 ID")
        registered[row.get("version_string")] = release_id
    if version not in registered:
        raise RuntimeError("目标版本尚未在 Hub 登记，不能设为建议线")
    current = policy.get("min_recommended_version") or ""
    if current and current not in registered:
        raise RuntimeError("当前建议线指向未登记版本，停止写入")
    if current and registered[current] >= registered[version]:
        print(f"{hub} 建议线已是同版或更新登记版本，跳过")
        return
    body = {
        "min_required_version": policy.get("min_required_version") or "",
        "min_recommended_version": version,
        "emergency_bypass": bool(policy.get("emergency_bypass")),
    }
    request("PUT", hub + POLICY_PATH, headers, body)
    after = request("GET", hub + RELEASES_PATH, headers)
    after_data = after.get("data", after)
    if not isinstance(after_data, dict) or not isinstance(after_data.get("policy"), dict):
        raise TypeError("写入后策略响应无效")
    after_policy = read_policy(after_data)
    if any(after_policy.get(field) != value for field, value in body.items()):
        raise RuntimeError("写入后读回策略不一致，停止并人工对账")
    print(f"{hub} 建议线已抬到 {version}，强制线和应急开关保持不变")


def main() -> int:
    if len(sys.argv) != 2 or not sys.argv[1].strip():
        print("用法：raise_skill_recommended.py <skill 版本>", file=sys.stderr)
        return 2
    try:
        hub = hub_url(os.environ.get("HUB_URL", ""))
        headers = operator_headers({
            "api_key": os.environ.get("HUB_API_KEY", ""),
            "app_id": os.environ.get("HUB_APP_ID") or "goalfymax",
            "operator_email": os.environ.get("HUB_OPERATOR_EMAIL", ""),
            "operator_id": os.environ.get("HUB_OPERATOR_ID", ""),
        })
        raise_recommended(sys.argv[1].strip(), hub, headers)
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        # 不打印服务端正文或含配置值的异常，避免凭据随响应进入日志。
        print(f"抬建议线失败：{type(exc).__name__}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
