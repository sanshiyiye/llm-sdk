# 测试Proxy连通性
$headers = @{
    "Content-Type" = "application/json"
    "Authorization" = "Bearer sk-123456"
}

$body = @{
    model = "Pro/zai-org/GLM-4.7"
    messages = @(
        @{
            role = "user"
            content = "Hello from SiliconFlow!"
        }
    )
    max_tokens = 50
} | ConvertTo-Json

$response = Invoke-RestMethod -Uri "http://localhost:4000/v1/chat/completions" -Method Post -Headers $headers -Body $body
Write-Host "Response: $($response.choices[0].message.content)"