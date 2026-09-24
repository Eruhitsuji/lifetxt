use std::{env, fs, path::PathBuf};

fn main() {
    let manifest_dir = PathBuf::from(env::var_os("CARGO_MANIFEST_DIR").unwrap());
    let project = manifest_dir.parent().unwrap().join("pyproject.toml");
    let text = fs::read_to_string(&project)
        .unwrap_or_else(|e| panic!("cannot read {}: {e}", project.display()));
    let version = text
        .lines()
        .skip_while(|line| !line.trim_start().starts_with("version = \""))
        .next()
        .and_then(|line| line.split('"').nth(1))
        .filter(|value| {
            value.split('.').count() == 3 && value.chars().all(|c| c.is_ascii_digit() || c == '.')
        })
        .unwrap_or_else(|| {
            panic!(
                "canonical project version missing from {}",
                project.display()
            )
        });
    println!("cargo:rustc-env=LIFETXT_VERSION={version}");
    println!("cargo:rerun-if-changed={}", project.display());
}
