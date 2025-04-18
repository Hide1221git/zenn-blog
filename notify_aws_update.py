import feedparser
import requests
import datetime
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

# === 今日のOpenAI使用料（ドル）を取得 ===
def get_today_usage_dollars():
    today = datetime.date.today()
    start = today.strftime("%Y-%m-%d")
    end = today.strftime("%Y-%m-%d")

    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    url = f"https://api.openai.com/v1/dashboard/billing/usage?start_date={start}&end_date={end}"
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        cents = res.json().get("total_usage", 0)
        return f"${cents / 100:.4f}"
    else:
        return "取得失敗"

# === 今月の上限・使用量・残高を取得 ===
def get_openai_usage_and_limit():
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}

    # 利用上限
    limit_res = requests.get("https://api.openai.com/v1/dashboard/billing/subscription", headers=headers)
    if limit_res.status_code != 200:
        return "上限取得失敗", "使用量取得失敗", "残高取得失敗"
    hard_limit_usd = limit_res.json().get("hard_limit_usd", 0.0)

    # 今月の使用量
    today = datetime.date.today()
    start_date = today.replace(day=1).strftime("%Y-%m-%d")
    end_date = today.strftime("%Y-%m-%d")
    usage_url = f"https://api.openai.com/v1/dashboard/billing/usage?start_date={start_date}&end_date={end_date}"
    usage_res = requests.get(usage_url, headers=headers)
    if usage_res.status_code != 200:
        return f"${hard_limit_usd:.2f}", "使用量取得失敗", "残高取得失敗"

    usage_usd = usage_res.json().get("total_usage", 0) / 100.0
    remaining_usd = hard_limit_usd - usage_usd

    return (
        f"${hard_limit_usd:.2f}",
        f"${usage_usd:.4f}",
        f"${remaining_usd:.4f}"
    )

# === Slackに通知 ===
def notify_to_slack(markdown_summary, link):
    today_cost = get_today_usage_dollars()
    limit, usage, remaining = get_openai_usage_and_limit()

    message = (
        f":aws: *AWSアップデート速報*\n"
        f"{markdown_summary}\n\n"
        f"🔗 詳細: {link}\n"
        f"💰 今日の要約コスト: {today_cost}\n"
        f"🧾 今月の使用量: {usage} / {limit}\n"
        f"💸 残りのクレジット: {remaining}"
    )

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

