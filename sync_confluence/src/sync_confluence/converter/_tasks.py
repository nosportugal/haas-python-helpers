"""Convert task-list checkboxes into Confluence ``ac:task-list`` structures.

Task UUIDs are derived deterministically (``uuid5``) from a per-document task
index so that re-rendering the same document yields an identical body.
"""

from __future__ import annotations

import uuid

from sync_confluence.converter._csf import AC, ElementType
from sync_confluence.converter._tree import replace_element

_TASK_NAMESPACE = uuid.UUID("6f1a2c34-0000-5000-8000-000000000000")


def _task_status(li: ElementType) -> str:
    checkbox = li.find("input")
    if checkbox is not None and checkbox.get("checked") is not None:
        return "complete"
    return "incomplete"


def _build_task(li: ElementType, index: int) -> ElementType:
    task = AC("task")
    task_uuid = str(uuid.uuid5(_TASK_NAMESPACE, str(index)))
    task.append(AC("task-id", str(index)))
    task.append(AC("task-uuid", task_uuid))
    task.append(AC("task-status", _task_status(li)))
    body = AC("task-body")
    body.text = "".join(li.itertext()).strip()
    task.append(body)
    return task


def transform_tasks(root: ElementType) -> None:
    """Rewrite checkbox lists into Confluence ``ac:task-list`` structures."""
    index = 0
    for unordered in list(root.iter("ul")):
        if "task-list" not in (unordered.get("class") or "").split():
            continue
        task_list = AC("task-list")
        for li in unordered.findall("li"):
            index += 1
            task_list.append(_build_task(li, index))
        replace_element(unordered, task_list)
