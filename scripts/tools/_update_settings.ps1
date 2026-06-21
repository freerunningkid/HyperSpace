$path = "$env:USERPROFILE\.claude\settings.json"
$config = @{
    env = @{
        ANTHROPIC_AUTH_TOKEN = "proxy-key"
        ANTHROPIC_BASE_URL = "http://127.0.0.1:15721"
        ANTHROPIC_MODEL = "deepseek-v4-flash"
        ANTHROPIC_DEFAULT_HAIKU_MODEL = "deepseek-v4-flash"
        ANTHROPIC_DEFAULT_HAIKU_MODEL_NAME = "deepseek-v4-flash"
        ANTHROPIC_DEFAULT_SONNET_MODEL = "deepseek-v4-pro"
        ANTHROPIC_DEFAULT_SONNET_MODEL_NAME = "deepseek-v4-pro"
        ANTHROPIC_DEFAULT_OPUS_MODEL = "deepseek-v4-pro"
        ANTHROPIC_DEFAULT_OPUS_MODEL_NAME = "deepseek-v4-pro"
    }
}
$config | ConvertTo-Json -Depth 2 | Set-Content $path -Encoding UTF8
Write-Host "done"
