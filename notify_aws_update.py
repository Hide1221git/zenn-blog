import feedparser
import requests
import datetime
from openai import OpenAI
import os
import sys

# === 設定 ===
AWS_RSS_URL = "https://aws.amazon.com/new/feed/"
# Github Secretsに保存してあるものを取得
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

    ## 現在時刻を取得し、現在のAWSの仕組みと、アップデート情報で何が違うのかを比較して、どのような違いがあるのかをまとめて。また、形式は以下を守ってください。
    ## 形式
    ・現在までのAWSの仕組み
    ・現在までの課題をや、クラウド環境を構築する人の悩みを収集し、端的に説明
    ・アップデートを使って、どのように悩みが解決されるのかを説明

    ## 検証方法

    """

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content.strip(), response.usage.total_tokens

# === Slackに通知 ===
def notify_to_slack(markdown_summary, link, total_tokens):

    message = (
        f":aws: *AWSアップデート速報*\n"
        f"{markdown_summary}\n\n"
        f"🔗 詳細: {link}\n"
        f"💰 今日の要約トークン: {total_tokens}\n"
        "Open AI APIの料金表は、https://openai.com/api/pricing/ をご覧ください。\n"
    )

    response = requests.post(SLACK_WEBHOOK_URL, json={"text": message})
    if response.status_code != 200:
        raise Exception(f"Slack通知失敗: {response.status_code}, {response.text}")

# === メイン処理 ===
def main():
    update = fetch_aws_update()
    markdown_summary, total_tokens = summarize_with_openai(update["title"], update["summary"])
    notify_to_slack(markdown_summary, update["link"], total_tokens)

if __name__ == "__main__":
    main()

