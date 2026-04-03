import { LLMClient } from '../typescript/dist/index.js'

/**
 * 这个例子专门展示如何使用 LLMClient 实例连接到你本地运行的 LiteLLM Proxy。
 * 即使你不使用全局单例的 `client`，也可以通过传入自定义配置来手动连接不同的 Proxy。
 */
async function main() {
  console.log('=== SDK 调用 LiteLLM Proxy 示例 ===\n')

  // 1. 手动实例化一个 LLMClient，并指定你的 Proxy 地址和 Master Key
  // 注意：在生产环境中，你应该将这些敏感信息写在环境变量 (.env) 中
  const proxyClient = new LLMClient({
    baseURL: 'http://127.0.0.1:4000', // LiteLLM Proxy 默认端口是 4000
    apiKey: 'sk-123456',              // 你的 LiteLLM_MASTER_KEY
    maxRetries: 3,                    // 失败重试次数
  })

  console.log('✅ 已成功初始化 LLMClient 实例，指向 http://127.0.0.1:4000')
  console.log('正在发送测试请求...\n')

  try {
    // 2. 测试 1：基础对话路由
    // 这里我们不指定具体模型，只指定能力。Proxy 会自动根据 config.yaml 中的 `auto-chat` 进行路由
    console.log('测试 1: 智能路由请求 (capability: chat)')
    const start1 = Date.now()
    const response1 = await proxyClient.chat('请问中国的首都是哪里？用一句话回答。')
    console.log(`[耗时 ${Date.now() - start1}ms] 代理返回:`, response1.content)
    console.log()

    // 3. 测试 2：指定特定模型
    // 有时候你可能想绕过智能路由，直接调用你在 config.yaml 里配置的具体某个模型别名
    console.log('测试 2: 强制指定模型别名 (model: siliconflow-chat)')
    const start2 = Date.now()
    const response2 = await proxyClient.chat('10的平方是多少？', {
      model: 'siliconflow-chat' // 这个名字必须存在于你的 config.yaml 的 model_list 中
    })
    console.log(`[耗时 ${Date.now() - start2}ms] 代理返回:`, response2.content)
    console.log()

    // 4. 测试 3：测试 Fallback（回退）机制
    // 如果你请求一个配置了 Fallback 的能力，当主模型宕机时，LiteLLM Proxy 会自动尝试备用模型。
    // 这对 SDK 来说是完全透明的！
    console.log('测试 3: 高可用兜底请求 (capability: fast)')
    const response3 = await proxyClient.chat('你好', { capability: 'fast' })
    console.log('代理返回:', response3.content)
    console.log()

    // 5. 测试 4：生图 (image-gen)
    // 这里使用我们在 config.yaml 中配置的生图能力。
    // 之前我们将它指向了 gemini-image-gen (nano-banana-2)
    console.log('测试 4: 生图请求 (image-gen)')
    console.log('正在生成像素休闲游戏资源图...')
    const start4 = Date.now()
    const imageUrl = await proxyClient.imageGen('像素风格的休闲游戏资源列表图，包含小草、石头、树木、金币、爱心，16x16 像素，清晰整齐的网格布局')
    console.log(`[耗时 ${Date.now() - start4}ms] 图片 URL:`, imageUrl)
    console.log()

    console.log('🎉 所有 Proxy 调用测试完成！')
    
  } catch (error: any) {
    console.error('\n❌ 请求失败！')
    console.error('请检查：')
    console.error('1. 你的 LiteLLM Proxy 是否已经启动？(运行 python start_proxy.py)')
    console.error('2. Proxy 的端口是否是 4000？')
    console.error('3. 错误详情:', error.message)
  }
}

main().catch(console.error)
