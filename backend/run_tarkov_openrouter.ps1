$env:LLM_PROVIDER = 'openrouter'
$env:LLM_API_KEY = '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'
$env:LLM_MODEL = 'openai/gpt-4o-mini'
$env:DATABASE_URL = 'sqlite+pysqlite:///tarkov_test.db'
$env:OPENROUTER_BASE_URL = 'https://openrouter.ai/api/v1'
$env:OPENROUTER_HTTP_REFERER = 'https://github.com/trust-trace/trust-trace'
$env:OPENROUTER_X_TITLE = 'trust-trace'

python -m tarkov.main serve
