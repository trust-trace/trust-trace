use std::fs;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

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
