use std::fs;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

use scuttle_crab::domain::company::{load_companies, load_companies_if_exists};

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
        "aliases": ["Apple", "Apple Inc."],
        "krs": "0000000001"
      },
      {
        "name": "Microsoft",
        "ticker": "MSFT",
        "aliases": ["Microsoft", "Microsoft Corp."],
        "nip": "1234567890"
      }
    ]
    "#;

    fs::write(&path, json).expect("reference file should be written");
    let companies = load_companies(&path).expect("companies should load");
    fs::remove_file(&path).ok();

    assert_eq!(companies.len(), 2);
    assert_eq!(companies[0].ticker, "AAPL");
    assert_eq!(companies[0].krs.as_deref(), Some("0000000001"));
    assert_eq!(companies[1].aliases[1], "Microsoft Corp.");
    assert_eq!(companies[1].nip.as_deref(), Some("1234567890"));
}

#[test]
fn missing_company_reference_file_returns_empty_list() {
    let path = temp_file_path("companies_missing");

    let companies = load_companies_if_exists(&path).expect("missing file should be ignored");

    assert!(companies.is_empty());
}
