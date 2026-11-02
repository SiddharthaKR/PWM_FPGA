#!/bin/bash
# Works from whatever folder this script lives in
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
source "$DIR/bin/activate"
export UPSTREAM=http://127.0.0.1:1234
export TEMPLATE="$DIR/gemma4_chat_template.jinja"
exec uvicorn gemma4_proxy:app --host 0.0.0.0 --port 8088 >> "$DIR/proxy.log" 2>&1
