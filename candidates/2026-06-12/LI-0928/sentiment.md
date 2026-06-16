# LI — Sentiment Analysis

## CHATTER LEVEL
**normal**

30 messages across a 7-day window is moderate baseline chatter for a NASDAQ cap stock (LI watchers: 31,220). No viral surge; consistent idle commentary, not panic-driven volume spikes.

## TONE
**bearish**

Of 4 tagged posts (30 total minus 26 untagged), 3 bullish and 1 bearish yields a 75% bullish ratio—but the raw posts themselves are dominated by bearish framing: "hit 52-week lows," "rejected early," "decline into oversold," "ATL," competition emoji. The tags are outliers; the actual sentiment narrative is down.

## CROWD THESIS
Chinese EV sector is structurally weak amid domestic housing collapse and geopolitical stress (US/Iran); LI is no exception—oversold but not yet a buy in this macro backdrop.

## CONTRARIAN READ
The crowd is correctly identifying sector weakness but may be ahead of a short-term rebound (the +4.8% move today occurred AFTER most of these posts were dated 2026-06-11 or earlier). The posts discuss 52-week lows and ATLs as if they're fresh developments, but the 52-week range per candidate.json is 13.36–32.025, meaning current price (14.435) is near the bottom already—there's less downside left than the tone suggests. If the crowd is waiting for confirmation of "further decline," a pop off these lows may surprise them.

## POSTS SAMPLED
4 across Stocktwits (full source used, no Reddit data available per the API availability notes).

## RAW DATA

```
[
  {
    "message_count": 30,
    "bullish": 3,
    "bearish": 1,
    "untagged": 26,
    "bullish_ratio_of_tagged": 0.75,
    "newest": "2026-06-11T18:21:41Z",
    "oldest": "2026-06-05T15:22:50Z",
    "top_author_samples": [
      {
        "body": "Why Did EH, AVEX, LI Stocks Hit 52-Week Lows Today? \n\n$EH $AVEX $LI\n\nhttps://stocktwits.com/news/equity/markets/why-did-eh-avex-li-stocks-hit-52-week-lows-today/cZ06dMvR7RC",
        "sentiment_tag": null,
        "author_followers": 107397
      },
      {
        "body": "🚀 $LI Trade Recap 📊 \n \n@ripster47 \nhighlighted the bearish bias premarket with clear plan to short pops as price stayed under all MTF clouds. \n \nAs price rejected early and remained below the 5 12 wit",
        "sentiment_tag": null,
        "author_followers": 9312
      },
      {
        "body": "$BABA $LI $XPEV $JD $PDD Chinese stocks continue their decline ultimately into Oversold conditions (IMO), given the backdrop of the US/Iran conflict, the weak domestic housing market, strained liquidi",
        "sentiment_tag": "Bullish",
        "author_followers": 5278
      },
      {
        "body": "$LI A new ATL 13.5!",
        "sentiment_tag": null,
        "author_followers": 5070
      },
      {
        "body": "$XPEV $NIO $LI \n\nCompetition 🔥🔥🔥",
        "sentiment_tag": null,
        "author_followers": 2120
      }
    ],
    "ticker": "LI",
    "watchers": 31220,
    "source": "stocktwits",
    "fetched_at": "2026-06-12T14:18:03.567727+00:00"
  }
]
```
