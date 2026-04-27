use std::fs;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

use scuttle_crab::crawler::matcher::{match_article, MatchType};
use scuttle_crab::domain::company::load_companies;

fn temp_file_path(name: &str) -> PathBuf {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("time should move forward")
        .as_nanos();

    std::env::temp_dir().join(format!("scuttle_crab_{name}_{nanos}.json"))
}

#[test]
fn loads_company_reference_file() {
    let path = temp_file_path("companies");
    let json = r#"
    [
      {
        "name": "Apple",
        "ticker": "AAPL",
        "aliases": ["Apple", "Apple Inc."]
      },
      {
        "name": "Microsoft",
        "ticker": "MSFT",
        "aliases": ["Microsoft", "Microsoft Corp."]
      }
    ]
    "#;

    fs::write(&path, json).expect("reference file should be written");
    let companies = load_companies(&path).expect("companies should load");
    fs::remove_file(&path).ok();

    assert_eq!(companies.len(), 2);
    assert_eq!(companies[0].ticker, "AAPL");
    assert_eq!(companies[1].aliases[1], "Microsoft Corp.");
}

#[test]
fn matches_exact_tickers_and_aliases_case_insensitively() {
    let path = temp_file_path("match_companies");
    let json = r#"
    [
      {
        "name": "Apple",
        "ticker": "AAPL",
        "aliases": ["Apple", "Apple Inc."]
      },
      {
        "name": "Microsoft",
        "ticker": "MSFT",
        "aliases": ["Microsoft", "Microsoft Corp."]
      }
    ]
    "#;

    fs::write(&path, json).expect("reference file should be written");
    let companies = load_companies(&path).expect("companies should load");
    fs::remove_file(&path).ok();

    let result = match_article(
        "apple rises after earnings",
        "Analysts said AAPL and Microsoft Corp. both moved higher.",
        &companies,
    );

    assert_eq!(result.tickers, vec!["AAPL", "MSFT"]);
    assert_eq!(result.companies, vec!["Apple", "Microsoft"]);
    assert_eq!(result.mentions[0].match_type, MatchType::Alias);
    assert_eq!(result.mentions[1].match_type, MatchType::Ticker);
    assert_eq!(result.mentions[2].match_type, MatchType::Alias);
}

#[test]
fn does_not_match_partial_words() {
    let path = temp_file_path("partial_words");
    let json = r#"
    [
      {
        "name": "Meta",
        "ticker": "META",
        "aliases": ["Meta"]
      }
    ]
    "#;

    fs::write(&path, json).expect("reference file should be written");
    let companies = load_companies(&path).expect("companies should load");
    fs::remove_file(&path).ok();

    let result = match_article(
        "Metaphor in modern writing",
        "This article talks about metadata and metamorphic tests.",
        &companies,
    );

    assert!(result.tickers.is_empty());
    assert!(result.companies.is_empty());
    assert!(result.mentions.is_empty());
}
