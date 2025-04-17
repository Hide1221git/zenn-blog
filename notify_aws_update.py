import feedparser
import requests
from openai import OpenAI
import os
import sys

# === 設定 ===
AWS_RSS_URL = "https://aws.amazon.com/new/feed/"
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# === バリデーション ===
if not SLACK_WEBHOOK_URL or not OPENAI_API_KEY:
    print("環境変数 SLACK_WEBHOOK_URL または OPENAI_API_KEY が設定されていません。", file=sys.stderr)
    sys.exit(1)

# === AWSの最新フィードを取得 ===
def fetch_aws_update():
    feed = feedparser.parse(AWS_RSS_URL)
    if not feed.entries:
        raise Exception("RSSフィードが空です")
    latest = feed.entries[0]
    return {
        "title": latest.title,
        "summary": latest.summary,
        "link": latest.link,
        "published": latest.published
    }

# === OpenAI GPTで要約を作成 ===
def summarize_with_openai(title, summary):
    client = OpenAI(api_key=OPENAI_API_KEY)

    prompt = f"""
以下はAWS公式のアップデート情報です。
Zennに投稿できるような技術ブログ風のMarkdown形式の要約を作成してください。

## タイトル
{title}

## 概要
{summary}
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content.strip()

# === Slackに通知 ===
def notify_to_slack(markdown_summary, link):
    message = f":aws: *AWSアップデート速報*\n{markdown_summary}\n\n🔗 詳細: {link}"
    response = requests.post(SLACK_WEBHOOK_URL, json={"text": message})
    if response.status_code != 200:
        raise Exception(f"Slack通知失敗: {response.status_code}, {response.text}")

# === メイン処理 ===
def main():
    update = fetch_aws_update()
    markdown_summary = summarize_with_openai(update["title"], update["summary"])
    notify_to_slack(markdown_summary, update["link"])

if __name__ == "__main__":
    main()

