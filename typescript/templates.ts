/**
 * Prompt 模板管理器
 * =================
 * 用法:
 *   import { templates } from './llm_sdk'
 *   templates.register('greet', { user: '用 {lang} 打招呼' })
 *   const reply = await templates.chatWithTemplate(client, 'greet', { lang: '日语' })
 *
 * 模板文件格式 (prompts/code_review.txt):
 *   system: 你是一个资深 {language} 工程师。
 *   ---
 *   审查以下代码，关注 {focus}:
 *
 *   {code}
 */

import * as fs from 'fs'
import * as path from 'path'
import { TemplateNotFoundError } from './errors'
import type { LLMClient, ChatOptions } from './client'

interface PromptTemplate {
  name: string
  userTemplate: string
  systemTemplate?: string
}

function renderTemplate(template: string, vars: Record<string, string>): string {
  return template.replace(/\{(\w+)\}/g, (_, key) => {
    if (!(key in vars)) throw new Error(`模板变量未提供: '${key}'`)
    return vars[key]
  })
}

function parseTemplateFile(name: string, content: string): PromptTemplate {
  content = content.trim()
  if (/^system:/i.test(content)) {
    const parts = content.split(/\n---\n/)
    if (parts.length >= 2) {
      const systemText = parts[0].replace(/^system:\s*/i, '').trim()
      const userText = parts.slice(1).join('\n---\n').trim()
      return { name, userTemplate: userText, systemTemplate: systemText }
    }
  }
  return { name, userTemplate: content }
}

export class TemplateRegistry {
  private registry = new Map<string, PromptTemplate>()

  register(name: string, opts: { user: string; system?: string }): void {
    this.registry.set(name, {
      name,
      userTemplate: opts.user.trim(),
      systemTemplate: opts.system?.trim(),
    })
  }

  loadDir(directory: string): number {
    const files = fs.readdirSync(directory).filter(f => f.endsWith('.txt'))
    for (const file of files) {
      const name = path.basename(file, '.txt')
      const content = fs.readFileSync(path.join(directory, file), 'utf-8')
      this.registry.set(name, parseTemplateFile(name, content))
    }
    return files.length
  }

  get(name: string): PromptTemplate {
    const tmpl = this.registry.get(name)
    if (!tmpl) throw new TemplateNotFoundError(name)
    return tmpl
  }

  list(): string[] {
    return [...this.registry.keys()]
  }

  async chatWithTemplate(
    llm: LLMClient,
    templateName: string,
    variables: Record<string, string>,
    opts: Omit<ChatOptions, 'system'> = {},
  ): Promise<string> {
    const tmpl = this.get(templateName)
    const userPrompt = renderTemplate(tmpl.userTemplate, variables)
    const system = tmpl.systemTemplate
      ? renderTemplate(tmpl.systemTemplate, variables)
      : undefined
    const result = await llm.chat(userPrompt, { ...opts, system })
    return typeof result === 'string' ? result : result.content
  }
}

export const templates = new TemplateRegistry()
