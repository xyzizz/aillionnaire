"""通知发送模块（程序化调用，非 CrewAI Tool）。

在 Crew 执行完毕后由 main.py 直接调用，确保通知 100% 可靠发送。
"""

import logging
import os

import requests

logger = logging.getLogger(__name__)


def send_wechat_notification(subject: str, body: str) -> str:
    """通过 PushPlus 发送微信通知。

    Args:
        subject: 通知标题，如 "NVDA.US [HOLD]"
        body: 通知正文（中文投资建议报告）

    Returns:
        发送状态描述字符串
    """
    pushplus_token = os.getenv("PUSHPLUS_TOKEN")

    if not pushplus_token:
        msg = "WeChat notification skipped: PushPlus Token not configured."
        logger.warning(msg)
        return msg

    logger.info(f"Sending WeChat notification: {subject}")

    try:
        response = requests.post(
            "https://www.pushplus.plus/send",
            json={
                "token": pushplus_token,
                "title": subject,
                "content": body,
                "channel": "wechat",
            },
            timeout=10,
        )
        response.raise_for_status()
        msg = "WeChat notification sent successfully."
        logger.info(msg)
        return msg

    except requests.exceptions.RequestException as e:
        msg = f"Error sending WeChat notification: {e}"
        logger.error(msg, exc_info=True)
        return msg
    except Exception as e:
        msg = f"Unexpected error sending WeChat notification: {e}"
        logger.error(msg, exc_info=True)
        return msg


def send_batch_notification(reports: list[dict]) -> str:
    """批量发送多只股票的分析报告（合并为一条通知）。

    Args:
        reports: 列表，每个元素包含 ticker, decision, report 字段

    Returns:
        发送状态描述字符串
    """
    if not reports:
        return "No reports to send."

    # 构建标题：汇总所有股票的决策
    decisions = [f"{r['ticker']}[{r['decision']}]" for r in reports]
    subject = f"每日投资分析 | {' '.join(decisions)}"

    # 构建正文：拼接所有报告
    body_parts = []
    for r in reports:
        body_parts.append(f"{'=' * 40}")
        body_parts.append(f"📊 {r['ticker']} - {r.get('name', '')} [{r['decision']}]")
        body_parts.append(f"{'=' * 40}")
        body_parts.append(r["report"])
        body_parts.append("")

    body = "\n".join(body_parts)

    return send_wechat_notification(subject, body)
