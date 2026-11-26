use std::{path::Path, process::Command};

fn main() {
    let checkout = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../build/tools/bullet");
    let revision = Command::new("git")
        .arg("-C").arg(&checkout).args(["rev-parse", "HEAD"])
        .output().expect("git is required to verify the Bullet dependency revision");
    assert!(revision.status.success(), "see docs/BULLET.md for the required Bullet checkout");
    assert_eq!(String::from_utf8_lossy(&revision.stdout).trim(),
        "5d70177680437b7c0ddf958bd4722d95afa78b0c", "unsupported Bullet revision");
    let clean = Command::new("git").arg("-C").arg(&checkout)
        .args(["diff", "--quiet", "HEAD", "--"]).status().expect("could not inspect Bullet tree");
    assert!(clean.success(), "use a clean upstream Bullet checkout");
    println!("cargo:rerun-if-changed={}", checkout.join(".git/HEAD").display());
    println!("cargo:rerun-if-changed={}", checkout.join("crates").display());
}
