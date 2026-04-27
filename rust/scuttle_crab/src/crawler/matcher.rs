//! Deterministic company and ticker matching.

use crate::domain::company::CompanyRecord;

/// How a company mention was matched.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum MatchType {
    Ticker,
    Alias,
}

/// One matched mention within an article.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CompanyMention {
    pub name: String,
    pub ticker: String,
    pub match_type: MatchType,
    pub matched_text: String,
}

/// Aggregated matching output for one article.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct MatchResult {
    pub tickers: Vec<String>,
    pub companies: Vec<String>,
    pub mentions: Vec<CompanyMention>,
}

/// Match a title and body against a fixed company reference list.
pub fn match_article(title: &str, body: &str, companies: &[CompanyRecord]) -> MatchResult {
    let mut result = MatchResult::default();

    for company in companies {
        push_alias_matches(title, company, &mut result);
        push_ticker_matches(title, company, &mut result);
        push_ticker_matches(body, company, &mut result);
        push_alias_matches(body, company, &mut result);
    }

    result
}

fn push_ticker_matches(text: &str, company: &CompanyRecord, result: &mut MatchResult) {
    if contains_exact_term(text, &company.ticker) {
        push_company(result, company, MatchType::Ticker, company.ticker.clone());
    }
}

fn push_alias_matches(text: &str, company: &CompanyRecord, result: &mut MatchResult) {
    for alias in &company.aliases {
        if contains_exact_term(text, alias) {
            push_company(result, company, MatchType::Alias, alias.clone());
            break;
        }
    }
}

fn push_company(
    result: &mut MatchResult,
    company: &CompanyRecord,
    match_type: MatchType,
    matched_text: String,
) {
    if !result
        .tickers
        .iter()
        .any(|ticker| ticker == &company.ticker)
    {
        result.tickers.push(company.ticker.clone());
    }

    if !result.companies.iter().any(|name| name == &company.name) {
        result.companies.push(company.name.clone());
    }

    result.mentions.push(CompanyMention {
        name: company.name.clone(),
        ticker: company.ticker.clone(),
        match_type,
        matched_text,
    });
}

fn contains_exact_term(text: &str, needle: &str) -> bool {
    let text_lower = text.to_lowercase();
    let needle_lower = needle.to_lowercase();

    text_lower.match_indices(&needle_lower).any(|(start, _)| {
        let end = start + needle_lower.len();
        let left_ok = start == 0
            || !text_lower[..start]
                .chars()
                .next_back()
                .is_some_and(is_word_char);
        let right_ok =
            end == text_lower.len() || !text_lower[end..].chars().next().is_some_and(is_word_char);

        left_ok && right_ok
    })
}

fn is_word_char(ch: char) -> bool {
    ch.is_ascii_alphanumeric()
}
