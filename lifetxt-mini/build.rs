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
            let parts: Vec<_> = value.split('.').collect();
            (parts.len() == 3 || parts.len() == 4)
                && parts.iter().all(|part| {
                    !part.is_empty()
                        && part.chars().all(|c| c.is_ascii_digit())
                        && (part.len() == 1 || !part.starts_with('0'))
                })
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
