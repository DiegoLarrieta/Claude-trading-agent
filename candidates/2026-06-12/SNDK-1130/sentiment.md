# Sentiment: SNDK

**CHATTER LEVEL:** normal

**TONE:** mixed

**CROWD THESIS:** After a 690% YTD run into analyst upgrades, the crowd is split (50/50 bullish/bearish on tagged posts). Some authors calling "strong" continuation / "$2000+ soon"; others calling "top" and comparing the move to a meme stock scam.

**CONTRARIAN READ:** The silence is conspicuous. After a +5.7% +1.3x-volume day at near 52-week highs following a $690% rally, we see only 30 messages in 17 minutes on Stocktwits with zero net conviction (8 bullish, 8 bearish, 14 untagged). Watchers are engaged (22,775), but the chatter is neither euphoric nor scared — it's muted and divided. This suggests either exhaustion (the crowd already positioned, no fresh buyers left) or indifference (real money hasn't noticed the move yet). Lesson #8 flags momentum continuation as a measured positive edge, but Lesson #4 warns blind buying backtests negative; selectivity matters. The split tone here offers no clear crowd consensus to trade against.

**POSTS SAMPLED:** Data unavailable — Reddit API credentials not configured (.env missing REDDIT_* keys); Stocktwits only.

**RAW DATA:**

```
Stocktwits sentiment_feed.py output (SNDK, fetched 2026-06-12T15:32:47Z):

{
  "message_count": 30,
  "bullish": 8,
  "bearish": 8,
  "untagged": 14,
  "bullish_ratio_of_tagged": 0.5,
  "newest": "2026-06-12T15:32:41Z",
  "oldest": "2026-06-12T15:15:55Z",
  "top_author_samples": [
    {
      "body": "$SNDK Proving strong \nhttps://share.trendspider.com/chart/SNDK/6682b2iriz",
      "sentiment_tag": "Bullish",
      "author_followers": 60618
    },
    {
      "body": "$SNDK Top.",
      "sentiment_tag": "Bearish",
      "author_followers": 1081
    },
    {
      "body": "$VYX That doesn't happen every day  \n \nCheck this out: \nPolitician: Ro Khanna \nPrevious big move: Bought $SNDK at $42 \nNow: Dropped ~$45K into $VYX,  \na company with a market cap around $981M \n \nWhy i",
      "sentiment_tag": null,
      "author_followers": 591
    },
    {
      "body": "$SNDK  tier 4 memory glut,   No demand \n\nIt's useless scam worse than meme $GME",
      "sentiment_tag": "Bearish",
      "author_followers": 546
    },
    {
      "body": "$SNDK $2000+ soon",
      "sentiment_tag": "Bullish",
      "author_followers": 334
    }
  ],
  "ticker": "SNDK",
  "watchers": 22775,
  "source": "stocktwits",
  "fetched_at": "2026-06-12T15:32:47.141789+00:00"
}
```
