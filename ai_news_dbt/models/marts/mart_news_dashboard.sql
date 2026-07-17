with articles as (

    select *
    from {{ ref('stg_news_articles') }}

),

enrichment as (

    select
        article_key,
        is_relevant,
        relevance_score,
        relevance_reason,
        category,
        industry,
        vendor,
        ai_tool,
        use_case,
        business_impact,
        sentiment_label,
        sentiment_score,
        summary,
        model_name,
        prompt_version,
        enriched_at

    from {{ source('raw_news', 'article_enrichment') }}

),

final as (

    select
        articles.article_key,

        articles.title,
        articles.description,
        articles.article_url,
        articles.image_url,

        articles.source_name,
        articles.author,
        articles.provider,

        articles.published_at,
        articles.published_date,
        articles.news_age_days,
        articles.news_age_bucket,

        articles.language,
        articles.country,
        articles.source_category,

        enrichment.is_relevant,
        enrichment.relevance_score,
        enrichment.relevance_reason,

        enrichment.category as ai_category,
        enrichment.industry,
        enrichment.vendor,
        enrichment.ai_tool,
        enrichment.use_case,
        enrichment.business_impact,

        enrichment.sentiment_label,
        enrichment.sentiment_score,
        enrichment.summary,

        enrichment.model_name,
        enrichment.prompt_version,
        enrichment.enriched_at,

        articles.batch_id,
        articles.ingested_at

    from articles

    inner join enrichment
        on articles.article_key = enrichment.article_key

)

select *
from final