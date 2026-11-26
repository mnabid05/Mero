//! Test oracle only: convert White-relative FEN | cp | WDL via the pinned upstream crate.
use bulletformat::{BulletFormat, ChessBoard};
use std::io::{self, BufRead, Write};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    if !cfg!(target_endian = "little") {
        return Err("the upstream raw struct encoder needs a little-endian host".into());
    }
    let mut output = io::BufWriter::new(io::stdout().lock());
    for line in io::stdin().lock().lines() {
        let board: ChessBoard = line?.parse()?;
        output.write_all(ChessBoard::as_bytes_slice(&[board]))?;
    }
    output.flush()?;
    Ok(())
}
