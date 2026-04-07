# TypeScript SDK

**Package:** `@goat/llm-sdk` (v1.0.0)  
**Build:** TypeScript 5.4 → ES2022 → CommonJS  
**Dependencies:** openai@^4.52.0, zod@^3.23.0, zod-to-json-schema@^3.23.0

---

## STRUCTURE

```
typescript/
├── index.ts           # Public exports
├── client.ts          # LLMClient class (core)
├── errors.ts          # Error hierarchy
├── session.ts         # Multi-turn Session
├── structured.ts      # Zod-based structured output
├── templates.ts       # Prompt template registry
├── package.json       # NPM config
├── tsconfig.json      # TS strict mode
└── tests/
    └── sdk.test.ts    # Vitest suite
```

---

## QUICK START

```bash
npm install
npm run build
```

```typescript
import { client, templates } from './index'
import { z } from 'zod'

// Basic chat
const reply = await client.chat('Hello')

// Streaming
for await (const chunk of client.chatStream('Write a story')) {
  process.stdout.write(chunk)
}

// Structured output
const schema = z.object({ name: z.string(), price: z.number() })
const result = await client.chatStructured('iPhone costs $999', schema)

// Multi-turn session
const session = client.session('You are a code reviewer')
const r1 = await session.chat('Review: const x = 1')
const r2 = await session.chat('What is the issue?')

// Templates
templates.loadDir('../prompts')
const reply = await templates.chatWithTemplate(client, 'code_review',
  { language: 'TypeScript', focus: 'types', code: 'const x = 1' })
```

---

## CORE EXPORTS

**From `index.ts`:**
- `LLMClient` — Main client class
- `client` — Singleton instance
- `Session` — Multi-turn conversation
- `chatStructured()` — Structured output helper
- `TemplateRegistry`, `templates` — Template system
- All error types (`LLMError`, `RateLimitError`, etc.)
- `TAG_MODEL_MAP` — Capability tag mappings
- `resolveModel()` — Tag resolver function

---

## COMMANDS

```bash
npm run build      # Compile TypeScript
npm test           # Run Vitest suite
npm run test:watch # Watch mode
npm run lint       # Type check only
```

---

## NOTES

- Strict TypeScript mode enabled
- Zod for runtime validation and JSON schema generation
- Uses OpenAI client under the hood
- Auto-retry on RateLimit/Network errors
