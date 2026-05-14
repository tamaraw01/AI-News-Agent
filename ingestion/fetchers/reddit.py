"""Reddit fetcher for community-driven news."""

from datetime import datetime

from config.settings import settings
from loguru import logger
from praw import Reddit

from ingestion.fetchers.base import BaseFetcher, RawArticle


class RedditFetcher(BaseFetcher):
    """Fetch news from Reddit subreddits."""

    # Subreddits to monitor (no r/ prefix)
    SUBREDDITS = [
        "worldnews",
        "news",
        "technology",
        "science",
        "Futurology",
        "geopolitics",
        "Economics",
        "climate",
        "space",
        "MachineLearning",
        "artificial",
        "singularity",
        "Bitcoin",
        "stocks",
        "investing",
        "indonesia",
        "ASEAN",
        "europe",
        "asia",
        "africa",
        "todayilearned",
        "explainlikeimfive",
    ]

    @property
    def name(self) -> str:
        return "reddit"

    @property
    def source_type(self) -> str:
        return "reddit"

    async def fetch(self) -> list[RawArticle]:
        """Fetch posts from Reddit subreddits."""
        if not settings.reddit_client_id or not settings.reddit_client_secret:
            logger.warning("Reddit credentials not configured, skipping")
            return []

        articles = []

        try:
            reddit = Reddit(
                client_id=settings.reddit_client_id,
                client_secret=settings.reddit_client_secret,
                user_agent=settings.reddit_user_agent,
            )

            for subreddit_name in self.SUBREDDITS:
                try:
                    logger.debug(f"Fetching Reddit: r/{subreddit_name}")
                    subreddit = reddit.subreddit(subreddit_name)

                    for submission in subreddit.hot(limit=settings.max_articles_per_source):
                        if submission.score < 50 or submission.over_18:  # Filter low engagement and NSFW
                            continue

                        article = RawArticle(
                            title=submission.title.strip(),
                            url=submission.url.strip(),
                            content=submission.selftext if submission.selftext else None,
                            source=f"Reddit r/{subreddit_name}",
                            source_type="reddit",
                            published_at=datetime.fromtimestamp(submission.created_utc),
                            language="en",
                            country=None,
                            raw_data={
                                "score": submission.score,
                                "comments": submission.num_comments,
                                "author": str(submission.author),
                                "subreddit": subreddit_name,
                            },
                        )

                        if article.title and article.url:
                            articles.append(article)

                except Exception as e:
                    logger.warning(f"Error fetching r/{subreddit_name}: {e}")

            logger.info(f"Reddit fetcher: collected {len(articles)} articles")

        except Exception as e:
            logger.error(f"Reddit fetcher error: {e}")

        return articles
