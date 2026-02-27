source /Users/jeff/claude_project/ygai/venv/bin/activate

unset http_proxy https_proxy all_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY
SSL_CERT_FILE=/Users/jeff/claude_project/ygai/venv/lib/python3.12/site-packages/certifi/cacert.pem
REQUESTS_CA_BUNDLE=/Users/jeff/claude_project/ygai/venv/lib/python3.12/site-packages/certifi/cacert.pem

python manage.py run_dingtalk_bot