with source_data as (

    select *
    from {{ source('raw_news', 'news_articles_raw') }}

),

renamed as (

    select
        article_key,
        lower(trim(provider)) as provider,
        trim(query_name) as query_name,
        trim(query_text) as query_text,
        trim(source_name) as source_name,
        trim(source_id) as source_id,
        trim(author) as author,
        trim(title) as title,
        trim(description) as description,
        trim(article_url) as article_url,
        trim(image_url) as image_url,

        published_at,
        cast(published_at as date) as published_date,

        datediff(
            day,
            cast(published_at as date),
            current_date()
        ) as news_age_days,

        case
            when published_at is null then 'Unknown'
            when datediff(day, cast(published_at as date), current_date()) = 0
                then 'Today'
            when datediff(day, cast(published_at as date), current_date()) = 1
                then '1 day old'
            when datediff(day, cast(published_at as date), current_date()) <= 7
                then '2-7 days old'
            when datediff(day, cast(published_at as date), current_date()) <= 14
                then '8-14 days old'
            when datediff(day, cast(published_at as date), current_date()) <= 30
                then '15-30 days old'
            else 'More than 30 days old'
        end as news_age_bucket,

        lower(trim(language)) as language,
        trim(country) as country,
        trim(category) as source_category,
        batch_id,
        ingested_at,
        raw_json

    from source_data

    where title is not null

)

select *
from renamed