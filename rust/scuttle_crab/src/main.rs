use scuttle_crab::serve;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    serve().await
}
