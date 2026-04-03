# 动态模型调用的Python封装
"""
允许传入任意模型名，自动路由到合适的提供商
"""

import os
import requests
from typing import Optional, Dict, Any

class DynamicLLMClient:
    def __init__(self, base_url: str = "http://localhost:4000", api_key: str = "sk-123456"):
        self.base_url = base_url
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
    
    def chat_with_model(self, model: str, message: str, max_tokens: int = 100) -> str:
        """
        使用指定模型进行对话
        
        Args:
            model: 模型名，如 "Pro/zai-org/GLM-4.7" 或 "auto-chat"
            message: 用户消息
            max_tokens: 最大token数
            
        Returns:
            模型响应内容
        """
        
        # 映射表：将外部模型名映射到Proxy配置的模型
        model_mapping = {
            # SiliconFlow模型
            "Pro/zai-org/GLM-4.7": "siliconflow-chat",
            "Pro/zai-org/GLM-4.5V": "siliconflow-vision", 
            "deepseek-ai/DeepSeek-V3.2": "siliconflow-chat",
            
            # OpenAI模型
            "gpt-3.5-turbo": "gpt-chat",
            "gpt-4o": "gpt-vision",
            
            # 如果找不到映射，使用capability标签
            "default": "auto-chat"
        }
        
        # 选择要使用的模型
        proxy_model = model_mapping.get(model, model_mapping["default"])
        
        data = {
            "model": proxy_model,
            "messages": [
                {"role": "user", "content": message}
            ],
            "max_tokens": max_tokens
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/v1/chat/completions",
                headers=self.headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            else:
                raise Exception(f"API调用失败: {response.status_code} - {response.text}")
                
        except Exception as e:
            raise Exception(f"调用失败: {e}")

# 使用示例
if __name__ == "__main__":
    client = DynamicLLMClient()
    
    # 可以直接使用SiliconFlow的模型名
    response = client.chat_with_model(
        model="Pro/zai-org/GLM-4.7",
        message="你好，这是动态模型测试"
    )
    print(f"响应: {response}")
    
    # 也可以使用capability标签
    response2 = client.chat_with_model(
        model="auto-chat",
        message="你好，这是capability测试"
    )
    print(f"响应: {response2}")