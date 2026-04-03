"""
Prompt 模板管理器
================
用法:
    from llm_sdk import client, templates

    # 代码注册
    templates.register("code_review",
        system="你是一个资深 {language} 工程师。",
        user="审查以下代码，关注 {focus}:\n\n{code}")

    # 文件目录加载（自动扫描 prompts/ 目录下的 .txt 文件）
    templates.load_dir("prompts/")

    # 使用模板
    reply = client.chat_with_template("code_review",
        language="Python", focus="内存泄漏", code=my_code)

模板文件格式（prompts/code_review.txt）:
    system: 你是一个资深 {language} 工程师。
    ---
    审查以下代码，关注 {focus}:

    {code}

    若无 system: 开头和 --- 分隔，整个文件视为 user prompt 模板。
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from .errors import TemplateNotFoundError

if TYPE_CHECKING:
    from .client import LLMClient


@dataclass
class PromptTemplate:
    name: str
    user_template: str
    system_template: str | None = None

    def render(self, **variables: str) -> tuple[str, str | None]:
        """渲染模板，返回 (user_prompt, system_prompt | None)"""
        user = self.user_template.format(**variables)
        system = self.system_template.format(**variables) if self.system_template else None
        return user, system


class TemplateRegistry:
    def __init__(self):
        self._registry: dict[str, PromptTemplate] = {}

    def register(
        self,
        name: str,
        user: str,
        system: str | None = None,
    ) -> None:
        """代码注册模板"""
        self._registry[name] = PromptTemplate(
            name=name,
            user_template=user.strip(),
            system_template=system.strip() if system else None,
        )

    def load_dir(self, directory: str) -> int:
        """
        扫描目录，加载所有 .txt 文件为模板。
        文件名（不含扩展名）作为模板名称。
        返回加载的模板数量。
        """
        count = 0
        for path in Path(directory).glob("*.txt"):
            name = path.stem
            content = path.read_text(encoding="utf-8")
            tmpl = _parse_template_file(name, content)
            self._registry[name] = tmpl
            count += 1
        return count

    def get(self, name: str) -> PromptTemplate:
        tmpl = self._registry.get(name)
        if tmpl is None:
            raise TemplateNotFoundError(name)
        return tmpl

    def list(self) -> list[str]:
        return list(self._registry.keys())

    def chat_with_template(
        self,
        llm: "LLMClient",
        template_name: str,
        *,
        capability: str | None = None,
        model: str | None = None,
        **variables,
    ) -> str:
        """渲染模板并调用 LLM"""
        tmpl = self.get(template_name)
        user_prompt, system_prompt = tmpl.render(**variables)
        return llm.chat(
            user_prompt,
            system=system_prompt,
            capability=capability,
            model=model,
        )


def _parse_template_file(name: str, content: str) -> PromptTemplate:
    """
    解析模板文件。
    格式一（有 system）：
        system: <system 文本，可多行>
        ---
        <user 模板>

    格式二（纯 user）：
        <user 模板>
    """
    content = content.strip()

    # 检查是否有 system 段
    if content.lower().startswith("system:"):
        parts = re.split(r"\n---\n", content, maxsplit=1)
        if len(parts) == 2:
            system_raw = parts[0]
            # 去掉开头的 "system:"
            system_text = re.sub(r"^system:\s*", "", system_raw, flags=re.IGNORECASE).strip()
            user_text = parts[1].strip()
            return PromptTemplate(
                name=name,
                user_template=user_text,
                system_template=system_text,
            )

    return PromptTemplate(name=name, user_template=content)


# ── 全局注册表单例 ────────────────────────────────────────────────────────────
templates = TemplateRegistry()
