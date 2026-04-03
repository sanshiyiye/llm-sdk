import { z } from 'zod'
import { client, chatStructured } from '../typescript/dist/index.js'

const ProductSchema = z.object({
  name: z.string().describe('商品名称'),
  price: z.number().describe('商品价格'),
  category: z.string().optional().describe('商品分类'),
})

async function main() {
  console.log('=== LLM SDK TypeScript Example ===\n')

  console.log('1. Basic Chat (标准对话):')
  const response = await client.chat('Hello, what is 2+2?')
  console.log('Response:', response.content)
  console.log()

  console.log('2. Structured Output (结构化提取):')
  const product = await chatStructured(
    client,
    'iPhone 16 Pro 售价 7999元，属于手机品类',
    ProductSchema
  )
  console.log('Extracted Product:', JSON.stringify(product, null, 2))
  console.log()

  console.log('3. Session (多轮对话 - 记忆上下文):')
  const session = client.session('你是一个有帮助的助手。')
  const r1 = await session.chat('我叫张三')
  console.log('Assistant:', r1)
  const r2 = await session.chat('我叫什么名字？')
  console.log('Assistant:', r2)
  console.log()

  console.log('4. Fast Chat (快速响应 - 使用 Gemini Flash):')
  const fastResponse = await client.chat('用一句话解释为什么天空是蓝色的', {
    capability: 'fast',
  })
  console.log('Fast Response:', fastResponse.content)
  console.log()

  console.log('5. Think / Reasoning (深度推理):')
  const thinkResponse = await client.chat(
    '请逐步推理：一个农场有鸡和兔子共35只，它们共有94只脚。请问鸡和兔子各有多少只？',
    { capability: 'reasoning' }
  )
  console.log('Think Response:', thinkResponse.content)
  console.log()

  console.log('6. Image Generation (图像生成 - SiliconFlow SD3.5):')
  const imageUrl = await client.imageGen(
    'an island near sea, with seagulls, moon shining over the sea, light house, boats in the background, fish flying over the sea',
    { size: '1024x1024' } 
  )
  console.log('Generated Image URL:', imageUrl)
  console.log()

  console.log('=== Done ===')
}

main().catch(console.error)
